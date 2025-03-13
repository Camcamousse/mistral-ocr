import os
import json
import time
import base64
import requests
import random
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, url_for, redirect, session, flash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import threading
import uuid

# Importer notre script Mistral OCR
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mistral_ocr import MistralOCR, PDF_AVAILABLE

# Charger les variables d'environnement
load_dotenv()

# Importer WeasyPrint si disponible
try:
    # Utilisation de WeasyPrint version 52.5
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    print("WeasyPrint n'est pas installé. L'exportation PDF ne sera pas disponible.")
    print("Pour l'installer: pip install weasyprint==52.5")

# Utiliser la variable de mistral_ocr.py
WEASYPRINT_AVAILABLE = PDF_AVAILABLE

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Augmenté à 100 MB max
# Configuration pour permettre des requêtes plus grandes
app.config['MAX_CONTENT_PATH'] = 100 * 1024 * 1024  # 100 MB
# Taille maximale acceptée par l'API Mistral (52.4 MB)
app.config['MISTRAL_API_MAX_SIZE'] = 52.4 * 1024 * 1024  # 52.4 MB

# Assurez-vous que le dossier d'upload existe
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Dictionnaire pour stocker l'état des tâches OCR
ocr_tasks = {}

def allowed_file(filename):
    """Vérifie si le fichier a une extension autorisée"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'jpg', 'jpeg', 'png', 'gif'}

def get_api_key():
    """Récupère la clé API Mistral, en priorité depuis la session utilisateur"""
    # Vérifier d'abord si la clé est dans la session
    if 'mistral_api_key' in session and session['mistral_api_key']:
        return session['mistral_api_key']
    
    # Sinon, utiliser la clé du fichier .env
    return os.environ.get("MISTRAL_API_KEY")

def process_ocr(task_id, api_key, file_path=None, url=None, include_images=True, output_formats=None):
    """Fonction pour traiter l'OCR en arrière-plan"""
    try:
        # Initialiser l'état de la tâche
        ocr_tasks[task_id] = {
            'status': 'processing',
            'progress': 0,
            'result_paths': {},
            'error': None
        }
        
        # Si aucun format n'est spécifié, utiliser tous les formats disponibles
        if output_formats is None:
            output_formats = ['json', 'md', 'html']
            if WEASYPRINT_AVAILABLE:
                output_formats.append('pdf')
        
        # Vérifier la taille du fichier si un fichier est fourni
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            if file_size > app.config['MISTRAL_API_MAX_SIZE']:
                ocr_tasks[task_id]['status'] = 'error'
                ocr_tasks[task_id]['error'] = f"Le fichier est trop volumineux pour l'API Mistral. La taille maximale autorisée est de 52.4 Mo, mais votre fichier fait {file_size / (1024 * 1024):.1f} Mo. Veuillez réduire la taille du fichier ou le diviser en parties plus petites."
                return
        
        # Mettre à jour la progression
        for i in range(1, 11):
            time.sleep(0.5)  # Simuler le traitement
            ocr_tasks[task_id]['progress'] = i * 10
        
        # Vérifier si la clé API est fournie
        if not api_key:
            ocr_tasks[task_id]['status'] = 'error'
            ocr_tasks[task_id]['error'] = "Clé API Mistral non configurée. Veuillez configurer votre clé API dans les paramètres."
            return
        
        # Log pour le débogage (masqué pour la sécurité)
        masked_key = api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else api_key
        print(f"Utilisation de la clé API: {masked_key}")
        
        # Créer l'instance MistralOCR avec la clé API
        try:
            ocr = MistralOCR(api_key)
            
            # Fonction pour effectuer une tentative avec mécanisme de nouvelle tentative
            def try_with_retry(operation_func, max_retries=3, initial_delay=2):
                retries = 0
                last_error = None
                
                while retries < max_retries:
                    try:
                        return operation_func()
                    except Exception as e:
                        last_error = e
                        error_str = str(e)
                        
                        # Si c'est une erreur 520 de Cloudflare, on réessaie
                        if "520" in error_str and "Cloudflare" in error_str:
                            retries += 1
                            if retries < max_retries:
                                # Attente exponentielle avec un peu de hasard pour éviter les collisions
                                delay = initial_delay * (2 ** (retries - 1)) * (1 + random.random() * 0.1)
                                print(f"Erreur Cloudflare 520 détectée. Nouvelle tentative {retries}/{max_retries} dans {delay:.1f} secondes...")
                                time.sleep(delay)
                            else:
                                print(f"Échec après {max_retries} tentatives. Dernière erreur: {error_str}")
                                raise Exception(f"Les serveurs de Mistral semblent temporairement indisponibles (Erreur Cloudflare 520). Veuillez réessayer plus tard. Si le problème persiste, contactez le support Mistral.")
                        else:
                            # Pour les autres erreurs, on ne réessaie pas
                            raise
                
                # Si on arrive ici, c'est qu'on a épuisé toutes les tentatives
                raise last_error
            
            # Traiter selon le type d'entrée avec mécanisme de nouvelle tentative
            if url:
                result = try_with_retry(lambda: ocr.process_document_url(url, include_images))
            elif file_path:
                if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    result = try_with_retry(lambda: ocr.process_image_file(file_path, include_images))
                else:
                    result = try_with_retry(lambda: ocr.process_pdf_file(file_path, include_images))
            else:
                raise ValueError("Aucun fichier ou URL fourni")
            
            # Vérifier si une erreur s'est produite
            if "error" in result:
                ocr_tasks[task_id]['status'] = 'error'
                ocr_tasks[task_id]['error'] = result["error"]
                return
            
            # Préparer le chemin de base pour les fichiers de sortie
            base_output = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}")
            
            # Générer les différents formats de sortie
            if 'json' in output_formats:
                json_file = base_output + ".json"
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                ocr_tasks[task_id]['result_paths']['json'] = json_file
            
            if 'md' in output_formats:
                md_file = base_output + ".md"
                with open(md_file, "w", encoding="utf-8") as f:
                    for page in result.get("pages", []):
                        f.write(f"### Page {page.get('index')}\n\n")
                        # Améliorer le formatage des tableaux et des expressions mathématiques
                        page_markdown = ocr._enhance_tables_and_math(page.get("markdown", ""))
                        f.write(page_markdown + "\n\n")
                ocr_tasks[task_id]['result_paths']['md'] = md_file
            
            if 'html' in output_formats:
                html_file = base_output + ".html"
                ocr.generate_html_output(result, html_file)
                ocr_tasks[task_id]['result_paths']['html'] = html_file
            
            # Générer le PDF si demandé et si WeasyPrint est disponible
            if 'pdf' in output_formats and WEASYPRINT_AVAILABLE:
                pdf_file = base_output + ".pdf"
                html_file = base_output + ".html"
                
                # S'assurer que le fichier HTML existe
                if not os.path.exists(html_file) and 'html' not in output_formats:
                    ocr.generate_html_output(result, html_file)
                
                # Convertir HTML en PDF
                try:
                    # Générer le PDF à partir du HTML avec WeasyPrint v52.5
                    HTML(filename=html_file).write_pdf(pdf_file)
                    ocr_tasks[task_id]['result_paths']['pdf'] = pdf_file
                except Exception as e:
                    print(f"Erreur lors de la génération du PDF: {str(e)}")
                    ocr_tasks[task_id]['result_paths']['pdf'] = None
            
            # Mettre à jour l'état de la tâche
            ocr_tasks[task_id]['status'] = 'completed'
            
        except Exception as api_error:
            error_message = str(api_error)
            print(f"Erreur détaillée de l'API: {error_message}")
            
            # Personnaliser le message d'erreur selon le type d'erreur
            if "401" in error_message or "Unauthorized" in error_message:
                error_message = "Erreur d'authentification avec l'API Mistral. Votre clé API semble être invalide ou ne dispose pas des autorisations nécessaires pour accéder au service OCR. Veuillez vérifier votre clé API ou contacter le support Mistral."
            elif "520" in error_message and "Cloudflare" in error_message:
                error_message = "Les serveurs de Mistral semblent temporairement indisponibles (Erreur Cloudflare 520). Veuillez réessayer plus tard. Si le problème persiste, contactez le support Mistral."
            
            ocr_tasks[task_id]['status'] = 'error'
            ocr_tasks[task_id]['error'] = error_message
            return
        
    except Exception as e:
        print(f"Erreur générale: {str(e)}")
        ocr_tasks[task_id]['status'] = 'error'
        ocr_tasks[task_id]['error'] = str(e)

