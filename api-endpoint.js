// Ce fichier serait à placer dans le dossier api/ d'un projet Next.js
// pour servir d'API endpoint pour déclencher des appels

import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import fs from 'fs';

const execPromise = promisify(exec);

export default async function handler(req, res) {
  // Vérifier la méthode HTTP
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Méthode non autorisée' });
  }

  // Récupérer les paramètres de requête  
  const { phone, apiKey, apiSecret } = req.query;
  
  if (!phone || !apiKey || !apiSecret) {
    return res.status(400).json({ error: 'Paramètres manquants' });
  }
  
  try {
    // Créer un fichier .env temporaire pour le script Python
    const envContent = `LIVEKIT_API_KEY=${apiKey}\nLIVEKIT_API_SECRET=${apiSecret}\n`;
    const tempEnvPath = path.join(process.cwd(), 'temp.env');
    
    fs.writeFileSync(tempEnvPath, envContent);
    
    // Chemin vers le script Python
    const scriptPath = path.join(process.cwd(), '..', 'scripts', 'setup_dispatch.py');
    
    // Exécuter le script Python avec les paramètres corrects
    const { stdout, stderr } = await execPromise(
      `python ${scriptPath} --phone "${phone}" --env ${tempEnvPath}`
    );
    
    // Analyser la sortie pour extraire les informations de l'appel
    const roomMatch = stdout.match(/Room: ([a-zA-Z0-9_-]+)/);
    const dispatchMatch = stdout.match(/ID: ([a-zA-Z0-9_-]+)/);
    
    const roomName = roomMatch ? roomMatch[1] : 'unknown';
    const dispatchId = dispatchMatch ? dispatchMatch[1] : 'unknown';
    
    // Supprimer le fichier .env temporaire
    fs.unlinkSync(tempEnvPath);
    
    // Renvoyer les informations de l'appel
    return res.status(200).json({
      success: true,
      roomName,
      dispatchId,
      message: 'Appel initié avec succès'
    });
    
  } catch (error) {
    console.error('Erreur lors de l\'exécution du script:', error);
    
    // Supprimer le fichier .env temporaire s'il existe
    try {
      const tempEnvPath = path.join(process.cwd(), 'temp.env');
      if (fs.existsSync(tempEnvPath)) {
        fs.unlinkSync(tempEnvPath);
      }
    } catch (e) {
      console.error('Erreur lors de la suppression du fichier .env temporaire:', e);
    }
    
    return res.status(500).json({
      error: 'Erreur lors de l\'initiation de l\'appel',
      details: error.message
    });
  }
}
