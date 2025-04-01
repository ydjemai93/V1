import asyncio
import argparse
import os
from dotenv import load_dotenv
from livekit import api

# Charger les variables d'environnement du fichier spécifié ou de .env par défaut
def load_env_file(env_file=None):
    if env_file and os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        # Chercher le fichier .env à la racine du projet
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        env_path = os.path.join(root_dir, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
        else:
            # Fallback au comportement par défaut
            load_dotenv()

async def create_dispatch(phone_number, env_file=None):
    """
    Crée un dispatch pour l'agent d'appels sortants avec un numéro de téléphone cible
    
    Args:
        phone_number: Numéro de téléphone à appeler
        env_file: Fichier .env spécifique à utiliser
    """
    # Charger les variables d'environnement
    load_env_file(env_file)
    
    # Initialisation du client LiveKit
    livekit_api = api.LiveKitAPI()
    
    try:
        # Création d'un nouveau dispatch pour l'agent
        response = await livekit_api.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name="outbound-caller",
                # Création d'une nouvelle room pour cet appel
                new_room=True,
                # Passage du numéro de téléphone comme métadonnée
                metadata=phone_number
            )
        )
        
        room_name = response.room
        dispatch_id = response.id
        
        print(f"Dispatch créé avec succès:")
        print(f"  ID: {dispatch_id}")
        print(f"  Room: {room_name}")
        print(f"  L'agent va appeler le numéro: {phone_number}")
        
        # Surveiller le statut de la room (optionnel)
        print("L'appel est en cours. Appuyez sur Ctrl+C pour quitter...")
        
        while True:
            # Vérifier périodiquement si la room existe encore
            try:
                room_info = await livekit_api.room.list_rooms(
                    api.ListRoomsRequest(names=[room_name])
                )
                if not room_info.rooms:
                    print("L'appel est terminé (la room n'existe plus)")
                    break
                await asyncio.sleep(2)
            except KeyboardInterrupt:
                print("Surveillance interrompue par l'utilisateur")
                break
            except Exception as e:
                print(f"Erreur lors de la vérification de la room: {e}")
                break
    
    except Exception as e:
        print(f"Erreur lors de la création du dispatch: {e}")
    finally:
        await livekit_api.aclose()

def main():
    parser = argparse.ArgumentParser(description='Créer un dispatch pour passer un appel sortant')
    parser.add_argument('--phone', '-p', required=True, help='Numéro de téléphone à appeler')
    parser.add_argument('--env', '-e', help='Fichier .env à utiliser (optionnel)')
    args = parser.parse_args()
    
    asyncio.run(create_dispatch(args.phone, args.env))

if __name__ == "__main__":
    main()
