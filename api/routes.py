import os
import json
import subprocess
import sys
import logging
from flask import request, jsonify
from threading import Thread
import asyncio

logger = logging.getLogger(__name__)

def register_routes(app):
    @app.route("/health", methods=["GET"])
    def health_check():
        """Endpoint de vérification de santé pour Railway"""
        return jsonify({"status": "ok", "message": "L'API d'agent téléphonique est opérationnelle"})
    
    @app.route("/api/call", methods=["POST"])
    def make_call():
        """Endpoint pour lancer un appel sortant"""
        data = request.json
        if not data or "phone" not in data:
            return jsonify({"error": "Numéro de téléphone manquant"}), 400
        
        phone_number = data["phone"]
        
        try:
            # Chemin vers le script Python
            script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "setup_dispatch.py")
            
            # Exécuter le script dans un processus séparé
            process_env = os.environ.copy()
            process = subprocess.Popen(
                [sys.executable, script_path, "--phone", phone_number],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=process_env  # Transmettre toutes les variables d'environnement
            )
            
            stdout, stderr = process.communicate()
            
            # Analyser la sortie pour extraire les informations de l'appel
            room_match = None
            dispatch_id = None
            
            for line in stdout.split("\n"):
                if "Room:" in line:
                    room_match = line.split("Room:")[1].strip()
                elif "ID:" in line:
                    dispatch_id = line.split("ID:")[1].strip()
            
            if process.returncode != 0:
                logger.error(f"Erreur lors de l'exécution du script: {stderr}")
                return jsonify({
                    "success": False,
                    "error": "Erreur lors de l'initiation de l'appel",
                    "details": stderr
                }), 500
            
            return jsonify({
                "success": True,
                "roomName": room_match or "unknown",
                "dispatchId": dispatch_id or "unknown",
                "message": "Appel initié avec succès"
            })
            
        except Exception as e:
            logger.exception("Erreur lors de l'appel")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/trunk/setup", methods=["POST"])
    def setup_trunk():
        """Endpoint pour configurer le trunk SIP"""
        try:
            # Chemin vers le script Python
            script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "setup_trunk.py")
            
            # Exécuter le script avec l'option Twilio
            process_env = os.environ.copy()
            process = subprocess.Popen(
                [sys.executable, script_path, "--twilio"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=process_env  # Transmettre toutes les variables d'environnement
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Erreur lors de la configuration du trunk: {stderr}")
                return jsonify({
                    "success": False,
                    "error": "Erreur lors de la configuration du trunk",
                    "details": stderr
                }), 500
            
            # Extraire l'ID du trunk
            trunk_id = None
            for line in stdout.split("\n"):
                if "Trunk SIP sortant créé avec succès: ID =" in line:
                    trunk_id = line.split("ID =")[1].strip()
            
            return jsonify({
                "success": True,
                "trunkId": trunk_id,
                "message": "Trunk SIP configuré avec succès"
            })
            
        except Exception as e:
            logger.exception("Erreur lors de la configuration du trunk")
            return jsonify({"error": str(e)}), 500
