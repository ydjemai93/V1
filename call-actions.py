import logging
import asyncio
import json
from typing import Annotated, Optional
from livekit.agents.llm import FunctionContext
from livekit.api import RoomParticipantIdentity
from livekit import rtc

logger = logging.getLogger(__name__)

class CallActions(FunctionContext):
    """
    Actions que l'agent peut effectuer pendant un appel téléphonique
    """
    
    def __init__(self, api, participant, room):
        """
        Initialisation des actions d'appel
        
        Args:
            api: Instance API LiveKit
            participant: Participant SIP (peut être None au début)
            room: Room LiveKit actuelle
        """
        super().__init__()
        self.api = api
        self.participant = participant
        self.room = room
    
    async def hangup(self):
        """
        Raccrocher l'appel en cours
        """
        try:
            if not self.participant:
                logger.warning("Tentative de raccrocher alors qu'aucun participant n'est défini")
                return
                
            logger.info(f"Raccrochage de l'appel avec {self.participant.identity}")
            await self.api.room.remove_participant(
                RoomParticipantIdentity(
                    room=self.room.name,
                    identity=self.participant.identity,
                )
            )
        except Exception as e:
            logger.error(f"Erreur lors du raccrochage : {e}")
    
    @FunctionContext.ai_callable()
    async def end_call(self):
        """Called when the user wants to end the call"""
        logger.info(f"Fin de l'appel avec {self.participant.identity}")
        await self.hangup()
    
    @FunctionContext.ai_callable()
    async def detected_voicemail(self):
        """Called when the agent detects it has reached a voicemail instead of a person"""
        logger.info(f"Messagerie vocale détectée pour {self.participant.identity}")
        
        # Attendre un court instant pour laisser le bip sonore se produire
        await asyncio.sleep(1)
        
        # Laisser un message
        return "Voicemail message left"
    
    @FunctionContext.ai_callable()
    async def schedule_callback(self, 
                              time: Annotated[str, "Time to call back"] = None,
                              date: Annotated[str, "Date to call back"] = None):
        """Called when the user requests to be called back at a specific time or date"""
        logger.info(f"Programmation d'un rappel pour {self.participant.identity} à {date} {time}")
        
        # Cette fonction simulerait l'enregistrement d'un rappel dans une base de données
        callback_info = {
            "phone_number": self.participant.identity.replace("phone_user_", ""),
            "date": date,
            "time": time
        }
        
        # Simuler l'enregistrement dans une base de données
        logger.info(f"Rappel programmé: {json.dumps(callback_info)}")
        
        return "Callback scheduled successfully"
    
    @FunctionContext.ai_callable()
    async def transfer_to_human(self, 
                              reason: Annotated[str, "Reason for transferring to a human agent"] = None):
        """Called when the agent needs to transfer the call to a human agent"""
        logger.info(f"Transfert vers un agent humain demandé pour {self.participant.identity}: {reason}")
        
        # Dans une vraie implémentation, ici on pourrait:
        # 1. Placer l'appel dans une file d'attente
        # 2. Notifier un agent humain
        # 3. Transférer l'appel vers un autre système
        
        # Pour cette démonstration, on simule seulement
        return "Transfer to human requested. Note: This is a simulation for demo purposes."
