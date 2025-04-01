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
    
    @app.route("/api/twilio/test", methods=["GET"])
    def test_twilio_env():
        """Endpoint pour tester les variables d'environnement Twilio"""
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN") 
        phone_number = os.environ.get("TWILIO_PHONE_NUMBER")
        
        return jsonify({
            "variables_present": {
                "TWILIO_ACCOUNT_SID": bool(account_sid),
                "TWILIO_AUTH_TOKEN": bool(auth_token),
                "TWILIO_PHONE_NUMBER": bool(phone_number)
            },
            "account_sid_prefix": account_sid[:4] + "..." if account_sid else None,
            "all_variables_present": all([account_sid, auth_token, phone_number])
        })
    
    @app.route("/api/twilio/verify", methods=["GET"])
    def verify_twilio():
        """Endpoint pour vérifier la connexion à Twilio"""
        try:
            from twilio.rest import Client
            
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            
            if not account_sid or not auth_token:
                return jsonify({
                    "success": False,
                    "error": "Identifiants Twilio manquants"
                })
            
            # Tenter de se connecter à Twilio et récupérer les informations du compte
            client = Client(account_sid, auth_token)
            account = client.api.accounts(account_sid).fetch()
            
            return jsonify({
                "success": True,
                "account_status": account.status,
                "account_name": account.friendly_name,
                "created_at": str(account.date_created)
            })
        except Exception as e:
            import traceback
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            })

    @app.route("/api/livekit/test", methods=["GET"])
    def test_livekit():
        """Endpoint pour tester la connexion à LiveKit"""
        try:
            import asyncio
            from livekit import api
            
            async def test_livekit_connection():
                livekit_api = api.LiveKitAPI()
                try:
                    # Tester la connexion en listant les rooms
                    response = await livekit_api.room.list_rooms(api.ListRoomsRequest())
                    return {
                        "success": True,
                        "connection": "OK",
                        "rooms_count": len(response.rooms)
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e)
                    }
                finally:
                    await livekit_api.aclose()
            
            result = asyncio.run(test_livekit_connection())
            return jsonify(result)
        except Exception as e:
            import traceback
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
    
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
    
    @app.route("/api/trunk/setup/direct", methods=["POST"])
    def setup_trunk_direct():
        """Endpoint pour configurer le trunk SIP directement dans le processus principal"""
        try:
            # Importations nécessaires
            from twilio.rest import Client
            import asyncio
            from livekit import api
            from livekit.protocol.sip import CreateSIPOutboundTrunkRequest, SIPOutboundTrunkInfo
            
            # Récupération des variables d'environnement
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            phone_number = os.environ.get("TWILIO_PHONE_NUMBER")
            
            logger.info(f"Setup trunk direct - Variables d'environnement: TWILIO_ACCOUNT_SID={account_sid[:4]}..., TWILIO_PHONE_NUMBER={phone_number}")
            
            # Vérification des variables
            if not all([account_sid, auth_token, phone_number]):
                return jsonify({
                    "success": False,
                    "error": "Variables d'environnement Twilio manquantes",
                    "details": {
                        "TWILIO_ACCOUNT_SID": bool(account_sid),
                        "TWILIO_AUTH_TOKEN": bool(auth_token),
                        "TWILIO_PHONE_NUMBER": bool(phone_number)
                    }
                }), 400
            
            # Fonction asynchrone pour configurer le trunk
            async def setup_trunk_async():
                try:
                    logger.info("Initialisation du client Twilio...")
                    # Initialisation du client Twilio
                    client = Client(account_sid, auth_token)
                    
                    logger.info("Récupération des trunks existants...")
                    # Récupération ou création du trunk Twilio - CORRECTION: utilisation de v1
                    trunks = client.sip.v1.trunks.list(limit=20)
                    
                    if trunks:
                        trunk = trunks[0]
                        logger.info(f"Utilisation du trunk existant: {trunk.sid}")
                    else:
                        logger.info("Création d'un nouveau trunk...")
                        # CORRECTION: utilisation de v1
                        trunk = client.sip.v1.trunks.create(friendly_name="LiveKit AI Trunk")
                        logger.info(f"Nouveau trunk créé: {trunk.sid}")
                    
                    domain_name = f"{trunk.sid}.sip.twilio.com"
                    logger.info(f"Domaine SIP: {domain_name}")
                    
                    # Récupérer les credential lists
                    logger.info("Récupération des credential lists...")
                    # CORRECTION: utilisation de v1
                    credential_lists = client.sip.v1.credential_lists.list(limit=20)
                    
                    if credential_lists:
                        cred_list = credential_lists[0]
                        logger.info(f"Utilisation de la credential list existante: {cred_list.sid}")
                    else:
                        logger.info("Création d'une nouvelle credential list...")
                        # CORRECTION: utilisation de v1
                        cred_list = client.sip.v1.credential_lists.create(friendly_name="LiveKit Credentials")
                        # CORRECTION: utilisation de v1
                        client.sip.v1.credential_lists(cred_list.sid).credentials.create(
                            username="livekit_user", password="s3cur3p@ssw0rd"
                        )
                        logger.info(f"Nouvelle credential list créée: {cred_list.sid}")
                    
                    logger.info("Initialisation du client LiveKit...")
                    # Initialisation du client LiveKit
                    livekit_api = api.LiveKitAPI()
                    
                    try:
                        # Création de l'objet trunk
                        logger.info("Création de l'objet trunk SIP...")
                        trunk_info = SIPOutboundTrunkInfo(
                            name="Twilio Trunk",
                            address=domain_name,
                            numbers=[phone_number],
                            auth_username="livekit_user",
                            auth_password="s3cur3p@ssw0rd"
                        )
                        
                        # Création de la requête
                        request = CreateSIPOutboundTrunkRequest(trunk=trunk_info)
                        
                        # Envoi de la requête à LiveKit
                        logger.info("Envoi de la requête à LiveKit...")
                        response = await livekit_api.sip.create_sip_outbound_trunk(request)
                        logger.info(f"Trunk SIP créé avec succès: {response.sid}")
                        
                        return {"success": True, "trunkId": response.sid, "message": "Trunk SIP configuré avec succès"}
                    finally:
                        await livekit_api.aclose()
                except Exception as e:
                    logger.error(f"Erreur dans setup_trunk_async: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    raise
            
            # Exécution de la fonction asynchrone
            logger.info("Démarrage de setup_trunk_async...")
            result = asyncio.run(setup_trunk_async())
            logger.info(f"Résultat: {result}")
            
            return jsonify(result)
        except Exception as e:
            import traceback
            logger.exception("Erreur lors de la configuration directe du trunk")
            return jsonify({
                "success": False,
                "error": "Erreur lors de la configuration du trunk",
                "details": traceback.format_exc()
            }), 500
    
    @app.route("/api/twilio/test-connect", methods=["GET"])
    def test_twilio_connect():
        """Endpoint pour tester directement la connexion et l'API Twilio"""
        try:
            from twilio.rest import Client
            
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            
            client = Client(account_sid, auth_token)
            account = client.api.accounts(account_sid).fetch()
            
            # Vérifier les méthodes disponibles sur le client.sip
            sip_methods = dir(client.sip)
            
            return jsonify({
                "success": True,
                "account": {
                    "sid": account.sid,
                    "status": account.status,
                    "name": account.friendly_name
                },
                "sip_methods": sip_methods
            })
        except Exception as e:
            import traceback
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
