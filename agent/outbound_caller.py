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
        # Logs détaillés de l'appel
        logger.info(f"====== DÉMARRAGE DE L'APPEL ======")
        logger.info(f"Détails de l'appel:")
        logger.info(f"Numéro de téléphone: {phone_number}")
        logger.info(f"Trunk ID: {self.trunk_id}")
        logger.info(f"Room Name: {self.room.name}")

        # Vérification du format du numéro de téléphone
        if not phone_number.startswith('+'):
            logger.warning(f"Le numéro de téléphone {phone_number} ne commence pas par '+'. Ajout du préfixe...")
            phone_number = f"+{phone_number}"
        
        # Supprimer les caractères spéciaux comme tirets ou espaces
        phone_number = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        logger.info(f"Numéro formaté pour l'appel: {phone_number}")
        
        if not phone_number:
            logger.error("ERREUR: Numéro de téléphone manquant")
            raise ValueError("Numéro de téléphone requis pour passer un appel")

        if not self.trunk_id:
            logger.error("ERREUR: Trunk ID manquant")
            raise ValueError("Trunk ID requis pour passer un appel")

        user_identity = f"phone_user_{phone_number}"
        
        logger.info(f"Préparation de l'appel vers {phone_number} via trunk {self.trunk_id}")
        
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
        
        try:
            # Lancement de l'appel via l'API LiveKit
            logger.info(f"Envoi de la requête à LiveKit SIP: {request}")
            sip_response = await self.api.sip.create_sip_participant(request)
            logger.info(f"Réponse SIP reçue: {sip_response}")
            
            # Attente que le participant rejoigne la room
            participant = await self._wait_for_participant_to_join(user_identity, timeout)
            
            logger.info(f"Appel réussi. Participant: {participant.identity}")
            return participant
        
        except Exception as e:
            logger.error(f"ERREUR lors du démarrage de l'appel: {e}")
            logger.exception("Détails de l'erreur:")
            raise
    
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
                logger.info(f"Participant {identity} déjà présent")
                return p
        
        # Configurer un event pour la connexion du participant
        participant_connected_event = asyncio.Event()
        
        # Définir la callback pour l'événement de connexion
        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.Participant, *_):
            logger.info(f"Participant connecté: {participant.identity}")
            if participant.identity == identity:
                participant_connected_event.set()
        
        # Attendre que le participant se connecte ou que le délai expire
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                logger.info(f"En attente de connexion pour {identity}")
                await asyncio.wait_for(participant_connected_event.wait(), 1)
                
                # Participant connecté, retourner l'instance
                for p in self.room.remote_participants.values():
                    if p.identity == identity:
                        logger.info(f"Participant {identity} trouvé")
                        return p
            except asyncio.TimeoutError:
                # Vérifier si l'appel a échoué
                for p in self.room.remote_participants.values():
                    if p.identity == identity:
                        logger.info(f"Participant {identity} trouvé malgré le timeout")
                        return p
            
            await asyncio.sleep(0.1)
        
        # Le délai a expiré sans que le participant ne se connecte
        logger.error(f"Délai d'attente dépassé pour {identity}")
        raise Exception(f"Délai d'attente dépassé pour que {identity} rejoigne l'appel")
    
    async def monitor_call_status(self, participant, check_interval=0.5):
        """
        Surveiller l'état d'un appel en cours
        
        Args:
            participant: Participant SIP à surveiller
            check_interval: Intervalle entre les vérifications en secondes
        """
        try:
            logger.info(f"Début de la surveillance de l'appel pour {participant.identity}")
            
            # Ajouter un compteur pour afficher les attributs périodiquement
            counter = 0
            
            while True:
                # Vérifier si le participant est toujours connecté
                if participant.identity not in self.room.remote_participants:
                    logger.info(f"Le participant {participant.identity} a quitté la room")
                    return
                
                # Récupérer le participant à jour (au cas où il aurait été mis à jour)
                participant = self.room.remote_participants.get(participant.identity)
                
                # Vérifier tous les attributs du participant
                if counter % 10 == 0:  # Afficher les détails toutes les 5 secondes environ
                    logger.info(f"Attributs du participant {participant.identity}:")
                    for attr_name, attr_value in participant.attributes.items():
                        logger.info(f"  {attr_name}: {attr_value}")
                
                # Vérifier l'état de l'appel via les attributs du participant
                call_status = participant.attributes.get("sip.callStatus")
                
                logger.debug(f"Statut de l'appel: {call_status}")
                
                if call_status == "active":
                    # L'appel est actif, continuer à surveiller
                    if counter % 10 == 0:
                        logger.info(f"L'appel est actif avec {participant.identity}")
                elif call_status == "hangup":
                    logger.info(f"L'appel avec {participant.identity} a été raccroché")
                    return
                elif call_status == "terminated":
                    logger.info(f"L'appel avec {participant.identity} est terminé")
                    return
                elif call_status == "automating":
                    # L'appel est en cours de numérotation, par exemple pour les extensions DTMF
                    if counter % 10 == 0:
                        logger.info(f"L'appel est en cours de numérotation (DTMF) pour {participant.identity}")
                elif call_status is None:
                    if counter % 10 == 0:
                        logger.warning(f"L'attribut sip.callStatus est absent pour {participant.identity}")
                else:
                    logger.info(f"Statut d'appel détecté: {call_status}")
                    
                counter += 1
                await asyncio.sleep(check_interval)
        except Exception as e:
            logger.error(f"Erreur lors de la surveillance de l'appel : {e}")
            logger.exception("Détails de l'erreur:")
    
    async def end_call(self, participant):
        """
        Terminer un appel en cours
        
        Args:
            participant: Participant SIP à déconnecter
        """
        try:
            logger.info(f"Tentative de fin d'appel pour {participant.identity}")
            await self.api.room.remove_participant(
                api.RoomParticipantIdentity(
                    room=self.room.name,
                    identity=participant.identity,
                )
            )
            logger.info(f"Appel avec {participant.identity} terminé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de la terminaison de l'appel : {e}")
            logger.exception("Détails de l'erreur:")
