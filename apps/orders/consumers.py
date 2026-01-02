# apps/orders/consumers.py

import json
from typing import List, Optional

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

from apps.pharmacies.models import Pharmacy  # adapte si ton emplacement est différent
from apps.orders.models import Commande  # optionnel, si tu veux vérifier droits

User = get_user_model()


class OrderConsumer(AsyncJsonWebsocketConsumer):
    """
    Consumer WebSocket pour événements liés aux commandes.
    - Authentification : via JwtAuthMiddleware (scope['user'] rempli)
    - Groupes :
        - user_{user.id}  (notifications ciblées utilisateur)
        - pharmacy_{pharmacy_id} (notifications pour toutes les personnes reliées à une pharmacie)
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or getattr(user, "is_anonymous", True):
            # Refuse la connexion si non authentifié
            await self.close(code=4401)
            return

        # Groupes auxquels s'abonner
        self.user_group = f"user_{user.id}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        # Si l'utilisateur est pharmacien, abonne-le aux groupes des pharmacies qu'il gère
        self.pharmacy_groups: List[str] = []
        user_role = getattr(user, "role", None)
        if user_role in ("pharmacien", "pharmacy", "pharmacist"):
            # Récupère les pharmacies liées à l'utilisateur
            try:
                pharmacies = await self._get_user_pharmacies(user)
                for pid in pharmacies:
                    group_name = f"pharmacy_{pid}"
                    await self.channel_layer.group_add(group_name, self.channel_name)
                    self.pharmacy_groups.append(group_name)
            except Exception:
                # en cas d'erreur, on continue sans throw
                pass

        await self.accept()

    async def disconnect(self, close_code):
        # Retire de tous les groupes
        try:
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
        except Exception:
            pass

        for g in getattr(self, "pharmacy_groups", []):
            try:
                await self.channel_layer.group_discard(g, self.channel_name)
            except Exception:
                pass

    async def receive_json(self, content, **kwargs):
        """
        Réception d'un message JSON du client.
        On gère ici uniquement des actions simples (ping, join order room, etc.).
        """
        action = content.get("action")

        if action == "ping":
            await self.send_json({"type": "pong"})
            return

        if action == "join_order":
            # rejoindre un groupe d'ordre spécifique (optionnel)
            order_id = content.get("order_id")
            if order_id:
                group = f"order_{order_id}"
                await self.channel_layer.group_add(group, self.channel_name)
                await self.send_json({"type": "joined", "group": group})
            return

        # autres actions possibles à implémenter
        await self.send_json({"type": "error", "message": "action inconnue"})

    # -----------------------------
    # Méthodes appelées par group_send (server -> consumer)
    # -----------------------------
    async def order_event(self, event):
        """
        Handler invoked when the server does:
        channel_layer.group_send(group, {"type": "order.event", "event": "...", "data": {...}})
        Note: Channels converts "order.event" -> order_event method name.
        """
        # event contient typiquement : {"type": "order.event", "event": "order_created", "data": {...}}
        # On renvoie le payload tel quel au client
        payload = {
            "type": event.get("event", "order_event"),
            "data": event.get("data", {}),
        }
        await self.send_json(payload)

    # Si tu veux traiter d'autres types, ajoute d'autres méthodes correspondantes
    # par exemple : def order_update(self, event): ...

    # -----------------------------
    # Helpers
    # -----------------------------
    @database_sync_to_async
    def _get_user_pharmacies(self, user: User) -> List[int]:
        """
        Retourne la liste des ids de pharmacies associées à l'utilisateur.
        Adapte selon ton modèle de relation (user.pharmacies ou autre).
        """
        # Exemple : si relation ManyToManyField named 'pharmacies'
        try:
            qs = user.pharmacies.all().values_list("id", flat=True)
            return list(qs)
        except Exception:
            # tentative alternative : relation inverse ou FK
            try:
                qs = Pharmacy.objects.filter(manager=user).values_list("id", flat=True)
                return list(qs)
            except Exception:
                return []
