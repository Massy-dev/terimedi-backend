FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

# Créer le répertoire de travail
WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copier les requirements
COPY requirements/ requirements/

# Installer les dépendances Python
RUN pip install --upgrade pip && \
    pip install -r requirements/base.txt

# Copier le projet
COPY . .

# Créer les dossiers nécessaires
RUN mkdir -p staticfiles media

# Collecter les fichiers statiques
RUN python manage.py collectstatic --noinput || true

# Exposer le port (Railway utilise la variable $PORT)
EXPOSE $PORT

# Script de démarrage qui exécute les migrations puis lance Daphne
ENTRYPOINT ["sh", "-c"]
CMD "python manage.py migrate --noinput && python manage.py collectstatic --noinput && daphne -b 0.0.0.0 -p ${PORT} config.asgi:application"

#COPY entrypoint.sh /entrypoint.sh
#RUN chmod +x /entrypoint.sh
#CMD ["/entrypoint.sh"]

#CMD ["/bin/sh", "-c", "daphne -b 0.0.0.0 -p ${PORT} config.asgi:application"]

#CMD daphne -b 0.0.0.0 -p  $PORT config.asgi:application

#CMD ["python", "start.py"]
