#!/bin/bash

# Script pour redémarrer l'application Mistral OCR

# Installer les dépendances
echo "Installation des dépendances..."
pip install -r requirements.txt

# Vérifier si un processus Flask est en cours d'exécution
echo "Vérification des processus existants..."
PID=$(ps aux | grep "python app.py" | grep -v grep | awk '{print $2}')

if [ ! -z "$PID" ]; then
    echo "Arrêt du processus existant (PID: $PID)..."
    kill $PID
    sleep 2
fi

# Démarrer l'application en arrière-plan
echo "Démarrage de l'application..."
cd mistral_ocr_web
nohup python app.py > ../app.log 2>&1 &

echo "Application redémarrée avec succès!"
echo "Vous pouvez accéder à l'application à l'adresse: http://127.0.0.1:5000"