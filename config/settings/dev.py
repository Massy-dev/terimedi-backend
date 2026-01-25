import os
from .base import *
print("🔥 DEV SETTINGS LOADED 🔥")
GDAL_LIBRARY_PATH = os.getenv("GDAL_LIBRARY_PATH")
GEOS_LIBRARY_PATH = os.getenv("GEOS_LIBRARY_PATH")
FIREBASE_CREDENTIALS = os.path.join(BASE_DIR, "firebase_credentials.json")
# Initialisation Firebase Admin SDK

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Base de données via Docker
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get("POSTGRES_DB", "terimedi"),
        'USER': os.environ.get("POSTGRES_USER", "terimedi"),
        'PASSWORD': os.environ.get("POSTGRES_PASSWORD", "teri_pass"),
        'HOST': os.environ.get("POSTGRES_HOST", "db"),  # Nom du service Docker
        'PORT': os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# Configuration CORS pour le développement
CORS_ALLOW_ALL_ORIGINS = True
"""CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    
]
"""

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL, #"redis://redis:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

#Channel
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    },
}
# Configuration Redis pour Docker
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")  # Nom du service Docker
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")

# Configuration Celery pour Docker
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"

# SÉCURITÉ DÉSACTIVÉE POUR LE DÉVELOPPEMENT
"""REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',  # Permet l'accès sans authentification
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}
"""