FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 


# Créer le répertoire de travail
WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copier les requirements
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copier le projet
COPY . .

# Créer les dossiers nécessaires
RUN mkdir -p staticfiles media
RUN python manage.py collectstatic --noinput || true

EXPOSE $PORT

CMD python manage.py migrate --noinput && \
    daphne -b 0.0.0.0 -p 8000 config.asgi:application