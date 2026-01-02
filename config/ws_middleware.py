# apps/core/ws_middleware.py

from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from rest_framework_simplejwt.backends import TokenBackend
from channels.db import database_sync_to_async

User = get_user_model()


class JwtAuthMiddleware(BaseMiddleware):
    """
    Middleware d'authentification WebSocket utilisant JWT (SimpleJWT).
    Il récupère le token dans :
        - query string : /ws/orders/?token=xxx
        - header : Sec-WebSocket-Protocol: token
    """

    async def __call__(self, scope, receive, send):
        close_old_connections()

        scope["user"] = None
        token = self._extract_token(scope)

        if token:
            user = await self._authenticate(token)
            scope["user"] = user

        return await super().__call__(scope, receive, send)

    def _extract_token(self, scope):
        query_string = scope.get("query_string", b"").decode()
        qs = parse_qs(query_string)

        # 1) Token dans la query string
        if "token" in qs:
            return qs["token"][0]

        # 2) Token dans l’en-tête `sec-websocket-protocol`
        headers = dict(scope.get("headers", []))
        proto = headers.get(b"sec-websocket-protocol")
        if proto:
            try:
                proto = proto.decode()
                return proto.split(",")[0].strip()
            except Exception:
                return None

        return None

    async def _authenticate(self, token: str):
        """
        Valide le JWT via TokenBackend (SimpleJWT).
        """
        try:
            backend = TokenBackend(algorithm="HS256")
            decoded = backend.decode(token, verify=True)

            user_id = decoded.get("user_id")
            if not user_id:
                return None

            return await database_sync_to_async(User.objects.get)(id=user_id)

        except Exception:
            return None
