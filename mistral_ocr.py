#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script pour effectuer l'OCR sur des documents à l'aide de l'API Mistral.
Ce script permet de traiter des fichiers PDF, des images et des URL de documents.
"""

import os
import sys
import argparse
import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Import de la librairie Mistral officielle
try:
    from mistralai import Mistral
except ImportError:
    print("La librairie mistralai n'est pas installée.")
    print("Installez-la avec: pip install mistralai")
    sys.exit(1)

# Imports pour la conversion Markdown vers HTML
try:
    import markdown2
    import re
    import shutil
    import uuid
    import time
except ImportError:
    print("Des dépendances nécessaires sont manquantes.")
    print("Installez toutes les dépendances avec: pip install -r requirements.txt")
    sys.exit(1)

# Importer WeasyPrint pour la conversion HTML vers PDF (DÉSACTIVÉ PAR DÉFAUT)
# Cette fonctionnalité est optionnelle et nécessite des dépendances système supplémentaires
PDF_AVAILABLE = False
try:
    # Pour activer WeasyPrint, décommentez la ligne ci-dessous
    # from weasyprint import HTML
    # Et changez PDF_AVAILABLE à True
    # PDF_AVAILABLE = True
    
    if not PDF_AVAILABLE:
        print("\n=== INFO: Génération PDF désactivée ===")
        print("Pour activer la génération PDF sur macOS:")
        print("1. Installez les dépendances système: brew install cairo pango gdk-pixbuf libffi")
        print("2. Installez WeasyPrint: pip install weasyprint==52.5")
        print("3. Modifiez ce fichier pour décommenter 'from weasyprint import HTML'")
        print("4. Changez PDF_AVAILABLE à True")
        print("================================\n")
except Exception as e:
    PDF_AVAILABLE = False
    print(f"\n=== ERREUR: Impossible d'importer WeasyPrint ===")
    print(f"Erreur: {str(e)}")
    print("La génération de PDF ne sera pas disponible.")
    print("Pour l'installer sur macOS:")
    print("1. Installez les dépendances système: brew install cairo pango gdk-pixbuf libffi")
    print("2. Installez WeasyPrint: pip install weasyprint==52.5")
    print("================================\n")


class MistralOCR:
    """Classe pour effectuer l'OCR avec l'API Mistral."""

    def __init__(self, api_key: str):
        """
        Initialise le client Mistral API.
        
        Args:
            api_key: Clé API Mistral
        """
        try:
            self.client = Mistral(api_key=api_key)
            # Tester immédiatement si la clé fonctionne
            models = self.client.list_models()
            print(f"Client Mistral initialisé avec succès. {len(models.data) if hasattr(models, 'data') else 0} modèles disponibles.")
            self.is_valid = True
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                print(f"ERREUR: Clé API invalide ou non autorisée: {error_msg}")
            else:
                print(f"ERREUR lors de l'initialisation du client Mistral: {error_msg}")
            self.is_valid = False
            # On crée quand même le client pour permettre d'autres opérations
            self.client = Mistral(api_key=api_key)
            
        self.model = "mistral-ocr-latest"

    def process_document_url(self, url: str, include_images: bool = True) -> Dict[str, Any]:
        """
        Traite un document à partir d'une URL.
        
        Args:
            url: URL du document
            include_images: Inclure les images en base64 dans la réponse
            
        Returns:
            Résultat de l'OCR
        """
        try:
            # Vérifier si le client est valide
            if not getattr(self, 'is_valid', True):
                return {"error": "Clé API Mistral invalide ou non autorisée. Veuillez vérifier votre clé API ou en créer une nouvelle sur https://console.mistral.ai/api-keys/"}
            
            # Utilisation de l'API OCR Mistral officielle
            response = self.client.ocr.process(
                model=self.model,
                document={
                    "type": "document_url",
                    "document_url": url
                },
                include_image_base64=include_images
            )
            
            # Conversion de la réponse en dictionnaire
            response_dict = response.model_dump()
            return response_dict
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                print(f"Erreur d'authentification lors du traitement de l'URL: {error_msg}")
                return {"error": "Clé API Mistral invalide ou non autorisée. Veuillez vérifier votre clé API ou en créer une nouvelle."}
            else:
                print(f"Erreur lors du traitement de l'URL: {error_msg}")
                return {"error": str(e)}

    def process_pdf_file(self, file_path: str, include_images: bool = True) -> Dict[str, Any]:
        """
        Traite un fichier PDF local.
        
        Args:
            file_path: Chemin vers le fichier PDF
            include_images: Inclure les images en base64 dans la réponse
            
        Returns:
            Résultat de l'OCR
        """
        try:
            # Vérifier si le client est valide
            if not getattr(self, 'is_valid', True):
                return {"error": "Clé API Mistral invalide ou non autorisée. Veuillez vérifier votre clé API ou en créer une nouvelle sur https://console.mistral.ai/api-keys/"}
            
            # Upload the PDF file
            with open(file_path, "rb") as f:
                uploaded_file = self.client.files.upload(
                    file={
                        "file_name": Path(file_path).name,
                        "content": f
                    },
                    purpose="ocr"
                )
            
            # Get a signed URL
            signed_url = self.client.files.get_signed_url(file_id=uploaded_file.id)
            
            # Process the document using the signed URL
            response = self.client.ocr.process(
                model=self.model,
                document={
                    "type": "document_url",
                    "document_url": signed_url.url
                },
                include_image_base64=include_images
            )
            
            # Conversion de la réponse en dictionnaire
            response_dict = response.model_dump()
            return response_dict
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                print(f"Erreur d'authentification lors du traitement du PDF: {error_msg}")
                return {"error": "Clé API Mistral invalide ou non autorisée. Veuillez vérifier votre clé API ou en créer une nouvelle."}
            else:
                print(f"Erreur lors du traitement du PDF: {error_msg}")
                return {"error": str(e)}

    def process_image_file(self, file_path: str, include_images: bool = False) -> Dict[str, Any]:
        """
        Traite un fichier image local.
        
        Args:
            file_path: Chemin vers le fichier image
            include_images: Inclure les images en base64 dans la réponse
            
        Returns:
            Résultat de l'OCR
        """
        try:
            # Vérifier si le client est valide
            if not getattr(self, 'is_valid', True):
                return {"error": "Clé API Mistral invalide ou non autorisée. Veuillez vérifier votre clé API ou en créer une nouvelle sur https://console.mistral.ai/api-keys/"}
            
            # Lecture et encodage de l'image en base64
            with open(file_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Détermination du type MIME en fonction de l'extension
            extension = Path(file_path).suffix.lower()
            mime_type = "image/jpeg"  # Par défaut
            if extension == ".png":
                mime_type = "image/png"
            elif extension == ".gif":
                mime_type = "image/gif"
            elif extension in [".jpg", ".jpeg"]:
                mime_type = "image/jpeg"
            
            # Création de l'URL data
            data_url = f"data:{mime_type};base64,{base64_image}"
            
            # Traitement de l'image avec l'API officielle
            response = self.client.ocr.process(
                model=self.model,
                document={
                    "type": "image_url",
                    "image_url": data_url
                },
                include_image_base64=include_images
            )
            
            # Conversion de la réponse en dictionnaire
            response_dict = response.model_dump()
            return response_dict
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                print(f"Erreur d'authentification lors du traitement de l'image: {error_msg}")
                return {"error": "Clé API Mistral invalide ou non autorisée. Veuillez vérifier votre clé API ou en créer une nouvelle."}
            else:
                print(f"Erreur lors du traitement de l'image: {error_msg}")
                return {"error": str(e)}

    def ask_question_about_document(self, document_url: str, question: str, model: str = "mistral-small-latest") -> str:
        """
        Pose une question sur un document en utilisant la compréhension documentaire de Mistral.
        
        Args:
            document_url: URL du document
            question: Question à poser sur le document
            model: Modèle à utiliser pour la compréhension documentaire
            
        Returns:
            Réponse à la question
        """
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": question
                        },
                        {
                            "type": "document_url",
                            "document_url": document_url
                        }
                    ]
                }
            ]
            
            chat_response = self.client.chat.complete(
                model=model,
                messages=messages
            )
            
            return chat_response.choices[0].message.content
        except Exception as e:
            print(f"Erreur lors de la question sur le document: {str(e)}")
            return f"Erreur: {str(e)}"

    def save_ocr_result(self, result: Dict[str, Any], output_file: str):
        """
        Sauvegarde le résultat de l'OCR dans un fichier.
        
        Args:
            result: Résultat de l'OCR
            output_file: Nom du fichier de sortie
        """
        try:
            # Si l'extension n'est pas spécifiée, on ajoute .json
            if not output_file.endswith(".json"):
                output_file += ".json"
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            print(f"Résultat OCR sauvegardé dans {output_file}")
            
            # Créer également un fichier markdown avec le contenu extrait
            md_file = output_file.replace(".json", ".md")
            with open(md_file, "w", encoding="utf-8") as f:
                for page in result.get("pages", []):
                    f.write(f"### Page {page.get('index')}\n\n")
                    f.write(page.get("markdown", "") + "\n\n")
            
            print(f"Contenu en markdown sauvegardé dans {md_file}")
            
            # Générer un fichier HTML avec un meilleur rendu
            self.generate_html_output(result, output_file.replace(".json", ".html"))
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du résultat: {str(e)}")
    
    def generate_html_output(self, result: Dict[str, Any], output_html_file: str):
        """
        Génère un fichier HTML à partir du résultat OCR avec un meilleur rendu visuel.
        
        Args:
            result: Résultat de l'OCR
            output_html_file: Chemin du fichier HTML de sortie
        """
        try:
            # Créer un dossier pour les images si nécessaire
            output_dir = os.path.dirname(output_html_file)
            images_dir = os.path.join(output_dir, "images_" + str(uuid.uuid4())[:8])
            os.makedirs(images_dir, exist_ok=True)
            
            # Préparer le contenu HTML
            html_content = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Résultat OCR Mistral</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        .page {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            padding: 40px;
            margin-bottom: 30px;
            position: relative;
        }
        .page-number {
            position: absolute;
            top: 10px;
            right: 10px;
            background-color: #007bff;
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 14px;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #2c3e50;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }
        h1 { font-size: 2.2em; }
        h2 { font-size: 1.8em; }
        h3 { font-size: 1.5em; }
        h4 { font-size: 1.3em; }
        h5 { font-size: 1.1em; }
        h6 { font-size: 1em; }
        img {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            margin: 15px 0;
        }
        pre {
            background-color: #f8f8f8;
            border-left: 4px solid #007bff;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
        }
        code {
            font-family: 'Courier New', Courier, monospace;
            background-color: #f0f0f0;
            padding: 2px 4px;
            border-radius: 3px;
        }
        blockquote {
            border-left: 4px solid #ccc;
            padding-left: 15px;
            color: #666;
            margin: 15px 0;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
            overflow-x: auto;
            display: block;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px 12px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            color: #666;
            font-size: 0.9em;
        }
        .math {
            font-family: 'Cambria Math', 'STIX', serif;
            font-style: italic;
        }
        @media print {
            body {
                background-color: white;
            }
            .page {
                box-shadow: none;
                margin-bottom: 0;
                page-break-after: always;
            }
        }
    </style>
    <script type="text/javascript" async
        src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/MathJax.js?config=TeX-MML-AM_CHTML">
    </script>
</head>
<body>
    <div class="header">
        <h1>Document OCR par Mistral AI</h1>
        <p>Traitement effectué le """ + time.strftime("%d/%m/%Y à %H:%M:%S") + """</p>
    </div>
"""
            
            # Traiter chaque page
            for page in result.get("pages", []):
                page_index = page.get("index", 0)
                page_markdown = page.get("markdown", "")
                
                # Améliorer le formatage des tableaux et des expressions mathématiques
                page_markdown = self._enhance_tables_and_math(page_markdown)
                
                # Extraire et sauvegarder les images
                for i, img in enumerate(page.get("images", [])):
                    if "base64" in img:
                        # Extraire l'image en base64
                        img_data = img["base64"]
                        img_format = "jpeg"  # Format par défaut
                        
                        # Déterminer le format de l'image
                        if img_data.startswith("data:image/"):
                            mime_type = img_data.split(";")[0].split(":")[1]
                            img_format = mime_type.split("/")[1]
                            img_data = img_data.split(",")[1]
                        
                        # Sauvegarder l'image
                        img_filename = f"page_{page_index}_img_{i}.{img_format}"
                        img_path = os.path.join(images_dir, img_filename)
                        
                        try:
                            with open(img_path, "wb") as img_file:
                                img_file.write(base64.b64decode(img_data))
                            
                            # Remplacer la référence dans le markdown
                            img_tag = f"![img-{i}.{img_format}](img-{i}.{img_format})"
                            relative_img_path = os.path.join(os.path.basename(images_dir), img_filename)
                            page_markdown = page_markdown.replace(img_tag, f"![Image {i}]({relative_img_path})")
                        except Exception as e:
                            print(f"Erreur lors de l'extraction de l'image {i} de la page {page_index}: {str(e)}")
                
                # Convertir le markdown en HTML
                html_page_content = markdown2.markdown(
                    page_markdown,
                    extras=[
                        "tables", "fenced-code-blocks", "footnotes",
                        "header-ids", "strike", "task_list"
                    ]
                )
                
                # Ajouter la page au document HTML
                html_content += f"""
    <div class="page">
        <div class="page-number">Page {page_index}</div>
        {html_page_content}
    </div>
"""
            
            # Finaliser le document HTML
            html_content += """
    <div class="footer">
        <p>Document généré par Mistral OCR</p>
    </div>
</body>
</html>
"""
            
            # Écrire le fichier HTML
            with open(output_html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            print(f"Rendu HTML amélioré sauvegardé dans {output_html_file}")
        except Exception as e:
            print(f"Erreur lors de la génération du fichier HTML: {str(e)}")
    
    def _enhance_tables_and_math(self, markdown_content: str) -> str:
        """
        Améliore le formatage des tableaux et des expressions mathématiques dans le contenu Markdown.
        
        Args:
            markdown_content: Contenu Markdown à améliorer
            
        Returns:
            Contenu Markdown amélioré
        """
        # Amélioration des tableaux
        markdown_content = self._enhance_tables(markdown_content)
        
        # Amélioration des expressions mathématiques
        markdown_content = self._enhance_math_expressions(markdown_content)
        
        return markdown_content
    
    def _enhance_tables(self, markdown_content: str) -> str:
        """
        Améliore le formatage des tableaux dans le contenu Markdown.
        
        Args:
            markdown_content: Contenu Markdown à améliorer
            
        Returns:
            Contenu Markdown avec des tableaux améliorés
        """
        # Recherche des tableaux dans le contenu Markdown
        table_pattern = r'(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n)+)'
        
        def format_table(match):
            table_content = match.group(1)
            
            # Diviser le tableau en lignes
            lines = table_content.strip().split('\n')
            
            # S'assurer que toutes les lignes ont le même nombre de colonnes
            if len(lines) >= 2:
                header_line = lines[0]
                separator_line = lines[1]
                
                # Compter le nombre de colonnes dans l'en-tête
                header_columns = header_line.count('|') - 1
                
                # Formater la ligne de séparation pour qu'elle ait le bon nombre de colonnes
                separator_parts = separator_line.split('|')
                separator_parts = [p for p in separator_parts if p]  # Supprimer les éléments vides
                
                # Créer une nouvelle ligne de séparation avec le bon nombre de colonnes
                new_separator = '|'
                for _ in range(header_columns):
                    new_separator += ' --- |'
                
                lines[1] = new_separator
                
                # Formater les lignes de données pour qu'elles aient le bon nombre de colonnes
                for i in range(2, len(lines)):
                    data_line = lines[i]
                    data_columns = data_line.count('|') - 1
                    
                    # Si la ligne a trop peu de colonnes, ajouter des colonnes vides
                    if data_columns < header_columns:
                        missing_columns = header_columns - data_columns
                        lines[i] = data_line.rstrip('|\n') + '|' + ' |' * missing_columns
                    
                    # Si la ligne a trop de colonnes, supprimer les colonnes excédentaires
                    elif data_columns > header_columns:
                        parts = data_line.split('|')
                        lines[i] = '|'.join(parts[:header_columns+2]) + '|'  # +2 pour inclure les éléments vides au début et à la fin
            
            # Reconstruire le tableau
            return '\n'.join(lines) + '\n'
        
        # Remplacer les tableaux par leur version améliorée
        enhanced_content = re.sub(table_pattern, format_table, markdown_content, flags=re.DOTALL)
        
        return enhanced_content
    
    def _enhance_math_expressions(self, markdown_content: str) -> str:
        """
        Améliore le formatage des expressions mathématiques dans le contenu Markdown.
        
        Args:
            markdown_content: Contenu Markdown à améliorer
            
        Returns:
            Contenu Markdown avec des expressions mathématiques améliorées
        """
        # Fonction pour nettoyer les expressions mathématiques
        def clean_math_expr(expr):
            # Supprimer les espaces inutiles
            expr = expr.strip()
            
            # Corriger les problèmes courants dans les expressions LaTeX
            replacements = {
                # Fractions
                r'\\frac\s+([^ {}]+)\s+([^ {}]+)': r'\\frac{\1}{\2}',
                r'\\frac\s*{([^}]*)}\s*{([^}]*)}': r'\\frac{\1}{\2}',
                
                # Indices et exposants
                r'_([a-zA-Z0-9])([^a-zA-Z0-9])': r'_{\1}\2',
                r'\^([a-zA-Z0-9])([^a-zA-Z0-9])': r'^{\1}\2',
                
                # Opérateurs avec limites
                r'\\sum\s*_([^ {}]+)': r'\\sum_{\1}',
                r'\\prod\s*_([^ {}]+)': r'\\prod_{\1}',
                r'\\int\s*_([^ {}]+)': r'\\int_{\1}',
                r'\\lim\s*_([^ {}]+)': r'\\lim_{\1}',
                
                # Espaces dans les commandes
                r'\\([a-zA-Z]+)\s+': r'\\\1 ',
                
                # Accolades manquantes
                r'\\sqrt\s+([^ {}]+)': r'\\sqrt{\1}',
                
                # Symboles spéciaux
                r'\\mathbb\s*{([^}]*)}': r'\\mathbb{\1}',
                r'\\mathcal\s*{([^}]*)}': r'\\mathcal{\1}',
                r'\\mathrm\s*{([^}]*)}': r'\\mathrm{\1}',
                r'\\mathbf\s*{([^}]*)}': r'\\mathbf{\1}',
                
                # Environnements
                r'\\begin\s*{([^}]*)}': r'\\begin{\1}',
                r'\\end\s*{([^}]*)}': r'\\end{\1}',
                
                # Corriger les problèmes d'espacement
                r'\s*\\,\s*': r'\\, ',
                r'\s*\\;\s*': r'\\; ',
                r'\s*\\quad\s*': r'\\quad ',
                r'\s*\\qquad\s*': r'\\qquad ',
                
                # Corriger les problèmes de délimiteurs
                r'\\left\s*([^\\])': r'\\left\1',
                r'\\right\s*([^\\])': r'\\right\1',
                
                # Corriger les problèmes de matrices
                r'\\begin\s*{matrix}': r'\\begin{matrix}',
                r'\\end\s*{matrix}': r'\\end{matrix}',
                r'\\begin\s*{pmatrix}': r'\\begin{pmatrix}',
                r'\\end\s*{pmatrix}': r'\\end{pmatrix}',
                r'\\begin\s*{bmatrix}': r'\\begin{bmatrix}',
                r'\\end\s*{bmatrix}': r'\\end{bmatrix}',
                
                # Corriger les problèmes de symboles
                r'\\infty\s': r'\\infty ',
                r'\\alpha\s': r'\\alpha ',
                r'\\beta\s': r'\\beta ',
                r'\\gamma\s': r'\\gamma ',
                r'\\delta\s': r'\\delta ',
                r'\\epsilon\s': r'\\epsilon ',
                r'\\zeta\s': r'\\zeta ',
                r'\\eta\s': r'\\eta ',
                r'\\theta\s': r'\\theta ',
                r'\\iota\s': r'\\iota ',
                r'\\kappa\s': r'\\kappa ',
                r'\\lambda\s': r'\\lambda ',
                r'\\mu\s': r'\\mu ',
                r'\\nu\s': r'\\nu ',
                r'\\xi\s': r'\\xi ',
                r'\\pi\s': r'\\pi ',
                r'\\rho\s': r'\\rho ',
                r'\\sigma\s': r'\\sigma ',
                r'\\tau\s': r'\\tau ',
                r'\\upsilon\s': r'\\upsilon ',
                r'\\phi\s': r'\\phi ',
                r'\\chi\s': r'\\chi ',
                r'\\psi\s': r'\\psi ',
                r'\\omega\s': r'\\omega ',
            }
            
            # Appliquer les remplacements
            for pattern, replacement in replacements.items():
                expr = re.sub(pattern, replacement, expr)
            
            return expr
        
        # Remplacer les expressions mathématiques en ligne (entre $ et $)
        def replace_inline_math(match):
            math_expr = match.group(1)
            cleaned_expr = clean_math_expr(math_expr)
            return f'$${cleaned_expr}$$'
        
        inline_math_pattern = r'\$([^$\n]+?)\$'
        enhanced_content = re.sub(inline_math_pattern, replace_inline_math, markdown_content)
        
        # Remplacer les expressions mathématiques en bloc (entre $$ et $$)
        def replace_block_math(match):
            math_expr = match.group(1)
            cleaned_expr = clean_math_expr(math_expr)
            return f'$$\n{cleaned_expr}\n$$'
        
        block_math_pattern = r'\$\$([^$]+?)\$\$'
        enhanced_content = re.sub(block_math_pattern, replace_block_math, enhanced_content)
        
        return enhanced_content


def main():
    parser = argparse.ArgumentParser(description="Effectuer l'OCR sur des documents avec l'API Mistral")
    
    # Options obligatoires
    parser.add_argument("--api-key", type=str, help="Clé API Mistral (ou définir la variable d'environnement MISTRAL_API_KEY)")
    
    # Type d'entrée (un seul requis)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--url", type=str, help="URL d'un document à traiter")
    input_group.add_argument("--pdf", type=str, help="Chemin vers un fichier PDF local à traiter")
    input_group.add_argument("--image", type=str, help="Chemin vers un fichier image local à traiter")
    
    # Options additionnelles
    parser.add_argument("--output", type=str, default="ocr_result.json", help="Nom du fichier de sortie (par défaut: ocr_result.json)")
    parser.add_argument("--no-images", action="store_true", help="Ne pas inclure les images en base64 dans le résultat")
    parser.add_argument("--question", type=str, help="Poser une question sur le document (document understanding)")
    parser.add_argument("--format", choices=["json", "md", "html", "pdf", "all"], default="all", 
                        help="Format de sortie: json, md (markdown), html, pdf ou all (tous les formats)")
    
    args = parser.parse_args()
    
    # Récupérer la clé API de l'argument ou de la variable d'environnement
    api_key = args.api_key or os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        print("Erreur: La clé API Mistral est requise. Utilisez --api-key ou définissez la variable d'environnement MISTRAL_API_KEY.")
        sys.exit(1)
    
    # Créer l'instance MistralOCR
    ocr = MistralOCR(api_key)
    
    # Traiter le document selon le type d'entrée
    if args.url:
        print(f"Traitement de l'URL: {args.url}")
        result = ocr.process_document_url(args.url, not args.no_images)
    elif args.pdf:
        print(f"Traitement du fichier PDF: {args.pdf}")
        result = ocr.process_pdf_file(args.pdf, not args.no_images)
    elif args.image:
        print(f"Traitement de l'image: {args.image}")
        result = ocr.process_image_file(args.image, not args.no_images)
    
    # Si une erreur s'est produite
    if "error" in result:
        print(f"Erreur lors du traitement: {result['error']}")
        sys.exit(1)
    
    # Sauvegarder le résultat selon le format demandé
    base_output = args.output
    if base_output.endswith(".json") or base_output.endswith(".md") or base_output.endswith(".html") or base_output.endswith(".pdf"):
        base_output = os.path.splitext(base_output)[0]
    
    if args.format == "json" or args.format == "all":
        ocr.save_ocr_result(result, base_output + ".json")
    
    if args.format == "md" or args.format == "all":
        # Le fichier markdown est généré dans save_ocr_result
        if args.format != "all":
            md_file = base_output + ".md"
            with open(md_file, "w", encoding="utf-8") as f:
                for page in result.get("pages", []):
                    f.write(f"### Page {page.get('index')}\n\n")
                    f.write(page.get("markdown", "") + "\n\n")
            print(f"Contenu en markdown sauvegardé dans {md_file}")
    
    if args.format == "html" or args.format == "all":
        html_file = base_output + ".html"
        if args.format != "all":
            ocr.generate_html_output(result, html_file)
        else:
            # Si on génère tous les formats, on a besoin du fichier HTML pour le PDF
            ocr.generate_html_output(result, html_file)
    
    if (args.format == "pdf" or args.format == "all") and PDF_AVAILABLE:
        pdf_file = base_output + ".pdf"
        html_file = base_output + ".html"
        
        # S'assurer que le fichier HTML existe
        if not os.path.exists(html_file) and args.format == "pdf":
            ocr.generate_html_output(result, html_file)
        
        # Convertir HTML en PDF
        try:
            # Utiliser le bon format pour WeasyPrint v60.2
            HTML(filename=html_file).write_pdf(pdf_file)
            print(f"Document PDF sauvegardé dans {pdf_file}")
        except Exception as e:
            print(f"Erreur lors de la génération du PDF: {str(e)}")
    elif args.format == "pdf" and not PDF_AVAILABLE:
        print("L'exportation PDF n'est pas disponible car WeasyPrint n'est pas installé.")
        print("Pour l'installer: pip install weasyprint")
    
    # Si une question est posée
    if args.question:
        print(f"\nQuestion: {args.question}")
        document_url = args.url
        if args.pdf or args.image:
            # Pour les questions sur des fichiers locaux, il faudrait d'abord les télécharger sur un serveur
            print("La fonctionnalité de question n'est disponible que pour les URL de documents.")
            sys.exit(1)
        
        answer = ocr.ask_question_about_document(document_url, args.question)
        print(f"\nRéponse: {answer}")


if __name__ == "__main__":
    main() 