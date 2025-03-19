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
try:
    from mistral_ocr import MistralOCR, PDF_AVAILABLE
except ImportError as e:
    print(f"Erreur d'importation de mistral_ocr.py: {str(e)}")
    print("Assurez-vous que le fichier mistral_ocr.py est présent à la racine du projet.")
    sys.exit(1)

# Charger les variables d'environnement
load_dotenv()

# Désactiver WeasyPrint par défaut
WEASYPRINT_AVAILABLE = False

# Utiliser la variable de mistral_ocr.py
if PDF_AVAILABLE:
    WEASYPRINT_AVAILABLE = True
    print("PDF_AVAILABLE est True dans mistral_ocr.py, donc la génération PDF sera activée.")
else:
    print("\n=== INFO: Génération PDF désactivée dans l'application web ===")
    print("La génération PDF est désactivée car PDF_AVAILABLE est False dans mistral_ocr.py")
    print("Pour l'activer:")
    print("1. Installez les dépendances système: brew install cairo pango gdk-pixbuf libffi")
    print("2. Installez WeasyPrint: pip install weasyprint==52.5")
    print("3. Modifiez mistral_ocr.py pour activer PDF_AVAILABLE")
    print("================================\n")

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
            # N'ajouter PDF que si WeasyPrint est disponible
            if WEASYPRINT_AVAILABLE:
                output_formats.append('pdf')
        elif 'pdf' in output_formats and not WEASYPRINT_AVAILABLE:
            # Si PDF est demandé mais pas disponible, on le retire et on l'indique
            output_formats.remove('pdf')
            print(f"Avertissement: PDF a été demandé mais WeasyPrint n'est pas disponible. Format PDF ignoré.")
        
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
                    # Importer WeasyPrint ici pour éviter les problèmes d'importation
                    from weasyprint import HTML
                    HTML(filename=html_file).write_pdf(pdf_file)
                    ocr_tasks[task_id]['result_paths']['pdf'] = pdf_file
                    print(f"PDF généré avec succès: {pdf_file}")
                except Exception as e:
                    print(f"Erreur lors de la génération du PDF: {str(e)}")
                    ocr_tasks[task_id]['result_paths']['pdf'] = None
            elif 'pdf' in output_formats and not WEASYPRINT_AVAILABLE:
                print(f"Impossible de générer le PDF car WeasyPrint n'est pas disponible")
            
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
    """Teste la validité de la clé API Mistral avec plusieurs méthodes"""
    try:
        print(f"Longueur de la clé API: {len(api_key)} caractères")
        print(f"Préfixe de la clé: {api_key[:6]}...")
        
        # Vérifier le format de base de la clé
        if not api_key.strip():
            return False, "La clé API est vide"
        
        if not api_key.startswith("mis_"):
            print("AVERTISSEMENT: La clé API ne commence pas par 'mis_', format potentiellement invalide")
        
        # Méthode 1: Vérifier avec l'endpoint models (la plus légère)
        print("Méthode 1: Test avec l'endpoint models")
        url = "https://api.mistral.ai/v1/models"
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"Réponse models: {response.status_code}")
            
            if response.status_code == 200:
                print("✓ Endpoint models: Succès")
                return True, "Clé API valide"
        except Exception as e:
            print(f"Échec de la méthode 1: {str(e)}")
        
        # Méthode 2: Vérifier avec l'endpoint chat (plus lourd)
        print("Méthode 2: Test avec l'endpoint chat")
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "mistral-tiny",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            print(f"Réponse chat: {response.status_code}")
            
            if response.status_code == 200:
                print("✓ Endpoint chat: Succès")
                return True, "Clé API valide"
        except Exception as e:
            print(f"Échec de la méthode 2: {str(e)}")
        
        # Méthode 3: Test direct avec le client Mistral
        print("Méthode 3: Test avec le client Mistral")
        try:
            from mistralai import Mistral
            client = Mistral(api_key=api_key)
            
            # On essaie juste d'initialiser le client et de récupérer les modèles disponibles
            models = client.list_models()
            print(f"✓ Client Mistral: Succès - {len(models)} modèles disponibles")
            return True, "Clé API valide"
        except Exception as e:
            print(f"Échec de la méthode 3: {str(e)}")
            # Vérifier si le message d'erreur indique un problème d'authentification
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                print("✗ Client Mistral: Échec d'authentification")
            else:
                print(f"✗ Client Mistral: Erreur - {error_msg}")
        
        # Si on arrive ici, aucune méthode n'a fonctionné
        error_msg = "La clé API n'est pas valide ou n'a pas les autorisations requises."
        
        # Ajouter des suggestions utiles
        error_msg += "\n\nSuggestions:\n"
        error_msg += "1. Vérifiez que vous avez bien copié la clé API complète depuis la console Mistral\n"
        error_msg += "2. Assurez-vous que la clé n'a pas expiré ou n'a pas été révoquée\n"
        error_msg += "3. Votre clé doit commencer par 'mis_' pour Mistral\n"
        error_msg += "4. Vérifiez que votre clé a accès à l'API OCR de Mistral (certaines clés ont des restrictions)\n"
        error_msg += "5. Créez une nouvelle clé API sur https://console.mistral.ai/api-keys/ si nécessaire"
        
        return False, error_msg
    except Exception as e:
        print(f"Exception générale lors de la validation: {str(e)}")
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
            # Formatter le message d'erreur pour l'affichage HTML
            error_html = message.replace('\n', '<br>')
            flash(f"La clé API n'est pas valide: {error_html}", "error")
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
    """Effacer la clé API de la session"""
    if 'mistral_api_key' in session:
        session.pop('mistral_api_key')
    flash("Clé API supprimée de la session", "success")
    return redirect(url_for('api_config'))

