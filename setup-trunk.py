import asyncio
import os
import json
import argparse
from dotenv import load_dotenv
from livekit import api
from livekit.protocol.sip import CreateSIPOutboundTrunkRequest, SIPOutboundTrunkInfo
from twilio.rest import Client

load_dotenv()

# Variables d'environnement Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

def create_twilio_sip_trunk():
    """
    Crée (ou récupère) un trunk SIP dans Twilio et configure les paramètres nécessaires
    
    Returns:
        dict: Informations sur le trunk SIP Twilio créé
    """
    # Vérification des informations Twilio
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
        print("Erreur: Variables d'environnement Twilio manquantes. Vérifiez votre fichier .env")
        return None
    
    try:
        # Initialisation du client Twilio
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Création du trunk SIP sur Twilio ou récupération de l'existant
        trunks = client.sip.trunks.list(limit=20)
        
        if trunks:
            trunk = trunks[0]  # Utiliser le premier trunk existant
            print(f"Utilisation du trunk Twilio existant: {trunk.sid}")
        else:
            # Création d'un nouveau trunk
            trunk = client.sip.trunks.create(friendly_name="LiveKit AI Trunk")
            print(f"Nouveau trunk Twilio créé: {trunk.sid}")
        
        # Configuration du trunk (domaine, etc.)
        domain_name = f"{trunk.sid}.sip.twilio.com"
        
        # Récupération ou création d'une credential list
        credential_lists = client.sip.credential_lists.list(limit=20)
        if credential_lists:
            cred_list = credential_lists[0]
            print(f"Utilisation de la credential list existante: {cred_list.sid}")
        else:
            cred_list = client.sip.credential_lists.create(friendly_name="LiveKit Credentials")
            # Ajout d'un nouvel identifiant à la liste (vous pouvez personnaliser)
            username = "livekit_user"
            password = "s3cur3p@ssw0rd"
            client.sip.credential_lists(cred_list.sid).credentials.create(
                username=username, password=password
            )
            print(f"Nouvelle credential list créée: {cred_list.sid}")
        
        # Renvoyer les informations du trunk
        return {
            "sid": trunk.sid,
            "domain_name": domain_name,
            "phone_number": TWILIO_PHONE_NUMBER,
            "auth_username": "livekit_user",
            "auth_password": "s3cur3p@ssw0rd"
        }
    
    except Exception as e:
        print(f"Erreur lors de la configuration du trunk Twilio: {e}")
        return None

async def create_outbound_trunk(trunk_data_file):
    """
    Crée un trunk SIP sortant dans LiveKit en utilisant les données d'un fichier JSON
    ou en récupérant automatiquement les données Twilio si disponibles
    
    Args:
        trunk_data_file: Chemin vers un fichier JSON contenant les informations du trunk
                        ou None pour utiliser Twilio directement
    
    Returns:
        L'ID du trunk créé
    """
    # Initialisation du client LiveKit
    livekit_api = api.LiveKitAPI()
    
    # Déterminer si on utilise un fichier ou Twilio directement
    if trunk_data_file and os.path.exists(trunk_data_file):
        # Chargement des données du trunk depuis le fichier
        with open(trunk_data_file, 'r') as f:
            trunk_config = json.load(f)
        
        # Extraction des informations du trunk
        trunk_info = trunk_config.get('trunk', {})
    else:
        # Obtenir les informations directement de Twilio
        twilio_trunk = create_twilio_sip_trunk()
        if not twilio_trunk:
            raise Exception("Impossible de configurer le trunk Twilio. Vérifiez vos identifiants.")
        
        # Conversion au format attendu
        trunk_info = {
            "name": "Twilio Trunk",
            "address": twilio_trunk["domain_name"],
            "numbers": [twilio_trunk["phone_number"]],
            "auth_username": twilio_trunk["auth_username"],
            "auth_password": twilio_trunk["auth_password"]
        }
    
    # Création de l'objet trunk
    trunk = SIPOutboundTrunkInfo(
        name=trunk_info.get('name', 'My Outbound Trunk'),
        address=trunk_info.get('address', ''),
        numbers=trunk_info.get('numbers', []),
        auth_username=trunk_info.get('auth_username', ''),
        auth_password=trunk_info.get('auth_password', ''),
    )
    
    # Création de la requête
    request = CreateSIPOutboundTrunkRequest(trunk=trunk)
    
    try:
        # Envoi de la requête à LiveKit
        response = await livekit_api.sip.create_sip_outbound_trunk(request)
        print(f"Trunk SIP sortant créé avec succès: ID = {response.sid}")
        
        # Enregistrement de l'ID du trunk dans le fichier .env
        with open('../agent/.env', 'r') as env_file:
            env_content = env_file.read()
        
        if 'OUTBOUND_TRUNK_ID' in env_content:
            # Mise à jour de la valeur existante
            env_lines = env_content.split('\n')
            updated_lines = []
            for line in env_lines:
                if line.startswith('OUTBOUND_TRUNK_ID='):
                    updated_lines.append(f'OUTBOUND_TRUNK_ID={response.sid}')
                else:
                    updated_lines.append(line)
            updated_env = '\n'.join(updated_lines)
        else:
            # Ajout de la nouvelle valeur
            updated_env = f"{env_content}\nOUTBOUND_TRUNK_ID={response.sid}"
        
        with open('../agent/.env', 'w') as env_file:
            env_file.write(updated_env)
        
        print(f"L'ID du trunk a été enregistré dans le fichier .env")
        
        return response.sid
    except Exception as e:
        print(f"Erreur lors de la création du trunk: {e}")
        raise
    finally:
        await livekit_api.aclose()

def main():
    parser = argparse.ArgumentParser(description='Créer un trunk SIP sortant dans LiveKit')
    parser.add_argument('--file', '-f', required=False, help='Chemin vers le fichier JSON contenant les informations du trunk')
    parser.add_argument('--twilio', '-t', action='store_true', help='Utiliser directement les informations Twilio')
    args = parser.parse_args()
    
    if args.twilio:
        # Utiliser directement les informations Twilio
        asyncio.run(create_outbound_trunk(None))
    elif args.file:
        # Utiliser un fichier de configuration
        asyncio.run(create_outbound_trunk(args.file))
    else:
        print("Erreur: Vous devez spécifier --file ou --twilio")
        parser.print_help()

if __name__ == "__main__":
    main()
