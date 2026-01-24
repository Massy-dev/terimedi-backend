import os
from .base import *
print("🔥 PROD SETTINGS LOADED 🔥")
GDAL_LIBRARY_PATH = os.getenv("GDAL_LIBRARY_PATH")
GEOS_LIBRARY_PATH = os.getenv("GEOS_LIBRARY_PATH")


# DB sécurisée
DATABASE_URL = os.environ.get('DATABASE_URL')

print("databse_url---",DATABASE_URL)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        ssl_require=True,
        engine="django.contrib.gis.db.backends.postgis",
    )
}

print(f"✅ Using PostgreSQL (Host: {DATABASES['default']['HOST']})")

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
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}





# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "https://terimedi-frontend.vercel.app",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    "authorization",
    "content-type",
    "accept",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])
#CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', cast=lambda v: [s.strip() for s in v.split(',')])
CSRF_TRUSTED_ORIGINS=[
    "https://terimedi-frontend.vercel.app",
    "https://terimedi-backend-production.up.railway.app",
    ]
#CSRF_TRUSTED_ORIGINS="https://terimedi-backend-production.up.railway.app"
#CORS_ALLOWED_ORIGINS="https://terimedi-backend-production.up.railway.app,https://*.railway.app,http://127.0.0.1:3000,http://localhost:3000"


FIREBASE_CREDENTIALS = config('FIREBASE_CREDENTIALS', default=None)
# En production, n'autorisez que les domaines spécifiques
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Firebase Configuration






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