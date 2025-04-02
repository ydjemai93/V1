# scripts/test_direct_sip_call.py
import asyncio
import os
import logging
import argparse
from dotenv import load_dotenv
from livekit import api
from livekit.protocol.sip import CreateSIPParticipantRequest

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
load_dotenv()

# Trunk ID pour les appels sortants
OUTBOUND_TRUNK_ID = os.getenv("OUTBOUND_TRUNK_ID")

async def make_direct_call(phone_number):
    """
    Effectue un appel direct sans utiliser l'agent
    
    Args:
        phone_number: Numéro de téléphone à appeler
    """
    # Initialisation du client LiveKit
    livekit_api = api.LiveKitAPI()
    
    try:
        # Vérification du format du numéro
        if not phone_number.startswith('+'):
            logger.warning(f"Le numéro {phone_number} ne commence pas par '+'. Ajout du préfixe...")
            phone_number = f"+{phone_number}"
            
        # Supprimer les caractères spéciaux comme tirets ou espaces
        phone_number = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        logger.info(f"Numéro formaté pour l'appel: {phone_number}")
            
        # Création d'un nom de room unique
        import secrets
        room_name = f"test-call-{secrets.token_hex(4)}"
        
        logger.info(f"====== TEST D'APPEL DIRECT ======")
        logger.info(f"Numéro de téléphone: {phone_number}")
        logger.info(f"Trunk ID: {OUTBOUND_TRUNK_ID}")
        logger.info(f"Room Name: {room_name}")
        
        # Création de la requête SIP
        request = CreateSIPParticipantRequest(
            room_name=room_name,
            sip_trunk_id=OUTBOUND_TRUNK_ID,
            sip_call_to=phone_number,
            participant_identity=f"test_user_{phone_number}",
            participant_name=f"Test Call {phone_number}",
            play_dialtone=True,
        )
        
        # Envoi de la requête
        logger.info(f"Envoi de la requête SIP: {request}")
        response = await livekit_api.sip.create_sip_participant(request)
        logger.info(f"Réponse SIP reçue: {response}")
        
        # Attendre quelques secondes pour permettre à l'appel de démarrer
        logger.info("Attente pendant l'établissement de l'appel...")
        await asyncio.sleep(5)
        
        # Vérifier si la room existe et contient des participants
        room_info = await livekit_api.room.list_rooms(api.ListRoomsRequest(names=[room_name]))
        
        if room_info.rooms:
            room = room_info.rooms[0]
            logger.info(f"Room créée. Nombre de participants: {room.num_participants}")
            
            # Surveiller la room pendant un certain temps
            logger.info("Surveillance de la room pour 60 secondes...")
            for i in range(12):  # 60 secondes au total
                await asyncio.sleep(5)
                room_info = await livekit_api.room.list_rooms(api.ListRoomsRequest(names=[room_name]))
                if not room_info.rooms:
                    logger.info("La room n'existe plus, l'appel s'est terminé")
                    break
                    
                room = room_info.rooms[0]
                logger.info(f"Statut de la room après {(i+1)*5} secondes: {room.num_participants} participants")
        else:
            logger.warning("La room n'a pas été créée ou a déjà été supprimée")
        
        logger.info("Fin du test d'appel direct")
        
    except Exception as e:
        logger.error(f"Erreur lors du test d'appel direct: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await livekit_api.aclose()

def main():
    parser = argparse.ArgumentParser(description='Test d\'appel direct via SIP')
    parser.add_argument('--phone', '-p', required=True, help='Numéro de téléphone à appeler')
    args = parser.parse_args()
    
    asyncio.run(make_direct_call(args.phone))

if __name__ == "__main__":
    main()
