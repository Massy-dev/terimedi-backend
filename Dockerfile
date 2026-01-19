FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 


# Créer le répertoire de travail
WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    build-essential \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*


# Variable d’environnement requise par GeoDjango
ENV GDAL_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/libgdal.so
ENV GEOS_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/libgeos_c.so


# Copier les requirements
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copier le projet
COPY . .


# Créer les dossiers nécessaires
RUN mkdir -p staticfiles media

# Entrypoint
#COPY entrypoint.sh /entrypoint.sh
#RUN chmod +x /entrypoint.sh

#ENTRYPOINT ["/entrypoint.sh"]

RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "========================================"\n\
echo "🚀 Starting TeriMedi Backend"\n\
echo "========================================"\n\
echo ""\n\
\n\
# Vérifier les variables d'\''environnement\n\
echo "📋 Environment Variables:"\n\
echo "  PORT: $PORT"\n\
echo "  DEBUG: $DEBUG"\n\
echo "  ALLOWED_HOSTS: $ALLOWED_HOSTS"\n\
echo "  DATABASE_URL: ${DATABASE_URL:0:30}..."\n\
if [ -n "$REDIS_URL" ]; then\n\
  echo "  REDIS_URL: ${REDIS_URL:0:30}..."\n\
else\n\
  echo "  REDIS_URL: (not set - using InMemory)"\n\
fi\n\
echo ""\n\
\n\
# Exécuter les migrations avec logs détaillés\n\
echo "========================================"\n\
echo "📊 Running database migrations..."\n\
echo "========================================"\n\
python manage.py migrate --noinput --verbosity 2 || {\n\
  echo "❌ Migration failed!"\n\
  exit 1\n\
}\n\
echo ""\n\
echo "✅ Migrations completed successfully"\n\
echo ""\n\
\n\
# Afficher les tables créées\n\
echo "📋 Database tables:"\n\
python manage.py showmigrations --list | head -20\n\
echo ""\n\
\n\
# Démarrer Daphne\n\
echo "========================================"\n\
echo "🌐 Starting Daphne server on port $PORT"\n\
echo "========================================"\n\
exec daphne -b 0.0.0.0 -p $PORT config.asgi:application\n\
' > /app/start.sh && chmod +x /app/start.sh

# Utiliser le script de démarrage
CMD ["/start.sh"]