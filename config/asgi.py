"""
ASGI config pour TeriMedi project.
Gère à la fois HTTP et WebSocket
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

# Initialiser Django ASGI application tôt pour charger les apps
django_asgi_app = get_asgi_application()

# Import après l'initialisation Django
from apps.notifications.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # Django's ASGI application pour gérer les requêtes HTTP traditionnelles
    "http": django_asgi_app,
    
    # WebSocket handler
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})