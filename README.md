# Mistral OCR

Une application d'extraction de texte intelligente utilisant l'API Mistral AI pour l'OCR (Reconnaissance Optique de Caractères).

## Fonctionnalités

- Extraction de texte à partir de fichiers PDF et d'images
- Traitement de documents via URL
- Exportation des résultats en plusieurs formats (JSON, Markdown, HTML)
- Interface web conviviale
- Utilisation de l'IA Mistral pour une reconnaissance précise

## Installation

### Prérequis

- Python 3.8 ou supérieur
- Une clé API Mistral (disponible sur [https://console.mistral.ai/](https://console.mistral.ai/))

### Installation standard

1. Clonez ce dépôt :
   ```bash
   git clone https://github.com/Camcamousse/mistral-ocr.git
   cd mistral-ocr
   ```

2. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

3. Configurez votre clé API Mistral :
   - Créez un fichier `.env` à la racine du projet
   - Ajoutez votre clé API : `MISTRAL_API_KEY=votre_clé_api`

### Fonctionnalité PDF (optionnelle)

Par défaut, l'exportation PDF est désactivée car elle nécessite des dépendances système supplémentaires.

Pour activer l'exportation PDF sur macOS :

1. Installez les dépendances système :
   ```bash
   brew install cairo pango gdk-pixbuf libffi
   ```

2. Installez WeasyPrint :
   ```bash
   pip install weasyprint==52.5
   ```

3. Modifiez le fichier `mistral_ocr.py` pour activer WeasyPrint :
   - Décommentez les lignes d'import WeasyPrint
   - Changez `PDF_AVAILABLE = False` en `PDF_AVAILABLE = True`

## Utilisation

### Interface Web

1. Lancez l'application web :
   ```bash
   cd mistral_ocr_web
   python app.py
   ```

2. Ouvrez votre navigateur à l'adresse [http://127.0.0.1:5000](http://127.0.0.1:5000)

3. Configurez votre clé API Mistral si ce n'est pas déjà fait

4. Téléchargez un fichier ou fournissez une URL pour commencer l'extraction

### Ligne de commande

```bash
python mistral_ocr.py --file chemin/vers/document.pdf --output-dir ./resultats --format json,md,html
```

Options disponibles :
- `--file` : Chemin vers un fichier PDF ou image
- `--url` : URL d'un document accessible publiquement
- `--output-dir` : Dossier de sortie pour les résultats
- `--format` : Formats de sortie (json, md, html, pdf)
- `--api-key` : Clé API Mistral (alternative au fichier .env)

## Dépannage

### Problèmes avec WeasyPrint

Si vous rencontrez des erreurs liées à WeasyPrint ou Cairo :

1. Vérifiez que vous avez correctement installé les dépendances système
2. Utilisez l'application sans la fonctionnalité PDF
3. Consultez la [documentation officielle de WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) pour des instructions spécifiques à votre système d'exploitation

### Erreurs d'API

- **Erreur 401** : Vérifiez que votre clé API est valide
- **Erreur 520** : Les serveurs Mistral peuvent être temporairement indisponibles, réessayez plus tard

## Licence

Ce projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails.

## Remerciements

- [Mistral AI](https://mistral.ai/) pour leur API OCR puissante
- [Flask](https://flask.palletsprojects.com/) pour le framework web
- [WeasyPrint](https://weasyprint.org/) pour la génération de PDF (fonctionnalité optionnelle)