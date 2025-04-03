from flask import Flask, request, jsonify
from flask_cors import CORS
from .routes import register_routes
import os
import sys
import asyncio
import subprocess
from threading import Thread
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialisation de l'application Flask
app = Flask(__name__)
CORS(app)

# Import des routes
from routes import register_routes

# Enregistrement des routes
register_routes(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
