FROM python:3.10-slim

WORKDIR /app

# Installation des dépendances système requises
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copie du requirements.txt à la racine
COPY requirements.txt /app/

# Installation des dépendances Python avec des versions spécifiques
RUN pip install --no-cache-dir flask==2.0.1 werkzeug==2.0.1
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copie des fichiers du projet
COPY agent/ /app/agent/
COPY scripts/ /app/scripts/
COPY api/ /app/api/

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Exposition du port
EXPOSE 8080

# Commande de démarrage
CMD ["gunicorn", "--chdir", "api", "-b", "0.0.0.0:8080", "app:app"]
