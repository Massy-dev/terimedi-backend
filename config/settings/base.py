"""
Configuration de base Django pour TeriMedi
"""
import os
from pathlib import Path
from decouple import config, Csv
import firebase_admin
from firebase_admin import credentials, messaging
import dj_database_url

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ------------------------------------------------------------
# Secrets et Debug
# ------------------------------------------------------------
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)




# ------------------------------------------------------------
# Notifications
# ------------------------------------------------------------
NOTIFICATION_SETTINGS = {
    'FCM_ENABLED': True,
    'WEBSOCKET_ENABLED': True,
    'NOTIFICATION_SOUND': 'default',
    'NOTIFICATION_PRIORITY': 'high',
}



# ------------------------------------------------------------
# Applications Django
# ------------------------------------------------------------
DJANGO_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
]

THIRD_PARTY_APPS = [
    
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_yasg',
    'leaflet',
    'channels',
    
]

LOCAL_APPS = [
    'apps.users',
    'apps.pharmacies',
    'apps.orders',
    'apps.notifications'
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS +  LOCAL_APPS

ASGI_APPLICATION = "config.asgi.application"

# ------------------------------------------------------------
# Channels / Redis
# ------------------------------------------------------------


REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/1')


"""
#Redis
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL, #"redis://redis:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}"""

# ------------------------------------------------------------
# Middleware
# ------------------------------------------------------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',

    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ROOT_URLCONF = 'config.urls'

# ------------------------------------------------------------
# Password validation
# ------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ------------------------------------------------------------
# Internationalization
# ------------------------------------------------------------
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Abidjan'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

#os.makedirs(os.path.join(MEDIA_ROOT, 'prescriptions'), exist_ok=True)
#os.makedirs(os.path.join(MEDIA_ROOT, 'pharmacies/logos/'), exist_ok=True)

# ------------------------------------------------------------
# Default primary key
# ------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ------------------------------------------------------------
# Custom User Model
# ------------------------------------------------------------
AUTH_USER_MODEL = 'users.CustomUser'

# ------------------------------------------------------------
# Django REST Framework
# ------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ------------------------------------------------------------
# JWT Settings
# ------------------------------------------------------------
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
}

# ------------------------------------------------------------
# Email
# ------------------------------------------------------------
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='no-reply@terimedi.local')
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ------------------------------------------------------------
# Leaflet map pour géolocaliser les pharmacie
# ------------------------------------------------------------
LEAFLET_CONFIG = {
    'DEFAULT_CENTER': (5.3600, -4.0083),  # Coordonnées d'Abidjan
    'DEFAULT_ZOOM': 10,
    'MIN_ZOOM': 3,
    'MAX_ZOOM': 18,
    'TILES': [
        ('OpenStreetMap', 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            'attribution': ''#'© OpenStreetMap contributors'
        }),
    ],
    'OVERLAYS': [],
    'ATTRIBUTION_PREFIX': '' #'Powered by Leaflet',
}

# GDAL Configuration
GDAL_LIBRARY_PATH = config('GDAL_LIBRARY_PATH', default='')
