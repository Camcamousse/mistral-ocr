#!/bin/bash

# Script pour redémarrer l'application Mistral OCR

echo "==================================================================="
echo "        REDÉMARRAGE DE L'APPLICATION MISTRAL OCR                   "
echo "==================================================================="

# Vérifier si Python est installé
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "ERREUR: Python n'est pas installé ou n'est pas dans le PATH."
    echo "Veuillez installer Python 3.8 ou supérieur."
    exit 1
fi

# Déterminer quelle commande Python utiliser
PYTHON_CMD="python"
if ! command -v python &> /dev/null; then
    PYTHON_CMD="python3"
fi

# Vérifier la version de Python
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
echo "Version Python détectée: $PYTHON_VERSION ($PYTHON_CMD)"

# Installer les dépendances
echo "Installation des dépendances..."
$PYTHON_CMD -m pip install -r requirements.txt

# Vérifier si l'installation a réussi
if [ $? -ne 0 ]; then
    echo "ERREUR: L'installation des dépendances a échoué."
    echo "Veuillez vérifier les erreurs ci-dessus et résoudre les problèmes d'installation."
    exit 1
fi

# Vérifier si un processus Flask est en cours d'exécution
echo "Vérification des processus existants..."
PID=$(ps aux | grep "python.*app.py" | grep -v grep | awk '{print $2}')

if [ ! -z "$PID" ]; then
    echo "Arrêt du processus existant (PID: $PID)..."
    kill $PID 2>/dev/null || true
    sleep 2
    
    # Vérifier si le processus a bien été arrêté
    if ps -p $PID > /dev/null 2>&1; then
        echo "ATTENTION: Le processus n'a pas pu être arrêté proprement."
        echo "Tentative d'arrêt forcé..."
        kill -9 $PID 2>/dev/null || true
        sleep 1
    fi
fi

# Créer le dossier uploads s'il n'existe pas
mkdir -p mistral_ocr_web/uploads
echo "Dossier uploads vérifié."

# Démarrer l'application en arrière-plan
echo "Démarrage de l'application..."
cd mistral_ocr_web || exit 1
$PYTHON_CMD app.py > ../app.log 2>&1 &
APP_PID=$!
cd ..

# Vérifier si l'application a démarré
sleep 2
if ! ps -p $APP_PID > /dev/null 2>&1; then
    echo "ERREUR: L'application n'a pas pu démarrer."
    echo "Veuillez consulter le fichier app.log pour plus de détails:"
    echo "-----------------------------------------------------------"
    tail -n 20 app.log
    echo "-----------------------------------------------------------"
    exit 1
fi

echo "Application démarrée avec succès! (PID: $APP_PID)"
echo "Vous pouvez accéder à l'application à l'adresse: http://127.0.0.1:5000"
echo "Les logs sont disponibles dans le fichier: app.log"
echo "==================================================================="