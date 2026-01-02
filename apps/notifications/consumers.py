import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User

class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Consumer pour gérer les connexions WebSocket des notifications en temps réel
    """
    
    async def connect(self):
        """Appelé quand un client se connecte"""
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room_group_name = f'notifications_{self.user_id}'
        
        # Vérifier si l'utilisateur existe
        user_exists = await self.check_user_exists(self.user_id)
        
        if not user_exists:
            await self.close()
            return
        
        # Rejoindre le groupe de notifications de l'utilisateur
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Envoyer un message de confirmation de connexion
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': f'Connecté au canal de notifications pour user {self.user_id}'
        }))
    
    async def disconnect(self, close_code):
        """Appelé quand un client se déconnecte"""
        # Quitter le groupe de notifications
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Recevoir un message du client (optionnel)"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', '')
            
            # Gérer les différents types de messages du client
            if message_type == 'mark_as_read':
                notification_id = data.get('notification_id')
                await self.mark_notification_read(notification_id)
                
                await self.send(text_data=json.dumps({
                    'type': 'notification_read',
                    'notification_id': notification_id,
                    'success': True
                }))
            
            elif message_type == 'ping':
                # Répondre au ping pour maintenir la connexion
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))
        
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Format JSON invalide'
            }))
    
    async def notification_message(self, event):
        """
        Recevoir une notification du groupe et l'envoyer au client
        Ce handler est appelé quand on envoie au groupe via channel_layer.group_send
        """
        # Envoyer le message au WebSocket
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))
    
    @database_sync_to_async
    def check_user_exists(self, user_id):
        """Vérifier si l'utilisateur existe"""
        try:
            User.objects.get(id=user_id)
            return True
        except User.DoesNotExist:
            return False
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Marquer une notification comme lue"""
        from .models import Notification
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False