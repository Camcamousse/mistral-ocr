#!/bin/bash

# Installer les dépendances requises
pip install -r requirements.txt

# Redémarrer le serveur
echo "Redémarrage du serveur..."
pkill -f "python app.py" || true
python app.py