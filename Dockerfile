FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV GDAL_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/libgdal.so

WORKDIR /app

# Mise à jour des sources de packages et installation des dépendances système
RUN apt-get update && apt-get install -y \
        libpq-dev \
        postgresql-client \
        gcc \
        g++ \
        make \
        python3-dev \
        cmake \
        git \
        libgeos-dev \
        libproj-dev \
        proj-bin \
        proj-data \
        libgdal-dev \
        gdal-bin \
        libspatialindex-dev \
        libffi-dev \
        libssl-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*



# Spécifier les variables d'environnement pour GDAL
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
ENV PROJ_LIB=/usr/share/proj

RUN mkdir -p media/prescriptions/
RUN mkdir -p media/pharmacies/logos/
RUN chmod -R 777 media




# Copier et installer les requirements
COPY requirements ./requirements/
RUN pip install --upgrade pip 
RUN pip install -r requirements/dev.txt
RUN pip install channels channels_redis
# Copier le code source
COPY . .

# Créer les dossiers nécessaires
RUN mkdir -p staticfiles media

# Collecter les fichiers statiques
RUN python manage.py collectstatic --noinput || true


# Donner tous les droits d'écriture sur les migrations
RUN find /app/apps -type d -name "migrations" -exec chmod -R 777 {} \; && chmod -R 777 /app

# Créer un utilisateur non-root pour la sécurité
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
USER appuser

# Exposition du port
EXPOSE 8000



# Script de démarrage
#COPY --chmod=755 start.sh /start.sh
#RUN chmod +x /start.sh

# Commande par défaut
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

