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
from mistralai import Mistral

# Imports pour la conversion Markdown vers HTML
import markdown2
import re
import shutil
import uuid
import time

# Importer WeasyPrint pour la conversion HTML vers PDF
try:
    # Désactiver WeasyPrint par défaut pour éviter les problèmes de dépendances
    # from weasyprint import HTML
    # Définir une variable pour indiquer que la fonctionnalité PDF est disponible
    PDF_AVAILABLE = False
    print("WeasyPrint est désactivé par défaut. Pour l'activer, décommentez la ligne d'import dans mistral_ocr.py")
except ImportError:
    # Si WeasyPrint n'est pas installé, désactiver la fonctionnalité PDF
    PDF_AVAILABLE = False
    print("WeasyPrint n'est pas installé. L'exportation PDF ne sera pas disponible.")
    print("Pour l'installer sur macOS: brew install cairo pango gdk-pixbuf libffi")
    print("Puis: pip install weasyprint==52.5")


class MistralOCR:
    """Classe pour effectuer l'OCR avec l'API Mistral."""

    def __init__(self, api_key: str):
        """
        Initialise le client Mistral API.
        
        Args:
            api_key: Clé API Mistral
        """
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
            print(f"Erreur lors du traitement de l'URL: {str(e)}")
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
            print(f"Erreur lors du traitement du PDF: {str(e)}")
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
            print(f"Erreur lors du traitement de l'image: {str(e)}")
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
            
            # Générer un fichier PDF si WeasyPrint est disponible
            if PDF_AVAILABLE:
                html_file = output_file.replace(".json", ".html")
                pdf_file = output_file.replace(".json", ".pdf")
                
                # S'assurer que le fichier HTML existe
                if os.path.exists(html_file):
                    try:
                        # Générer le PDF à partir du HTML
                        from weasyprint import HTML
                        HTML(filename=html_file).write_pdf(pdf_file)
                        print(f"PDF généré avec succès: {pdf_file}")
                    except Exception as e:
                        print(f"Erreur lors de la génération du PDF: {str(e)}")
                else:
                    print(f"Le fichier HTML {html_file} n'existe pas, impossible de générer le PDF")
            else:
                print("WeasyPrint n'est pas installé. L'exportation PDF n'est pas disponible.")
                print("Pour l'installer sur macOS: brew install cairo pango gdk-pixbuf libffi")
                print("Puis: pip install weasyprint==52.5")
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
            # Créer un dossier pour les ressources si nécessaire
            output_dir = os.path.dirname(output_html_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Préparer le contenu HTML
            html_content = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Résultat OCR</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #2980b9;
            margin-top: 30px;
        }
        h3 {
            color: #3498db;
        }
        img {
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 5px;
            margin: 10px 0;
        }
        pre {
            background-color: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            overflow-x: auto;
        }
        code {
            font-family: Consolas, Monaco, 'Andale Mono', monospace;
            background-color: #f8f9fa;
            padding: 2px 4px;
            border-radius: 3px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
        .page-container {
            margin-bottom: 40px;
            border: 1px solid #eee;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .page-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .page-number {
            font-weight: bold;
            color: #7f8c8d;
        }
        .metadata {
            background-color: #f8f9fa;
            border-left: 3px solid #3498db;
            padding: 10px 15px;
            margin: 20px 0;
            font-size: 0.9em;
        }
        .metadata p {
            margin: 5px 0;
        }
        .image-container {
            text-align: center;
            margin: 20px 0;
        }
        .footer {
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            text-align: center;
            font-size: 0.8em;
            color: #7f8c8d;
        }
        /* Styles pour les tableaux dans le markdown */
        .markdown-table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        .markdown-table th, .markdown-table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        .markdown-table th {
            background-color: #f2f2f2;
        }
        /* Styles pour les formules mathématiques */
        .math {
            font-family: 'Times New Roman', serif;
            font-style: italic;
        }
    </style>
</head>
<body>
    <h1>Résultat de la reconnaissance de texte (OCR)</h1>
    
    <div class="metadata">
        <p><strong>Document traité le:</strong> """ + time.strftime("%d/%m/%Y à %H:%M:%S") + """</p>
        <p><strong>Nombre de pages:</strong> """ + str(len(result.get("pages", []))) + """</p>
        <p><strong>Modèle utilisé:</strong> """ + result.get("model", "Non spécifié") + """</p>
    </div>
    
    <div id="content">
"""
            
            # Ajouter chaque page
            for page in result.get("pages", []):
                page_index = page.get("index", 0)
                page_markdown = page.get("markdown", "")
                
                # Améliorer le formatage des tableaux et des expressions mathématiques
                page_markdown = self._enhance_tables_and_math(page_markdown)
                
                # Convertir le markdown en HTML
                page_html = markdown2.markdown(page_markdown, extras=["tables", "fenced-code-blocks"])
                
                html_content += f"""
    <div class="page-container" id="page-{page_index}">
        <div class="page-header">
            <h2>Page {page_index}</h2>
            <span class="page-number">{page_index}/{len(result.get("pages", []))}</span>
        </div>
        
        <div class="page-content">
            {page_html}
        </div>
    </div>
"""
            
            # Fermer le HTML
            html_content += """
    </div>
    
    <div class="footer">
        <p>Document généré par Mistral OCR</p>
    </div>
</body>
</html>
"""
            
            # Écrire le fichier HTML
            with open(output_html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            print(f"Fichier HTML généré avec succès: {output_html_file}")
            
        except Exception as e:
            print(f"Erreur lors de la génération du fichier HTML: {str(e)}")
    
    def _enhance_tables_and_math(self, markdown_text: str) -> str:
        """
        Améliore le formatage des tableaux et des expressions mathématiques dans le markdown.
        
        Args:
            markdown_text: Texte markdown à améliorer
            
        Returns:
            Texte markdown amélioré
        """
        # Améliorer les tableaux
        # Rechercher les lignes qui ressemblent à des tableaux (contenant plusieurs |)
        lines = markdown_text.split('\n')
        in_table = False
        table_start_index = -1
        
        for i, line in enumerate(lines):
            pipe_count = line.count('|')
            
            # Si la ligne contient au moins 3 pipes et n'est pas déjà dans un tableau formaté
            if pipe_count >= 3 and not in_table and not line.strip().startswith('|'):
                in_table = True
                table_start_index = i
                # Formater cette ligne comme début de tableau
                lines[i] = '|' + line.replace('|', '|').strip() + '|'
            
            # Si nous sommes dans un tableau et la ligne continue le motif
            elif in_table and pipe_count >= 3:
                # Formater cette ligne comme continuation de tableau
                lines[i] = '|' + line.replace('|', '|').strip() + '|'
                
                # Si c'est la deuxième ligne du tableau, ajouter une ligne de séparation
                if i == table_start_index + 1:
                    # Compter le nombre de colonnes
                    columns = lines[i].count('|') - 1
                    separator_line = '|' + '---|' * columns
                    # Insérer la ligne de séparation
                    lines.insert(i, separator_line)
                    i += 1  # Ajuster l'index après l'insertion
            
            # Si nous étions dans un tableau mais la ligne ne correspond plus au motif
            elif in_table and pipe_count < 3:
                in_table = False
                table_start_index = -1
        
        # Améliorer les expressions mathématiques
        # Rechercher les motifs qui ressemblent à des formules mathématiques
        enhanced_text = '\n'.join(lines)
        
        # Remplacer les expressions entre $$ par des balises <div class="math">
        enhanced_text = re.sub(r'\$\$(.*?)\$\$', r'<div class="math">\1</div>', enhanced_text)
        
        # Remplacer les expressions entre $ par des balises <span class="math">
        enhanced_text = re.sub(r'\$(.*?)\$', r'<span class="math">\1</span>', enhanced_text)
        
        return enhanced_text


def main():
    """Fonction principale du script."""
    parser = argparse.ArgumentParser(description="Mistral OCR - Reconnaissance de texte dans des documents")
    
    # Options pour les sources de documents
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--url", help="URL d'un document à traiter")
    source_group.add_argument("--pdf", help="Chemin vers un fichier PDF local à traiter")
    source_group.add_argument("--image", help="Chemin vers un fichier image local à traiter")
    
    # Options générales
    parser.add_argument("--api-key", help="Clé API Mistral (ou définir la variable d'environnement MISTRAL_API_KEY)")
    parser.add_argument("--output", default="ocr_result", help="Nom du fichier de sortie (par défaut: ocr_result.json)")
    parser.add_argument("--no-images", action="store_true", help="Ne pas inclure les images en base64 dans le résultat")
    parser.add_argument("--question", help="Poser une question sur le document (document understanding, URL uniquement)")
    
    args = parser.parse_args()
    
    # Récupérer la clé API
    api_key = args.api_key or os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        print("Erreur: Aucune clé API Mistral fournie. Utilisez --api-key ou définissez la variable d'environnement MISTRAL_API_KEY.")
        sys.exit(1)
    
    # Créer l'instance MistralOCR
    ocr = MistralOCR(api_key)
    
    # Traiter selon le type d'entrée
    if args.url:
        if args.question:
            # Mode question sur document
            answer = ocr.ask_question_about_document(args.url, args.question)
            print(f"\nQuestion: {args.question}\n\nRéponse: {answer}")
        else:
            # Mode OCR normal
            result = ocr.process_document_url(args.url, not args.no_images)
            ocr.save_ocr_result(result, args.output)
    elif args.pdf:
        result = ocr.process_pdf_file(args.pdf, not args.no_images)
        ocr.save_ocr_result(result, args.output)
    elif args.image:
        result = ocr.process_image_file(args.image, not args.no_images)
        ocr.save_ocr_result(result, args.output)


if __name__ == "__main__":
    main()