@app.route('/process', methods=['POST'])
def process():
    """Endpoint pour démarrer le traitement OCR"""
    # Vérifier si une clé API est configurée
    api_key = get_api_key()
    if not api_key:
        return jsonify({'error': 'Clé API Mistral non configurée. Veuillez configurer votre clé API dans les paramètres.'}), 400
    
    # Récupérer les formats de sortie demandés
    output_formats = request.form.getlist('output_formats')
    if not output_formats:
        output_formats = ['json', 'md', 'html']
        if WEASYPRINT_AVAILABLE:
            output_formats.append('pdf')
    
    task_id = str(uuid.uuid4())
    
    # Vérifier si une URL a été fournie
    url = request.form.get('url')
    if url and url.strip():
        # Démarrer le traitement OCR en arrière-plan
        thread = threading.Thread(target=process_ocr, args=(task_id, api_key, None, url.strip(), True, output_formats))
        thread.daemon = True
        thread.start()
        return jsonify({'task_id': task_id})
    
    # Vérifier si un fichier a été téléchargé
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier fourni'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    # Vérifier la taille du fichier
    try:
        file_size = len(file.read())
        file.seek(0)  # Réinitialiser le curseur du fichier
        
        if file_size > app.config['MAX_CONTENT_LENGTH']:
            return jsonify({'error': f'Le fichier est trop volumineux. La taille maximale autorisée est de {app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)} Mo.'}), 413
        
        # Vérifier également la limite de l'API Mistral
        if file_size > app.config['MISTRAL_API_MAX_SIZE']:
            return jsonify({'error': f'Le fichier est trop volumineux pour l\'API Mistral. La taille maximale autorisée est de 52.4 Mo, mais votre fichier fait {file_size / (1024 * 1024):.1f} Mo. Veuillez réduire la taille du fichier ou le diviser en parties plus petites.'}), 413
    except Exception as e:
        return jsonify({'error': f'Erreur lors de la vérification du fichier: {str(e)}'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_{filename}")
        file.save(file_path)
        
        # Démarrer le traitement OCR en arrière-plan
        thread = threading.Thread(target=process_ocr, args=(task_id, api_key, file_path, None, True, output_formats))
        thread.daemon = True
        thread.start()
        
        return jsonify({'task_id': task_id})
    
    return jsonify({'error': 'Type de fichier non autorisé'}), 400

@app.route('/status/<task_id>')
def status(task_id):
    """Endpoint pour vérifier l'état d'une tâche OCR"""
    if task_id not in ocr_tasks:
        return jsonify({'error': 'Tâche non trouvée'}), 404
    
    return jsonify(ocr_tasks[task_id])

@app.route('/download/<task_id>/<format>')
def download(task_id, format):
    """Endpoint pour télécharger le résultat OCR dans le format spécifié"""
    if task_id not in ocr_tasks or ocr_tasks[task_id]['status'] != 'completed':
        return jsonify({'error': 'Résultat non disponible'}), 404
    
    if format not in ocr_tasks[task_id]['result_paths']:
        return jsonify({'error': f'Format {format} non disponible'}), 404
    
    result_path = ocr_tasks[task_id]['result_paths'][format]
    if result_path is None or not os.path.exists(result_path):
        return jsonify({'error': 'Fichier non disponible ou non trouvé'}), 404
    
    # Déterminer le nom du fichier à télécharger
    download_name = f"ocr_result.{format}"
    
    return send_file(result_path, as_attachment=True, download_name=download_name)

@app.route('/view/<task_id>/<format>')
def view(task_id, format):
    """Endpoint pour visualiser le résultat OCR dans le format spécifié"""
    if task_id not in ocr_tasks or ocr_tasks[task_id]['status'] != 'completed':
        return jsonify({'error': 'Résultat non disponible'}), 404
    
    if format not in ocr_tasks[task_id]['result_paths'] or format not in ['html', 'pdf']:
        return jsonify({'error': f'Format {format} non disponible pour la visualisation'}), 404
    
    result_path = ocr_tasks[task_id]['result_paths'][format]
    if result_path is None or not os.path.exists(result_path):
        return jsonify({'error': 'Fichier non disponible ou non trouvé'}), 404
    
    # Pour HTML et PDF, on peut les afficher directement dans le navigateur
    return send_file(result_path)

@app.errorhandler(413)
def request_entity_too_large(error):
    """Gestionnaire d'erreur pour les fichiers trop volumineux"""
    return jsonify({'error': f'Le fichier est trop volumineux. La taille maximale autorisée est de {app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)} Mo.'}), 413

if __name__ == '__main__':
    # Utiliser waitress pour le serveur de production, plus stable que le serveur de développement Flask
    try:
        from waitress import serve
        print("Démarrage du serveur avec Waitress...")
        serve(app, host='0.0.0.0', port=5001)
    except ImportError:
        print("Waitress n'est pas installé, utilisation du serveur de développement Flask.")
        print("AVERTISSEMENT: L'application est accessible à toutes les interfaces réseau.")
        print("Pour des raisons de sécurité, utilisez cette configuration uniquement pour le développement.")
        app.run(host='0.0.0.0', port=5001, debug=False) 