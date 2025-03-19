#!/bin/bash

# Script pour redémarrer l'application Mistral OCR

echo "==================================================================="
echo "        REDÉMARRAGE DE L'APPLICATION MISTRAL OCR                   "
echo "==================================================================="

# Vérifier si Python est installé
if ! command -v python &> /dev/null; then
    echo "ERREUR: Python n'est pas installé ou n'est pas dans le PATH."
    echo "Veuillez installer Python 3.8 ou supérieur."
    exit 1
fi

# Vérifier la version de Python
PYTHON_VERSION=$(python --version 2>&1 | cut -d' ' -f2)
echo "Version Python détectée: $PYTHON_VERSION"

# Installer les dépendances
echo "Installation des dépendances..."
pip install -r requirements.txt

# Vérifier si l'installation a réussi
if [ $? -ne 0 ]; then
    echo "ERREUR: L'installation des dépendances a échoué."
    echo "Veuillez vérifier les erreurs ci-dessus et résoudre les problèmes d'installation."
    exit 1
fi

# Vérifier si un processus Flask est en cours d'exécution
echo "Vérification des processus existants..."
PID=$(ps aux | grep "python mistral_ocr_web/app.py" | grep -v grep | awk '{print $2}')

if [ ! -z "$PID" ]; then
    echo "Arrêt du processus existant (PID: $PID)..."
    kill $PID
    sleep 2
    
    # Vérifier si le processus a bien été arrêté
    if ps -p $PID > /dev/null; then
        echo "ATTENTION: Le processus n'a pas pu être arrêté proprement."
        echo "Tentative d'arrêt forcé..."
        kill -9 $PID
        sleep 1
    fi
fi

# Créer le dossier uploads s'il n'existe pas
mkdir -p mistral_ocr_web/uploads
echo "Dossier uploads vérifié."

# Démarrer l'application en arrière-plan
echo "Démarrage de l'application..."
python mistral_ocr_web/app.py > app.log 2>&1 &

# Vérifier si l'application a démarré
if [ $? -ne 0 ]; then
    echo "ERREUR: L'application n'a pas pu démarrer."
    echo "Veuillez consulter le fichier app.log pour plus de détails."
    exit 1
fi

echo "Application démarrée avec succès!"
echo "Vous pouvez accéder à l'application à l'adresse: http://127.0.0.1:5001"
echo "Les logs sont disponibles dans le fichier: app.log"
echo "===================================================================" 