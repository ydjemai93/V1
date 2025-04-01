import asyncio
import os
import json
import argparse
from dotenv import load_dotenv
from livekit import api
from livekit.protocol.sip import CreateSIPOutboundTrunkRequest, SIPOutboundTrunkInfo
from twilio.rest import Client

# Chercher le fichier .env à la racine du projet
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
env_path = os.path.join(root_dir, ".env")
load_dotenv(env_path)

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
    # Afficher toutes les variables d'environnement disponibles
    print("=== VARIABLES D'ENVIRONNEMENT DISPONIBLES ===")
    for key, value in os.environ.items():
        if "TWILIO" in key:
            mask = "***" if "TOKEN" in key or "SECRET" in key or "KEY" in key else value
            print(f"{key}={mask}")
    
    # Débogage: Vérifier les variables spécifiques
    print(f"TWILIO_ACCOUNT_SID={TWILIO_ACCOUNT_SID if TWILIO_ACCOUNT_SID else 'Non défini'}")
    print(f"TWILIO_AUTH_TOKEN={'*****' if TWILIO_AUTH_TOKEN else 'Non défini'}")
    print(f"TWILIO_PHONE_NUMBER={TWILIO_PHONE_NUMBER if TWILIO_PHONE_NUMBER else 'Non défini'}")
    
    # Vérification des informations Twilio
    if not TWILIO_ACCOUNT_SID:
        print("ERREUR CRITIQUE: TWILIO_ACCOUNT_SID n'est pas défini")
    if not TWILIO_AUTH_TOKEN:
        print("ERREUR CRITIQUE: TWILIO_AUTH_TOKEN n'est pas défini")
    if not TWILIO_PHONE_NUMBER:
        print("ERREUR CRITIQUE: TWILIO_PHONE_NUMBER n'est pas défini")
    
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
        print("Erreur: Variables d'environnement Twilio manquantes. Vérifiez votre fichier .env")
        return None
    
    try:
        # Initialisation du client Twilio
        print("Initialisation du client Twilio...")
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Création du trunk SIP sur Twilio ou récupération de l'existant
        print("Récupération des trunks existants...")
        trunks = client.sip.trunks.list(limit=20)
        
        if trunks:
            trunk = trunks[0]  # Utiliser le premier trunk existant
            print(f"Utilisation du trunk Twilio existant: {trunk.sid}")
        else:
            # Création d'un nouveau trunk
            print("Création d'un nouveau trunk...")
            trunk = client.sip.trunks.create(friendly_name="LiveKit AI Trunk")
            print(f"Nouveau trunk Twilio créé: {trunk.sid}")
        
        # Configuration du trunk (domaine, etc.)
        domain_name = f"{trunk.sid}.sip.twilio.com"
        
        # Récupération ou création d'une credential list
        print("Récupération des credential lists...")
        credential_lists = client.sip.credential_lists.list(limit=20)
        if credential_lists:
            cred_list = credential_lists[0]
            print(f"Utilisation de la credential list existante: {cred_list.sid}")
        else:
            print("Création d'une nouvelle credential list...")
            cred_list = client.sip.credential_lists.create(friendly_name="LiveKit Credentials")
            # Ajout d'un nouvel identifiant à la liste (vous pouvez personnaliser)
            username = "livekit_user"
            password = "s3cur3p@ssw0rd"
            client.sip.credential_lists(cred_list.sid).credentials.create(
                username=username, password=password
            )
            print(f"Nouvelle credential list créée: {cred_list.sid}")
        
        # Renvoyer les informations du trunk
        print("Configuration Twilio terminée avec succès.")
        return {
            "sid": trunk.sid,
            "domain_name": domain_name,
            "phone_number": TWILIO_PHONE_NUMBER,
            "auth_username": "livekit_user",
            "auth_password": "s3cur3p@ssw0rd"
        }
    
    except Exception as e:
        print(f"Erreur lors de la configuration du trunk Twilio: {e}")
        import traceback
        traceback.print_exc()
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
    print("Initialisation du client LiveKit API...")
    livekit_api = api.LiveKitAPI()
    
    # Déterminer si on utilise un fichier ou Twilio directement
    if trunk_data_file and os.path.exists(trunk_data_file):
        # Chargement des données du trunk depuis le fichier
        print(f"Chargement des données depuis le fichier {trunk_data_file}...")
        with open(trunk_data_file, 'r') as f:
            trunk_config = json.load(f)
        
        # Extraction des informations du trunk
        trunk_info = trunk_config.get('trunk', {})
    else:
        # Obtenir les informations directement de Twilio
        print("Récupération des informations Twilio...")
        twilio_trunk = create_twilio_sip_trunk()
        if not twilio_trunk:
            print("Erreur fatale: Impossible d'obtenir les informations du trunk Twilio.")
            raise Exception("Impossible de configurer le trunk Twilio. Vérifiez vos identifiants.")
        
        # Conversion au format attendu
        print("Conversion des données Twilio au format LiveKit...")
        trunk_info = {
            "name": "Twilio Trunk",
            "address": twilio_trunk["domain_name"],
            "numbers": [twilio_trunk["phone_number"]],
            "auth_username": twilio_trunk["auth_username"],
            "auth_password": twilio_trunk["auth_password"]
        }
    
    # Création de l'objet trunk
    print("Création de l'objet trunk SIP...")
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
        print("Envoi de la requête à LiveKit pour créer le trunk SIP sortant...")
        response = await livekit_api.sip.create_sip_outbound_trunk(request)
        print(f"Trunk SIP sortant créé avec succès: ID = {response.sid}")
        
        # Enregistrement de l'ID du trunk dans le fichier .env
        env_path = os.path.join(root_dir, ".env")
        try:
            print(f"Mise à jour du fichier .env à {env_path}...")
            with open(env_path, 'r') as env_file:
                env_content = env_file.read()
            
            if 'OUTBOUND_TRUNK_ID' in env_content:
                # Mise à jour de la valeur existante
                print("Mise à jour de la variable OUTBOUND_TRUNK_ID existante...")
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
                print("Ajout de la variable OUTBOUND_TRUNK_ID...")
                updated_env = f"{env_content}\nOUTBOUND_TRUNK_ID={response.sid}"
            
            with open(env_path, 'w') as env_file:
                env_file.write(updated_env)
            
            print(f"L'ID du trunk a été enregistré dans le fichier .env")
        except Exception as e:
            print(f"Attention: Impossible de mettre à jour le fichier .env: {e}")
            print(f"Trunk ID: {response.sid} - Pensez à l'ajouter manuellement à vos variables d'environnement.")
        
        return response.sid
    except Exception as e:
        print(f"Erreur lors de la création du trunk SIP: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        print("Fermeture de la connexion LiveKit API...")
        await livekit_api.aclose()

def main():
    parser = argparse.ArgumentParser(description='Créer un trunk SIP sortant dans LiveKit')
    parser.add_argument('--file', '-f', required=False, help='Chemin vers le fichier JSON contenant les informations du trunk')
    parser.add_argument('--twilio', '-t', action='store_true', help='Utiliser directement les informations Twilio')
    args = parser.parse_args()
    
    if args.twilio:
        # Utiliser directement les informations Twilio
        print("Configuration du trunk SIP avec Twilio...")
        asyncio.run(create_outbound_trunk(None))
    elif args.file:
        # Utiliser un fichier de configuration
        print(f"Configuration du trunk SIP avec le fichier {args.file}...")
        asyncio.run(create_outbound_trunk(args.file))
    else:
        print("Erreur: Vous devez spécifier --file ou --twilio")
        parser.print_help()

if __name__ == "__main__":
    main()
