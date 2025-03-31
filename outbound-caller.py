import asyncio
import logging
from livekit import api, rtc
from livekit.protocol.sip import CreateSIPParticipantRequest

logger = logging.getLogger(__name__)

class OutboundCaller:
    """
    Classe gérant les appels sortants via SIP
    """
    
    def __init__(self, api, room, trunk_id):
        """
        Initialisation de l'appelant sortant
        
        Args:
            api: Instance API LiveKit
            room: Room LiveKit actuelle
            trunk_id: ID du trunk SIP sortant
        """
        self.api = api
        self.room = room
        self.trunk_id = trunk_id
    
    async def start_call(self, phone_number, timeout=30):
        """
        Démarrer un appel sortant vers un numéro de téléphone
        
        Args:
            phone_number: Numéro de téléphone à appeler
            timeout: Délai maximum d'attente en secondes
            
        Returns:
            Participant SIP si l'appel est réussi
            
        Raises:
            Exception si l'appel échoue ou expire
        """
        user_identity = f"phone_user_{phone_number}"
        
        logger.info(f"Appel en cours vers {phone_number} via trunk {self.trunk_id}")
        
        # Création de la requête SIP pour passer l'appel
        request = CreateSIPParticipantRequest(
            room_name=self.room.name,
            sip_trunk_id=self.trunk_id,
            sip_call_to=phone_number,
            participant_identity=user_identity,
            participant_name=f"Customer {phone_number}",
            # Jouer une tonalité pendant que l'appel se connecte
            play_dialtone=True,
        )
        
        # Lancement de l'appel via l'API LiveKit
        await self.api.sip.create_sip_participant(request)
        
        # Attente que le participant rejoigne la room
        participant = await self._wait_for_participant_to_join(user_identity, timeout)
        return participant
    
    async def _wait_for_participant_to_join(self, identity, timeout):
        """
        Attendre qu'un participant rejoigne la room
        
        Args:
            identity: Identité du participant
            timeout: Délai maximum d'attente
            
        Returns:
            Participant si trouvé
            
        Raises:
            Exception si le délai est dépassé
        """
        start_time = asyncio.get_event_loop().time()
        
        # Vérifier si le participant existe déjà
        for p in self.room.remote_participants.values():
            if p.identity == identity:
                return p
        
        # Configurer un event pour la connexion du participant
        participant_connected_event = asyncio.Event()
        
        # Définir la callback pour l'événement de connexion
        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.Participant, *_):
            if participant.identity == identity:
                participant_connected_event.set()
        
        # Attendre que le participant se connecte ou que le délai expire
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                await asyncio.wait_for(participant_connected_event.wait(), 1)
                # Participant connecté, retourner l'instance
                for p in self.room.remote_participants.values():
                    if p.identity == identity:
                        return p
            except asyncio.TimeoutError:
                # Vérifier si l'appel a échoué
                for p in self.room.remote_participants.values():
                    if p.identity == identity:
                        return p
            await asyncio.sleep(0.1)
        
        # Le délai a expiré sans que le participant ne se connecte
        raise Exception(f"Délai d'attente dépassé pour que {identity} rejoigne l'appel")
    
    async def monitor_call_status(self, participant, check_interval=0.5):
        """
        Surveiller l'état d'un appel en cours
        
        Args:
            participant: Participant SIP à surveiller
            check_interval: Intervalle entre les vérifications en secondes
        """
        while True:
            # Vérifier si le participant est toujours connecté
            if participant.identity not in self.room.remote_participants:
                logger.info(f"Le participant {participant.identity} a quitté la room")
                return
            
            # Vérifier l'état de l'appel via les attributs du participant
            call_status = participant.attributes.get("sip.callStatus")
            
            if call_status == "active":
                # L'appel est actif, continuer à surveiller
                pass
            elif call_status == "hangup":
                logger.info(f"L'appel avec {participant.identity} a été raccroché")
                return
            elif call_status == "automation":
                # DTMF en cours, continuer à surveiller
                pass
            
            await asyncio.sleep(check_interval)
    
    async def end_call(self, participant):
        """
        Terminer un appel en cours
        
        Args:
            participant: Participant SIP à déconnecter
        """
        try:
            await self.api.room.remove_participant(
                api.RoomParticipantIdentity(
                    room=self.room.name,
                    identity=participant.identity,
                )
            )
            logger.info(f"Appel avec {participant.identity} terminé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de la terminaison de l'appel : {e}")