def test_api_key(api_key):
    """Teste la validité de la clé API Mistral"""
    try:
        # URL de l'API Mistral pour vérifier la clé
        # Utilisons l'endpoint models qui est plus léger et disponible pour tous les utilisateurs
        url = "https://api.mistral.ai/v1/models"
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        # Faire une requête simple pour vérifier la clé
        response = requests.get(url, headers=headers)
        
        # Si la réponse est 200, la clé est valide pour l'API générale
        if response.status_code == 200:
            print(f"Clé API validée avec succès: {response.status_code}")
            return True, "Clé API valide"
        else:
            error_msg = f"Erreur de validation de la clé API: {response.status_code}"
            if response.text:
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('message', '')}"
                except:
                    error_msg += f" - {response.text}"
            print(f"Erreur de validation: {error_msg}")
            return False, error_msg
    except Exception as e:
        print(f"Exception lors de la validation: {str(e)}")
        return False, f"Erreur lors de la vérification de la clé API: {str(e)}"

@app.route('/')
def index():
    """Page d'accueil"""
    # Vérifier si une clé API est configurée
    api_key = get_api_key()
    has_api_key = bool(api_key)
    # Vérifier si WeasyPrint est disponible pour la génération de PDF
    return render_template('index.html', has_api_key=has_api_key, pdf_available=WEASYPRINT_AVAILABLE)

