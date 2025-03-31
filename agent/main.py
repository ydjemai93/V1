import asyncio
import os
import logging
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.llm import ChatContext, ChatMessage, FunctionContext
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.agents import AutoSubscribe
from livekit.plugins import deepgram, silero, openai, cartesia
from dotenv import load_dotenv

from outbound_caller import OutboundCaller
from call_actions import CallActions

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
load_dotenv()

# Trunk ID pour les appels sortants
OUTBOUND_TRUNK_ID = os.getenv("OUTBOUND_TRUNK_ID")

# Informations Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

def prewarm(proc):
    """Fonction de préchauffage pour charger les modèles IA à l'avance"""
    # Préchargement du modèle VAD
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    """Point d'entrée principal de l'agent"""
    logger.info(f"Agent démarré, connexion à la room {ctx.room.name}")
    
    # Initialisation du contexte de conversation
    initial_ctx = ChatContext().append(
        role="system",
        content=(
            "Vous êtes un assistant téléphonique professionnel. "
            "Vous parlez de manière naturelle et concise. "
            "Vous êtes poli et serviable. "
            "Vous êtes capable de comprendre les demandes des clients et d'y répondre efficacement. "
            "Évitez d'utiliser des formulations robotiques comme 'je suis un assistant IA'. "
            "Si le client pose une question complexe, demandez poliment plus de détails."
        ),
    )

    # Numéro de téléphone à appeler (fourni dans les métadonnées du job)
    phone_number = ctx.job.metadata
    logger.info(f"Numéro de téléphone à appeler: {phone_number}")

    # Initialisation de l'agent vocal
    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(model="sonic-2"),  # Utilisation de Cartesia pour la synthèse vocale
        chat_ctx=initial_ctx,
        allow_interruptions=True,
    )

    # Initialisation des actions d'appel
    call_actions = CallActions(api=ctx.api, participant=None, room=ctx.room)
    
    # Connexion à la room LiveKit
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    # Initialisation de l'appelant
    outbound_caller = OutboundCaller(
        api=ctx.api,
        room=ctx.room,
        trunk_id=OUTBOUND_TRUNK_ID
    )
    
    # Démarrer l'appel
    logger.info(f"Lancement de l'appel vers {phone_number}")
    try:
        participant = await outbound_caller.start_call(phone_number)
        
        # Mise à jour des actions d'appel avec le participant
        call_actions.participant = participant
        
        # Configurer l'agent pour utiliser les actions d'appel
        agent_llm = openai.LLM(
            model="gpt-4o-mini",
            fnc_ctx=call_actions,
        )
        agent.llm = agent_llm
        
        # Démarrage de l'agent vocal
        agent.start(ctx.room, participant)
        
        # Premier message de l'agent
        intro_message = (
            f"Bonjour, je suis votre assistant virtuel. "
            f"Comment puis-je vous aider aujourd'hui?"
        )
        await agent.say(intro_message, allow_interruptions=True)
        
        # Surveillance de l'état de l'appel
        call_monitoring_task = asyncio.create_task(
            outbound_caller.monitor_call_status(participant)
        )
        
        # Attendre la fin de l'appel
        await call_monitoring_task
        
    except Exception as e:
        logger.error(f"Erreur lors de l'appel : {e}")
        ctx.shutdown(reason=f"Erreur d'appel: {e}")

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            # Désactivation de la répartition automatique pour utiliser l'API de dispatch explicite
            agent_name="outbound-caller",
        )
    )
