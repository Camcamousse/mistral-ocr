# Mistral OCR

Application web pour la reconnaissance optique de caractères (OCR) utilisant l'API Mistral AI.

## Fonctionnalités

- Reconnaissance de texte à partir d'images téléchargées ou d'URL d'images
- Interface utilisateur moderne et intuitive
- Visualisation des résultats en format HTML
- Prise en charge de plusieurs langues

## Prérequis

- Python 3.8 ou supérieur
- Une clé API Mistral AI (obtenue sur [console.mistral.ai](https://console.mistral.ai/))

## Installation

1. Clonez ce dépôt :
```bash
git clone https://github.com/Camcamousse/mistral-ocr.git
cd mistral-ocr
```

2. Installez les dépendances :
```bash
pip install -r requirements.txt
```

3. Démarrez l'application :
```bash
cd mistral_ocr_web
python app.py
```

4. Accédez à l'application dans votre navigateur à l'adresse `http://127.0.0.1:5000`

## Configuration

Lors de la première utilisation, vous devrez configurer votre clé API Mistral. Suivez les instructions dans l'application pour obtenir et configurer votre clé.

## Structure du projet

- `mistral_ocr.py` : Script principal pour la reconnaissance OCR en ligne de commande
- `mistral_ocr_web/` : Application web Flask pour l'OCR
  - `app.py` : Serveur Flask
  - `templates/` : Templates HTML
  - `static/` : Fichiers statiques (CSS, JavaScript, images)

## Licence

Ce projet est sous licence MIT.