@app.route('/api-config', methods=['GET', 'POST'])
def api_config():
    """Page de configuration de la clé API"""
    if request.method == 'POST':
        api_key = request.form.get('api_key', '').strip()
        
        if not api_key:
            flash("Veuillez entrer une clé API valide", "error")
            return redirect(url_for('api_config'))
        
        # Tester la validité de la clé API
        is_valid, message = test_api_key(api_key)
        if not is_valid:
            flash(f"La clé API n'est pas valide: {message}", "error")
            return redirect(url_for('api_config'))
        
        # Masquer la clé pour les logs
        masked_key = api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else api_key
        print(f"Clé API configurée: {masked_key}")
        
        # Stocker la clé API dans la session
        session['mistral_api_key'] = api_key
        flash("Clé API enregistrée avec succès", "success")
        return redirect(url_for('index'))
    
    # Récupérer la clé API actuelle (si elle existe dans la session)
    current_api_key = session.get('mistral_api_key', '')
    # Masquer la clé pour l'affichage
    masked_api_key = ''
    if current_api_key:
        # Afficher seulement les 4 premiers et 4 derniers caractères
        if len(current_api_key) > 8:
            masked_api_key = current_api_key[:4] + '*' * (len(current_api_key) - 8) + current_api_key[-4:]
        else:
            masked_api_key = current_api_key
    
    return render_template('api_config.html', masked_api_key=masked_api_key)

@app.route('/clear-api-key', methods=['POST'])
def clear_api_key():
    """Supprime la clé API de la session"""
    if 'mistral_api_key' in session:
        session.pop('mistral_api_key')
        flash("Clé API supprimée avec succès", "success")
    return redirect(url_for('api_config'))

@app.route('/process-file', methods=['POST'])
def process_file():
    """Traite un fichier téléchargé pour OCR"""
    # Vérifier si une clé API est configurée
    api_key = get_api_key()
    if not api_key:
        return jsonify({
            'status': 'error',
            'message': 'Clé API Mistral non configurée. Veuillez configurer votre clé API dans les paramètres.'
        }), 400
    
    # Vérifier si un fichier a été téléchargé
    if 'file' not in request.files:
        return jsonify({
            'status': 'error',
            'message': 'Aucun fichier n\'a été téléchargé'
        }), 400
    
    file = request.files['file']
    
    # Vérifier si le fichier a un nom
    if file.filename == '':
        return jsonify({
            'status': 'error',
            'message': 'Aucun fichier sélectionné'
        }), 400
    
    # Vérifier si le fichier est autorisé
    if not allowed_file(file.filename):
        return jsonify({
            'status': 'error',
            'message': 'Type de fichier non supporté. Formats acceptés: PDF, JPG, JPEG, PNG, GIF'
        }), 400
    
    # Sauvegarder le fichier
    filename = secure_filename(file.filename)
    task_id = str(uuid.uuid4())
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_{filename}")
    file.save(file_path)
    
    # Récupérer les formats de sortie demandés
    output_formats = request.form.getlist('output_formats')
    if not output_formats:
        output_formats = ['json', 'md', 'html']
        if WEASYPRINT_AVAILABLE:
            output_formats.append('pdf')
    
    # Lancer le traitement OCR en arrière-plan
    thread = threading.Thread(target=process_ocr, args=(task_id, api_key, file_path, None, True, output_formats))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'status': 'processing',
        'task_id': task_id,
        'message': 'Traitement OCR en cours'
    })

