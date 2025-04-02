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
            
            # Vérifier et normaliser le format du numéro
            if not phone_number.startswith('+'):
                phone_number = f"+{phone_number}"
            
            # Supprimer les caractères spéciaux comme tirets ou espaces
            phone_number = ''.join(c for c in phone_number if c.isdigit() or c == '+')
            logger.info(f"Numéro formaté pour l'appel Twilio: {phone_number}")
            
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
        
        # Vérifier et normaliser le format du numéro
        if not phone_number.startswith('+'):
            phone_number = f"+{phone_number}"
        
        # Supprimer les caractères spéciaux comme tirets ou espaces
        phone_number = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        logger.info(f"Numéro formaté pour le test de dispatch: {phone_number}")
        
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
        
        # Vérifier et normaliser le format du numéro
        if not phone_number.startswith('+'):
            phone_number = f"+{phone_number}"
        
        # Supprimer les caractères spéciaux comme tirets ou espaces
        phone_number = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        logger.info(f"Numéro formaté pour l'appel API: {phone_number}")
        
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
                    
                    # Nous ne vérifions plus si l'agent est disponible car list_agent_info n'est pas disponible
                    # Au lieu de cela, nous supposons que l'agent est en cours d'exécution
                    # et nous laissons la création du dispatch échouer si ce n'est pas le cas
                    agent_available = True  # On suppose que l'agent est disponible
                    
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
                            "agent_available": agent_available,  # Présumé vrai
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
                    
                    # Nous ne pouvons pas récupérer les agents avec list_agent_info
                    # À la place, nous allons essayer de créer un dispatch pour voir si l'agent est disponible
                    
                    # Création d'un dispatch temporaire pour tester si l'agent est disponible
                    try:
                        # Nom unique pour éviter des conflits
                        test_room = f"test-agent-{secrets.token_hex(4)}"
                        test_dispatch = await livekit_api.agent_dispatch.create_dispatch(
                            api.CreateAgentDispatchRequest(
                                agent_name="outbound-caller",
                                room=test_room,
                                metadata=json.dumps({"test": True})
                            )
                        )
                        
                        # Si on arrive ici, le dispatch a été créé, donc l'agent est disponible
                        # Suppression de la room de test
                        await livekit_api.room.delete_room(api.DeleteRoomRequest(room=test_room))
                        
                        return {
                            "success": True,
                            "agents": [
                                {
                                    "name": "outbound-caller",
                                    "status": "active",
                                    "capacity": 1.0
                                }
                            ],
                            "outbound_caller_available": True
                        }
                        
                    except Exception as e:
                        # Si une erreur se produit, l'agent n'est probablement pas disponible
                        logger.error(f"Erreur lors du test de l'agent: {e}")
                        return {
                            "success": True,
                            "agents": [],
                            "outbound_caller_available": False
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
                    
                    # Vérifier le trunk dans LiveKit
                    trunks = await livekit_api.sip.list_sip_outbound_trunk(
                        api.ListSIPOutboundTrunkRequest(ids=[trunk_id])
                    )
                    
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
                            "exists": len(trunks.trunks) > 0,
                            "details": {
                                "name": trunks.trunks[0].name if trunks.trunks else None,
                                "address": trunks.trunks[0].address if trunks.trunks else None,
                                "numbers": trunks.trunks[0].numbers if trunks.trunks else None
                            } if trunks.trunks else None
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
            
    @app.route("/api/sip/direct-call", methods=["POST"])
    def direct_sip_call():
        """Test d'appel direct via l'API SIP de LiveKit"""
        try:
            from livekit import api
            from livekit.protocol.sip import CreateSIPParticipantRequest
            
            data = request.json
            if not data or "phone" not in data:
                return jsonify({"error": "Numéro de téléphone manquant"}), 400
            
            phone_number = data["phone"]
            
            # Vérifier et normaliser le format du numéro
            if not phone_number.startswith('+'):
                phone_number = f"+{phone_number}"
            
            # Supprimer les caractères spéciaux comme tirets ou espaces
            phone_number = ''.join(c for c in phone_number if c.isdigit() or c == '+')
            logger.info(f"Numéro formaté pour l'appel SIP direct: {phone_number}")
            
            async def make_direct_call():
                livekit_api = None
                try:
                    livekit_api = api.LiveKitAPI()
                    
                    # Vérifier si OUTBOUND_TRUNK_ID est défini
                    trunk_id = os.getenv('OUTBOUND_TRUNK_ID')
                    if not trunk_id:
                        return {
                            "success": False,
                            "error": "Aucun trunk SIP configuré"
                        }
                    
                    # Créer une room unique pour cet appel
                    room_name = f"direct-call-{secrets.token_hex(4)}"
                    
                    # Créer la requête SIP
                    request = CreateSIPParticipantRequest(
                        room_name=room_name,
                        sip_trunk_id=trunk_id,
                        sip_call_to=phone_number,
                        participant_identity=f"direct_call_{phone_number}",
                        participant_name=f"Direct Call {phone_number}",
                        play_dialtone=True,
                    )
                    
                    # Envoyer la requête
                    logger.info(f"Envoi de la requête SIP directe: {request}")
                    response = await livekit_api.sip.create_sip_participant(request)
                    logger.info(f"Réponse SIP reçue: {response}")
                    
                    return {
                        "success": True,
                        "message": f"Appel direct initié vers {phone_number}",
                        "roomName": room_name,
                        "trunkId": trunk_id,
                        "response": str(response)
                    }
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'appel SIP direct: {e}")
                    return {
                        "success": False,
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    }
                finally:
                    if livekit_api:
                        await livekit_api.aclose()
            
            result = asyncio.run(make_direct_call())
            return jsonify(result)
            
        except Exception as e:
            logger.exception("Erreur lors de l'appel SIP direct")
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500
    
    @app.route("/api/test-direct-call/<phone_number>", methods=["GET"])
    def api_test_direct_call(phone_number):
        """Endpoint pour exécuter le script de test d'appel direct"""
        try:
            # Vérifier et normaliser le format du numéro
            if not phone_number.startswith('+'):
                phone_number = f"+{phone_number}"
            
            # Supprimer les caractères spéciaux comme tirets ou espaces
            phone_number = ''.join(c for c in phone_number if c.isdigit() or c == '+')
            logger.info(f"Numéro formaté pour le test direct: {phone_number}")
            
            # Importation depuis le module (assurez-vous que scripts/test_direct_sip_call.py existe)
            from livekit import api
            from livekit.protocol.sip import CreateSIPParticipantRequest
            
            # Récupération du trunk ID
            trunk_id = os.getenv('OUTBOUND_TRUNK_ID')
            if not trunk_id:
                return jsonify({
                    "success": False,
                    "error": "Aucun trunk SIP configuré. Utilisez /api/trunk/setup/direct d'abord."
                })
            
            # Créer un collecteur de logs
            class LogCollector:
                def __init__(self):
                    self.logs = []
                
                def info(self, message):
                    self.logs.append(f"INFO: {message}")
                    logger.info(message)
                
                def warning(self, message):
                    self.logs.append(f"WARNING: {message}")
                    logger.warning(message)
                
                def error(self, message):
                    self.logs.append(f"ERROR: {message}")
                    logger.error(message)
                
                def exception(self, message):
                    self.logs.append(f"EXCEPTION: {message}")
                    logger.exception(message)
            
            # Fonction d'appel direct
            async def make_direct_call():
                log_collector = LogCollector()
                livekit_api = None
                
                try:
                    # Initialisation du client LiveKit
                    livekit_api = api.LiveKitAPI()
                    
                    # Création d'un nom de room unique
                    import secrets
                    room_name = f"test-call-{secrets.token_hex(4)}"
                    
                    log_collector.info(f"====== TEST D'APPEL DIRECT ======")
                    log_collector.info(f"Numéro de téléphone: {phone_number}")
                    log_collector.info(f"Trunk ID: {trunk_id}")
                    log_collector.info(f"Room Name: {room_name}")
                    
                    # Création de la requête SIP
                    request = CreateSIPParticipantRequest(
                        room_name=room_name,
                        sip_trunk_id=trunk_id,
                        sip_call_to=phone_number,
                        participant_identity=f"test_user_{phone_number}",
                        participant_name=f"Test Call {phone_number}",
                        play_dialtone=True,
                    )
                    
                    # Envoi de la requête
                    log_collector.info(f"Envoi de la requête SIP: {request}")
                    response = await livekit_api.sip.create_sip_participant(request)
                    log_collector.info(f"Réponse SIP reçue: {response}")
                    
                    # Attendre quelques secondes pour permettre à l'appel de démarrer
                    log_collector.info("Attente pendant l'établissement de l'appel...")
                    await asyncio.sleep(5)
                    
                    # Vérifier si la room existe et contient des participants
                    room_info = await livekit_api.room.list_rooms(api.ListRoomsRequest(names=[room_name]))
                    
                    if room_info.rooms:
                        room = room_info.rooms[0]
                        log_collector.info(f"Room créée. Nombre de participants: {room.num_participants}")
                        
                        # Surveiller la room pendant un certain temps
                        log_collector.info("Surveillance de la room pour 60 secondes...")
                        for i in range(12):  # 60 secondes au total
                            await asyncio.sleep(5)
                            room_info = await livekit_api.room.list_rooms(api.ListRoomsRequest(names=[room_name]))
                            if not room_info.rooms:
                                log_collector.info("La room n'existe plus, l'appel s'est terminé")
                                break
                                
                            room = room_info.rooms[0]
                            log_collector.info(f"Statut de la room après {(i+1)*5} secondes: {room.num_participants} participants")
                    else:
                        log_collector.warning("La room n'a pas été créée ou a déjà été supprimée")
                    
                    log_collector.info("Fin du test d'appel direct")
                    
                    return {
                        "success": True,
                        "message": f"Test d'appel direct exécuté pour {phone_number}",
                        "roomName": room_name,
                        "logs": log_collector.logs
                    }
                    
                except Exception as e:
                    log_collector.error(f"Erreur lors du test d'appel direct: {e}")
                    import traceback
                    trace = traceback.format_exc()
                    log_collector.error(trace)
                    return {
                        "success": False,
                        "error": str(e),
                        "traceback": trace,
                        "logs": log_collector.logs
                    }
                finally:
                    if livekit_api:
                        await livekit_api.aclose()
            
            # Exécuter la fonction d'appel direct
            result = asyncio.run(make_direct_call())
            return jsonify(result)
            
        except Exception as e:
            logger.exception("Erreur lors de l'exécution du test d'appel direct")
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500

    @app.route("/api/trunk/reconfigure", methods=["POST"])
    def reconfigure_trunk():
        """Reconfigure le trunk SIP avec des paramètres plus détaillés"""
        try:
            import asyncio
            from livekit import api
            from livekit.protocol.sip import CreateSIPOutboundTrunkRequest, SIPOutboundTrunkInfo
            from twilio.rest import Client
    
            async def reconfigure_trunk_async():
                livekit_api = None
                try:
                    # Variables Twilio
                    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
                    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
                    phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
                    existing_trunk_id = os.environ.get('OUTBOUND_TRUNK_ID')
                    
                    if not all([account_sid, auth_token, phone_number]):
                        return {
                            "success": False,
                            "error": "Variables Twilio manquantes"
                        }
                    
                    # Client Twilio
                    client = Client(account_sid, auth_token)
                    
                    # Afficher l'ancien trunk ID
                    logger.info(f"Trunk ID existant: {existing_trunk_id}")
                    logger.info("Note: La suppression de trunk n'est pas supportée, nous allons créer un nouveau trunk")
                    
                    try:
                        # Utilisation de client.trunking.trunks au lieu de client.sip.trunks
                        trunks = list(client.trunking.trunks.list(limit=1))
                        if trunks:
                            trunk = trunks[0]
                            logger.info(f"Utilisation du trunk Twilio existant: {trunk.sid}")
                        else:
                            trunk = client.trunking.trunks.create(friendly_name="LiveKit AI Trunk")
                            logger.info(f"Nouveau trunk Twilio créé: {trunk.sid}")
                        
                        # Vérifier si une liste d'identifiants existe
                        cred_lists = list(client.trunking.credential_lists.list(limit=1))
                        if not cred_lists:
                            logger.info("Création d'une nouvelle credential list Twilio")
                            cred_list = client.trunking.credential_lists.create(
                                friendly_name="LiveKit Credentials"
                            )
                            # Ajout des identifiants à la liste de credentials
                            cred_list.credentials.create(
                                username="livekit_user", 
                                password="s3cur3p@ssw0rd"
                            )
                        else:
                            cred_list = cred_lists[0]
                            logger.info(f"Utilisation de la credential list existante: {cred_list.sid}")
                            
                        # Associer la liste d'identifiants au trunk
                        try:
                            # Pour Twilio Trunking, l'association se fait différemment
                            trunk.credential_lists.create(cred_list.sid)
                            logger.info(f"Credential list associée au trunk")
                        except Exception as e:
                            logger.warning(f"Erreur lors de l'association de la credential list: {e}")
                        
                        # Client LiveKit
                        livekit_api = api.LiveKitAPI()
                        
                        # Configurer le domaine
                        domain_name = f"{trunk.sid}.sip.twilio.com"
                        
                        # Créer un nouvel objet trunk SIP dans LiveKit
                        trunk_info = SIPOutboundTrunkInfo(
                            name="Twilio Trunk",
                            address=domain_name,
                            numbers=[phone_number],
                            auth_username="livekit_user",
                            auth_password="s3cur3p@ssw0rd"
                        )
                        
                        # Envoyer la requête à LiveKit
                        request = CreateSIPOutboundTrunkRequest(trunk=trunk_info)
                        response = await livekit_api.sip.create_sip_outbound_trunk(request)
                        
                        # Récupérer l'ID du nouveau trunk
                        trunk_id = getattr(response, 'sid', getattr(response, 'id', str(response)))
                        
                        # Mettre à jour la variable d'environnement
                        os.environ['OUTBOUND_TRUNK_ID'] = trunk_id
                        
                        return {
                            "success": True,
                            "old_trunk_id": existing_trunk_id,
                            "new_trunk_id": trunk_id,
                            "twilioTrunkSid": trunk.sid,
                            "domainName": domain_name,
                            "message": "Nouveau trunk SIP configuré avec succès"
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
            result = asyncio.run(reconfigure_trunk_async())
            return jsonify(result)
            
        except Exception as e:
            logger.exception("Erreur lors de la reconfiguration du trunk")
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500
