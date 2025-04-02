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
                livekit_api = None
                try:
                    livekit_api = api.LiveKitAPI()
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
                    if livekit_api:
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

    @app.route("/api/dispatch/test", methods=["POST"])
    def test_dispatch():
        """Endpoint pour tester la création d'un dispatch"""
        data = request.json
        if not data or "phone" not in data:
            return jsonify({"error": "Numéro de téléphone manquant"}), 400
        
        phone_number = data["phone"]
        
        try:
            from livekit import api
            
            async def create_test_dispatch():
                livekit_api = None
                try:
                    livekit_api = api.LiveKitAPI()
                    
                    # Vérifier si OUTBOUND_TRUNK_ID est défini
                    trunk_id = os.getenv('OUTBOUND_TRUNK_ID')
                    if not trunk_id:
                        return {
                            "success": False,
                            "error": "Aucun trunk SIP configuré. Utilisez /api/trunk/setup/direct d'abord."
                        }
                    
                    # Génération d'un nom de room unique
                    unique_room_name = f"dispatch-{secrets.token_hex(4)}"
                    
                    # Création du dispatch - modification de la méthode
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
                        "message": f"Dispatch créé pour {phone_number}"
                    }
                
                except Exception as e:
                    logger.error(f"Erreur de dispatch: {e}")
                    return {
                        "success": False,
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    }
                finally:
                    if livekit_api:
                        await livekit_api.aclose()
            
            # Exécuter la fonction asynchrone
            result = asyncio.run(create_test_dispatch())
            
            if result['success']:
                return jsonify(result)
            else:
                return jsonify(result), 500
        
        except Exception as e:
            logger.exception("Erreur lors du test de dispatch")
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
        verbose = data.get("verbose", False)  # Option pour avoir plus de détails
        
        try:
            from livekit import api
            
            async def create_call():
                livekit_api = None
                try:
                    livekit_api = api.LiveKitAPI()
                    
                    # Vérifier si OUTBOUND_TRUNK_ID est défini
                    trunk_id = os.getenv('OUTBOUND_TRUNK_ID')
                    if not trunk_id:
                        return {
                            "success": False,
                            "error": "Aucun trunk SIP configuré. Utilisez /api/trunk/setup/direct d'abord."
                        }
                    
                    # Vérifier que l'agent est disponible
                    agents = await livekit_api.agent_dispatch.list_agent_info(
                        api.ListAgentInfoRequest()
                    )
                    agent_available = any(agent.name == "outbound-caller" for agent in agents.agents)
                    if not agent_available:
                        return {
                            "success": False,
                            "error": "L'agent 'outbound-caller' n'est pas disponible. Vérifiez que le worker est en cours d'exécution."
                        }
                    
                    # Génération d'un nom de room unique
                    unique_room_name = f"call-{secrets.token_hex(4)}"
                    
                    # Journalisation détaillée
                    logger.info(f"Préparation de l'appel vers {phone_number}")
                    logger.info(f"Trunk ID: {trunk_id}")
                    logger.info(f"Room: {unique_room_name}")
                    
                    # Création du dispatch
                    dispatch_request = api.CreateAgentDispatchRequest(
                        agent_name="outbound-caller",
                        room=unique_room_name,
                        metadata=json.dumps({
                            "phone_number": phone_number,
                            "trunk_id": trunk_id
                        })
                    )
                    
                    logger.info(f"Envoi de la requête de dispatch: {dispatch_request}")
                    dispatch = await livekit_api.agent_dispatch.create_dispatch(dispatch_request)
                    logger.info(f"Dispatch créé: {dispatch}")
                    
                    # Attendre brièvement pour vérifier si la room est créée
                    await asyncio.sleep(1)
                    rooms_check = await livekit_api.room.list_rooms(api.ListRoomsRequest(names=[unique_room_name]))
                    
                    return {
                        "success": True,
                        "roomName": dispatch.room,
                        "dispatchId": dispatch.id,
                        "message": f"Appel initié pour {phone_number}",
                        "diagnostic": {
                            "agent_available": agent_available,
                            "trunk_id": trunk_id,
                            "room_created": len(rooms_check.rooms) > 0,
                            "metadata": {
                                "phone_number": phone_number,
                                "trunk_id": trunk_id
                            }
                        } if verbose else None
                    }
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'appel: {e}")
                    return {
                        "success": False,
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    }
                finally:
                    if livekit_api:
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
    
    @app.route("/api/agent/status", methods=["GET"])
    def check_agent_status():
        """Endpoint pour vérifier si l'agent est en cours d'exécution et disponible"""
        try:
            from livekit import api
            
            async def check_agents():
                livekit_api = None
                try:
                    livekit_api = api.LiveKitAPI()
                    
                    # Récupérer les agents disponibles
                    agents = await livekit_api.agent_dispatch.list_agent_info(
                        api.ListAgentInfoRequest()
                    )
                    
                    active_agents = []
                    for agent in agents.agents:
                        active_agents.append({
                            "name": agent.name,
                            "status": "active",
                            "capacity": agent.capacity,
                        })
                    
                    return {
                        "success": True,
                        "agents": active_agents,
                        "outbound_caller_available": any(agent.name == "outbound-caller" for agent in agents.agents)
                    }
                    
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    }
                finally:
                    if livekit_api:
                        await livekit_api.aclose()
            
            result = asyncio.run(check_agents())
            return jsonify(result)
        
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500
    
    @app.route("/api/trunk/status", methods=["GET"])
    def check_trunk_status():
        """Endpoint pour vérifier l'état du trunk SIP outbound"""
        try:
            from livekit import api
            
            async def check_trunk():
                livekit_api = None
                try:
                    livekit_api = api.LiveKitAPI()
                    
                    # Récupérer l'ID du trunk
                    trunk_id = os.getenv('OUTBOUND_TRUNK_ID')
                    if not trunk_id:
                        return {
                            "success": False,
                            "error": "Aucun trunk SIP configuré"
                        }
                    
                    # Vérifier le trunk dans LiveKit - modification pour corriger l'erreur
                    # Au lieu de filtrer par ID, nous allons récupérer tous les trunks et filtrer manuellement
                    try:
                        # Récupérer tous les trunks outbound
                        trunks_response = await livekit_api.sip.list_sip_outbound_trunk(
                            api.ListSIPOutboundTrunkRequest()
                        )
                        
                        # Filtrer manuellement pour trouver le trunk avec l'ID correspondant
                        matching_trunks = [t for t in trunks_response.trunks if t.sid == trunk_id]
                        trunk_exists = len(matching_trunks) > 0
                        trunk_details = matching_trunks[0] if trunk_exists else None
                    except Exception as e:
                        logger.error(f"Erreur lors de la récupération des trunks LiveKit: {e}")
                        trunk_exists = False
                        trunk_details = None
                    
                    # Vérifier le trunk dans Twilio
                    from twilio.rest import Client
                    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
                    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
                    
                    twilio_trunk_info = None
                    if account_sid and auth_token:
                        client = Client(account_sid, auth_token)
                        twilio_trunks = list(client.trunking.trunks.list(limit=1))
                        if twilio_trunks:
                            twilio_trunk_info = {
                                "sid": twilio_trunks[0].sid,
                                "name": twilio_trunks[0].friendly_name,
                                "domain": f"{twilio_trunks[0].sid}.sip.twilio.com"
                            }
                    
                    return {
                        "success": True,
                        "livekit_trunk": {
                            "id": trunk_id,
                            "exists": trunk_exists,
                            "details": {
                                "name": trunk_details.name if trunk_details else None,
                                "address": trunk_details.address if trunk_details else None,
                                "numbers": trunk_details.numbers if trunk_details else None
                            } if trunk_details else None
                        },
                        "twilio_trunk": twilio_trunk_info
                    }
                    
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    }
                finally:
                    if livekit_api:
                        await livekit_api.aclose()
            
            result = asyncio.run(check_trunk())
            return jsonify(result)
        
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500
