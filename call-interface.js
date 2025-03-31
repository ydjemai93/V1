import React, { useState } from 'react';
import '../styles/CallInterface.css';

function CallInterface({ apiKey, apiSecret }) {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [callStatus, setCallStatus] = useState('idle'); // idle, calling, active, ended
  const [callHistory, setCallHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  
  // Fonction pour appeler l'API de backend pour lancer un appel
  const makeCall = async () => {
    if (!phoneNumber || phoneNumber.length < 10) {
      alert('Veuillez saisir un numéro de téléphone valide');
      return;
    }
    
    try {
      setIsLoading(true);
      setCallStatus('calling');
      
      // Construction de l'URL de l'API avec paramètres d'authentification
      const apiUrl = `/api/call?phone=${encodeURIComponent(phoneNumber)}&apiKey=${encodeURIComponent(apiKey)}&apiSecret=${encodeURIComponent(apiSecret)}`;
      
      const response = await fetch(apiUrl, {
        method: 'POST',
      });
      
      if (!response.ok) {
        throw new Error(`Erreur lors de l'appel: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Ajout à l'historique des appels
      const newCall = {
        id: Date.now().toString(),
        phoneNumber,
        timestamp: new Date().toISOString(),
        status: 'active',
        roomName: data.roomName
      };
      
      setCallHistory([newCall, ...callHistory]);
      setCallStatus('active');
      
      // Simuler un appel qui dure quelques secondes (pour la démo)
      setTimeout(() => {
        setCallStatus('ended');
        
        // Mise à jour de l'historique avec le statut terminé
        setCallHistory(prevHistory => 
          prevHistory.map(call => 
            call.id === newCall.id ? { ...call, status: 'ended' } : call
          )
        );
      }, 60000); // 60 secondes
      
    } catch (error) {
      console.error('Erreur:', error);
      setCallStatus('error');
      alert(`Erreur: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };
  
  // Fonction pour gérer la soumission du formulaire
  const handleSubmit = (e) => {
    e.preventDefault();
    makeCall();
  };
  
  return (
    <div className="call-interface">
      <div className="call-panel">
        <h2>Passer un appel</h2>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="phoneNumber">Numéro de téléphone</label>
            <input 
              id="phoneNumber"
              type="tel" 
              value={phoneNumber} 
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder="+33612345678"
              disabled={callStatus === 'calling' || callStatus === 'active'}
            />
          </div>
          
          <button 
            type="submit" 
            className="call-button"
            disabled={isLoading || callStatus === 'calling' || callStatus === 'active'}
          >
            {isLoading ? 'Appel en cours...' : 'Appeler'}
          </button>
        </form>
        
        <div className={`call-status ${callStatus}`}>
          {callStatus === 'idle' && <p>Prêt à appeler</p>}
          {callStatus === 'calling' && <p>Appel en cours...</p>}
          {callStatus === 'active' && <p>Appel en cours avec {phoneNumber}</p>}
          {callStatus === 'ended' && <p>Appel terminé</p>}
          {callStatus === 'error' && <p>Erreur lors de l'appel</p>}
        </div>
      </div>
      
      <div className="history-panel">
        <h2>Historique des appels</h2>
        
        {callHistory.length === 0 ? (
          <p className="no-calls">Aucun appel effectué</p>
        ) : (
          <ul className="call-list">
            {callHistory.map(call => (
              <li key={call.id} className={`call-item ${call.status}`}>
                <div className="call-info">
                  <span className="call-number">{call.phoneNumber}</span>
                  <span className="call-time">
                    {new Date(call.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <div className="call-status-badge">
                  {call.status === 'active' && 'En cours'}
                  {call.status === 'ended' && 'Terminé'}
                  {call.status === 'error' && 'Erreur'}
                </div>
                <div className="call-room">
                  Room: {call.roomName}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default CallInterface;
