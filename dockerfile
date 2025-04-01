FROM python:3.10-slim

WORKDIR /app

# Installation des dépendances système requises
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copie des fichiers de dépendances d'abord pour profiter du cache Docker
COPY requirements.txt /app/

# Installation des dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

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
CMD ["gunicorn", "--chdir", "api", "app:app", "--bind", "0.0.0.0:8080"]
