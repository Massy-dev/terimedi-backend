import os
from .base import *

GDAL_LIBRARY_PATH = os.getenv("GDAL_LIBRARY_PATH")
GEOS_LIBRARY_PATH = os.getenv("GEOS_LIBRARY_PATH")
#ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=Csv())
#ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")
ALLOWED_HOSTS="terimedi-backend-production.up.railway.app","localhost","127.0.0.1"

"""if not ALLOWED_HOSTS:

    RAILWAY_STATIC_URL = os.getenv('RAILWAY_STATIC_URL', '')
    if RAILWAY_STATIC_URL:
        ALLOWED_HOSTS = [RAILWAY_STATIC_URL.replace('https://', '').replace('http://', '')]
    ALLOWED_HOSTS.append('*.railway.app')"""
#os.environ.get("DJANGO_ALLOWED_HOSTS").split(" ")

# DB sécurisée
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL'),
        conn_max_age=600,
        
    )
}

# Redis URL
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379')

# Channel Layers - Railway Redis
if REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [REDIS_URL],
            },
        },
    }

else:
    # Fallback sans Redis (temporaire)
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer'
        }
    }

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}





# CORS Configuration
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000',
    cast=Csv()
)


# En production, n'autorisez que les domaines spécifiques
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Firebase Configuration



import json
FIREBASE_CREDENTIALS = config('FIREBASE_CREDENTIALS', default=None)

if not firebase_admin._apps:
    if FIREBASE_CREDENTIALS:
        # En production : utiliser la variable d'environnement
        try:
            cred_dict = json.loads(FIREBASE_CREDENTIALS)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            print(f"Firebase init error: {e}")
    else:
        firebase_path  = os.path.join(BASE_DIR, "firebase_credentials.json")

        if os.path.exists(firebase_path ):
            cred = credentials.Certificate(firebase_path )
            firebase_admin.initialize_app(cred)
   

# Notification Settings
NOTIFICATION_SETTINGS = {
    'FCM_ENABLED': True,
    'WEBSOCKET_ENABLED': True,
    'NOTIFICATION_SOUND': 'default',
    'NOTIFICATION_PRIORITY': 'high',
}

## ============================
# SECURITY SETTINGS (PROD)
# ============================

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    CSRF_TRUSTED_ORIGINS = [
        "https://*.railway.app",
    ]
    

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}