@app.route('/process-url', methods=['POST'])
def process_url():
    """Traite une URL pour OCR"""
    # Vérifier si une clé API est configurée
    api_key = get_api_key()
    if not api_key:
        return jsonify({
            'status': 'error',
            'message': 'Clé API Mistral non configurée. Veuillez configurer votre clé API dans les paramètres.'
        }), 400
    
    # Récupérer l'URL
    url = request.form.get('url', '').strip()
    if not url:
        return jsonify({
            'status': 'error',
            'message': 'Aucune URL fournie'
        }), 400
    
    # Vérifier si l'URL est valide
    if not url.startswith(('http://', 'https://')):
        return jsonify({
            'status': 'error',
            'message': 'URL invalide. L\'URL doit commencer par http:// ou https://'
        }), 400
    
    # Récupérer les formats de sortie demandés
    output_formats = request.form.getlist('output_formats')
    if not output_formats:
        output_formats = ['json', 'md', 'html']
        if WEASYPRINT_AVAILABLE:
            output_formats.append('pdf')
    
    # Générer un ID de tâche
    task_id = str(uuid.uuid4())
    
    # Lancer le traitement OCR en arrière-plan
    thread = threading.Thread(target=process_ocr, args=(task_id, api_key, None, url, True, output_formats))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'status': 'processing',
        'task_id': task_id,
        'message': 'Traitement OCR en cours'
    })

@app.route('/task-status/<task_id>')
def task_status(task_id):
    """Récupère l'état d'une tâche OCR"""
    if task_id not in ocr_tasks:
        return jsonify({
            'status': 'error',
            'message': 'Tâche non trouvée'
        }), 404
    
    task = ocr_tasks[task_id]
    
    # Construire les URLs pour les résultats
    result_urls = {}
    for format_type, file_path in task.get('result_paths', {}).items():
        if file_path:
            result_urls[format_type] = url_for('download_result', task_id=task_id, format_type=format_type)
    
    return jsonify({
        'status': task['status'],
        'progress': task.get('progress', 0),
        'error': task.get('error'),
        'result_urls': result_urls
    })

@app.route('/download-result/<task_id>/<format_type>')
def download_result(task_id, format_type):
    """Télécharge le résultat d'une tâche OCR"""
    if task_id not in ocr_tasks:
        flash("Tâche non trouvée", "error")
        return redirect(url_for('index'))
    
    task = ocr_tasks[task_id]
    
    if task['status'] != 'completed':
        flash("Le traitement n'est pas encore terminé", "error")
        return redirect(url_for('index'))
    
    if format_type not in task.get('result_paths', {}):
        flash(f"Format {format_type} non disponible", "error")
        return redirect(url_for('index'))
    
    file_path = task['result_paths'][format_type]
    
    if not os.path.exists(file_path):
        flash("Fichier non trouvé", "error")
        return redirect(url_for('index'))
    
    # Déterminer le type MIME
    mime_type = 'application/octet-stream'  # Par défaut
    if format_type == 'json':
        mime_type = 'application/json'
    elif format_type == 'md':
        mime_type = 'text/markdown'
    elif format_type == 'html':
        mime_type = 'text/html'
    elif format_type == 'pdf':
        mime_type = 'application/pdf'
    
    return send_file(file_path, mimetype=mime_type, as_attachment=True, download_name=f"ocr_result.{format_type}")

@app.route('/view-result/<task_id>/<format_type>')
def view_result(task_id, format_type):
    """Affiche le résultat d'une tâche OCR dans le navigateur"""
    if task_id not in ocr_tasks:
        flash("Tâche non trouvée", "error")
        return redirect(url_for('index'))
    
    task = ocr_tasks[task_id]
    
    if task['status'] != 'completed':
        flash("Le traitement n'est pas encore terminé", "error")
        return redirect(url_for('index'))
    
    if format_type not in task.get('result_paths', {}):
        flash(f"Format {format_type} non disponible", "error")
        return redirect(url_for('index'))
    
    file_path = task['result_paths'][format_type]
    
    if not os.path.exists(file_path):
        flash("Fichier non trouvé", "error")
        return redirect(url_for('index'))
    
    # Déterminer le type MIME
    mime_type = 'application/octet-stream'  # Par défaut
    if format_type == 'json':
        mime_type = 'application/json'
    elif format_type == 'md':
        mime_type = 'text/markdown'
    elif format_type == 'html':
        mime_type = 'text/html'
    elif format_type == 'pdf':
        mime_type = 'application/pdf'
    
    return send_file(file_path, mimetype=mime_type)

if __name__ == '__main__':
    # Créer le dossier d'upload s'il n'existe pas
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Démarrer l'application
    app.run(debug=True)