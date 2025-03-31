import React, { useState } from 'react';
import CallInterface from './components/CallInterface';
import './styles/App.css';

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  
  const handleLogin = (e) => {
    e.preventDefault();
    
    // Vérification simple des informations d'identification
    if (apiKey && apiSecret) {
      setIsLoggedIn(true);
    } else {
      alert('Veuillez saisir les informations d'API LiveKit');
    }
  };
  
  if (!isLoggedIn) {
    return (
      <div className="container">
        <div className="login-box">
          <h1>Agent Téléphonique IA</h1>
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>API Key</label>
              <input 
                type="text" 
                value={apiKey} 
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Entrez votre clé API LiveKit"
              />
            </div>
            <div className="form-group">
              <label>API Secret</label>
              <input 
                type="password" 
                value={apiSecret} 
                onChange={(e) => setApiSecret(e.target.value)}
                placeholder="Entrez votre secret API LiveKit"
              />
            </div>
            <button type="submit" className="login-button">Se connecter</button>
          </form>
        </div>
      </div>
    );
  }
  
  return (
    <div className="container">
      <header>
        <h1>Agent Téléphonique IA</h1>
        <button className="logout-button" onClick={() => setIsLoggedIn(false)}>
          Déconnexion
        </button>
      </header>
      
      <main>
        <CallInterface apiKey={apiKey} apiSecret={apiSecret} />
      </main>
      
      <footer>
        <p>© 2025 TeleAgent - Démonstration d'agent téléphonique IA</p>
      </footer>
    </div>
  );
}

export default App;
