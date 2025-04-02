import asyncio
import os
import logging
import json
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.llm import ChatContext, ChatMessage, FunctionContext
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.agents import AutoSubscribe
from livekit.plugins import deepgram, silero, openai, cartesia
from dotenv import load_dotenv

from outbound_caller import OutboundCaller
from call_actions import CallActions

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG,  # Changez de INFO à DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Affiche les logs dans la console
        logging.FileHandler('agent.log')  # Sauvegarde les logs dans un fichier
    ]
)
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
load_dotenv()

# Trunk ID pour les appels sortants
OUTBOUND_TRUNK_ID = os.getenv("OUTBOUND_TRUNK_ID")

def prewarm(proc):
    """Fonction de préchauffage pour charger les modèles IA à l'avance"""
    # Préchargement du modèle VAD
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    """Point d'entrée principal de l'agent"""
    # Logs détaillés au début de l'entrypoint
    logger.info(f"DEBUT DE L'ENTRYPOINT")
    logger.info(f"Métadonnées du job brutes: {ctx.job.metadata}")
    
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

    try:
        # Extraction du numéro de téléphone à partir des métadonnées
        job_metadata = ctx.job.metadata
        # Essayer de parser les métadonnées comme du JSON
        try:
            metadata_dict = json.loads(job_metadata)
            phone_number = metadata_dict.get('phone_number', None)
            trunk_id = metadata_dict.get('trunk_id', None)
        except json.JSONDecodeError:
            # Si les métadonnées ne sont pas du JSON (cas simple), utiliser directement
            phone_number = job_metadata
            trunk_id = None
        
        logger.info(f"Configuration de l'appel:")
        logger.info(f"Numéro de téléphone: {phone_number}")
        logger.info(f"Trunk ID: {trunk_id}")
        logger.info(f"Room: {ctx.room.name}")

        # Vérification des valeurs extraites
        if not phone_number:
            logger.error("ERREUR CRITIQUE: Numéro de téléphone non trouvé dans les métadonnées")
            ctx.shutdown(reason="Numéro de téléphone manquant")
            return

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
            trunk_id=trunk_id or OUTBOUND_TRUNK_ID
        )
        
        # Démarrage de l'appel
        logger.info(f"Lancement de l'appel vers {phone_number}")
        try:
            # Log détaillé avant le démarrage de l'appel
            logger.info(f"Configuration de l'appel - Room: {ctx.room.name}, Trunk ID: {trunk_id or OUTBOUND_TRUNK_ID}")
            
            participant = await outbound_caller.start_call(phone_number)
            
            # Log après démarrage de l'appel
            logger.info(f"Appel démarré - Participant: {participant.identity}")
            
            # Mise à jour des actions d'appel avec le participant
            call_actions.participant = participant
            
            # Configurer l'agent pour utiliser les actions d'appel
            agent_llm = openai.LLM(
                model="gpt-4o-mini",
