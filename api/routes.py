import os
import json
import subprocess
import sys
import logging
from flask import request, jsonify
from threading import Thread
import asyncio
import traceback
import aiohttp
import secrets

# Configuration pour fermer proprement les sessions aiohttp
asyncio.get_event_loop().set_debug(True)
aiohttp.ClientSession.DEFAULT_TIMEOUT = 30

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
    
    @app.route("/api/sip/check", methods=["GET"])
    def check_sip_config():
        """Vérification détaillée de la configuration SIP"""
        try:
            from twilio.rest import Client
            
            account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
            auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
            phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
            trunk_id = os.environ.get('OUTBOUND_TRUNK_ID')
            
            client = Client(account_sid, auth_token)
            
            # Vérification du trunk
            trunk = client.trunking.trunks(trunk_id).fetch()
            
            return jsonify({
                "success": True,
                "account_sid": account_sid,
                "phone_number": phone_number,
                "trunk_id": trunk_id,
                "trunk_name": trunk.friendly_name,
                "trunk_domain": f"{trunk_id}.sip.twilio.com"
            })
        
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500
    
    @app.route("/api/twilio/test-call", methods=["POST"])
    def test_twilio_call():
        """Test d'appel direct via Twilio"""
        try:
            from twilio.rest import Client
            
            data = request.json
            if not data or "phone" not in data:
                return jsonify({"error": "Numéro de téléphone manquant"}), 400
            
            phone_number = data["phone"]
            
            account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
            auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
            twilio_phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
            
            client = Client(account_sid, auth_token)
            
            # Tenter un appel simple
            call = client.calls.create(
                to=phone_number,
                from_=twilio_phone_number,
                url="http://demo.twilio.com/docs/voice.xml"  # URL de test Twilio
            )
            
            return jsonify({
                "success": True,
                "call_sid": call.sid,
                "status": call.status
            })
        
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500

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
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500

    @app.route("/api/livekit/test", methods=["GET"])
    def test_livekit():
        """Endpoint pour tester la connexion à LiveKit"""
        try:
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
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500

   @app.route("/api/trunk/setup/direct", methods=["POST"])
def setup_trunk_direct():
    """Endpoint pour configurer directement le trunk SIP via l'API"""
    try:
        import asyncio
        from livekit import api
        from livekit.protocol.sip import CreateSIPOutboundTrunkRequest, SIPOutboundTrunkInfo
        from twilio.rest import Client

        async def setup_trunk_async():
            # Variables Twilio
            account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
            auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
            phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
            livekit_api = None

            if not all([account_sid, auth_token, phone_number]):
                return {
                    "success": False,
                    "error": "Variables Twilio manquantes"
                }

            try:
                # Client Twilio
                client = Client(account_sid, auth_token)
                
                # Débogage - impression des attributs du client
                logger.info(f"Attributs du client Twilio: {dir(client)}")
                logger.info(f"Attributs de trunking: {dir(client.trunking)}")
                
                try:
                    # Essayer de récupérer les trunks
                    trunks = list(client.trunking.trunks.list(limit=1))
                except Exception as e:
                    logger.error(f"Erreur lors de la récupération des trunks: {e}")
                    trunks = []
                
                # Créer un trunk si aucun n'existe
                if not trunks:
                    logger.info("Aucun trunk trouvé. Création d'un nouveau trunk.")
                    trunk = client.trunking.trunks.create(friendly_name="LiveKit AI Trunk")
                else:
                    trunk = trunks[0]
                    logger.info(f"Trunk existant trouvé: {trunk.sid}")

                # Configurer le domaine
                domain_name = f"{trunk.sid}.sip.twilio.com"

                # Initialisation du client LiveKit
                livekit_api = api.LiveKitAPI()
                
                # Création de l'objet trunk
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
                response = await livekit_api.sip.create_sip_outbound_trunk(request)
                
                # Récupérer l'ID du trunk
                trunk_id = getattr(response, 'sid', getattr(response, 'id', str(response)))
                
                # Mise à jour de l'environnement
                os.environ['OUTBOUND_TRUNK_ID'] = trunk_id

                return {
                    "success": True,
                    "trunkId": trunk_id,
                    "twilioTrunkSid": trunk.sid,
                    "domainName": domain_name,
                    "message": "Trunk SIP configuré avec succès"
                }
            except Exception as e:
                logger.error(f"Erreur de configuration du trunk: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            finally:
                # S'assurer que la session LiveKit est fermée
                if livekit_api:
                    await livekit_api.aclose()

        # Exécuter la fonction asynchrone
        result = asyncio.run(setup_trunk_async())
        
        return jsonify(result)
    
    except Exception as e:
        logger.exception("Erreur lors de la configuration du trunk")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

    @app.route("/api/call", methods=["POST"])
    def make_call():
        """Endpoint pour lancer un appel sortant"""
        data = request.json
        if not data or "phone" not in data:
            return jsonify({"error": "Numéro de téléphone manquant"}), 400
        
        phone_number = data["phone"]
        
        try:
            from livekit import api
            
            async def create_call():
                livekit_api = api.LiveKitAPI()
                
                try:
                    # Vérifier si OUTBOUND_TRUNK_ID est défini
                    trunk_id = os.getenv('OUTBOUND_TRUNK_ID')
                    if not trunk_id:
                        return {
                            "success": False,
                            "error": "Aucun trunk SIP configuré. Utilisez /api/trunk/setup/direct d'abord."
                        }
                    
                    # Génération d'un nom de room unique
                    unique_room_name = f"call-{secrets.token_hex(4)}"
                    
                    # Création du dispatch
                    dispatch = await livekit_api.agent_dispatch.create_dispatch(
                        api.CreateAgentDispatchRequest(
                            agent_name="outbound-caller",
                            room=unique_room_name,
                            metadata=json.dumps({
                                "phone_number": phone_number,
                                "trunk_id": trunk_id
                            })
                        )
                    )
                    
                    return {
                        "success": True,
                        "roomName": dispatch.room,
                        "dispatchId": dispatch.id,
                        "message": f"Appel initié pour {phone_number}"
                    }
                
                except Exception as e:
                    logger.error(f"Erreur lors de l'appel: {e}")
                    return {
                        "success": False,
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    }
                finally:
                    await livekit_api.aclose()
            
            # Exécuter la fonction asynchrone
            result = asyncio.run(create_call())
            
            if result['success']:
                return jsonify(result)
            else:
                return jsonify(result), 500
        
        except Exception as e:
            logger.exception("Erreur lors de l'appel")
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500
