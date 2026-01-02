import logging
from typing import Dict, List, Optional
from apps.users.models import CustomUser
from django.contrib.auth.models import User
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from firebase_admin import messaging
from .models import DeviceToken, Notification, NotificationPreference

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service centralisé pour gérer les notifications FCM et WebSocket
    """
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
   
    def send_notification(
        self,
        user: User,
        notification_type: str,
        title: str,
        body: str,
        data: Optional[Dict] = None,
        force_fcm: bool = False
    ) -> Notification:
        """
        Envoie une notification via FCM et/ou WebSocket selon les préférences
        
        Args:
            user: L'utilisateur destinataire
            notification_type: Type de notification (order_created, order_confirmed, etc.)
            title: Titre de la notification
            body: Corps de la notification
            data: Données supplémentaires (dict)
            force_fcm: Forcer l'envoi FCM même si l'utilisateur n'a pas de token
        
        Returns:
            Notification: L'objet notification créé
        """
        # Vérifier les préférences de l'utilisateur
        preferences = self._get_user_preferences(user)
        print("preference------- ",preferences)
        if not self._should_send_notification(preferences, notification_type):
            logger.info(f"Notification {notification_type} désactivée pour {user.phone}")
            return None
        
        # Créer l'enregistrement de notification
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
            channel='both'
        )
        
        # Déterminer les canaux à utiliser
        send_fcm = preferences.enable_fcm
        send_ws = preferences.enable_websocket
        
        success = False
        
        # Envoyer via WebSocket si l'utilisateur est connecté
        if send_ws:
            ws_success = self._send_via_websocket(user, notification)
            success = success or ws_success
        
        # Envoyer via FCM pour les notifications push
        if send_fcm or force_fcm:
            fcm_success = self._send_via_fcm(user, notification)
            success = success or fcm_success
        
        # Marquer comme envoyée si au moins un canal a réussi
        if success:
            notification.mark_as_sent()
        else:
            notification.error_message = "Échec d'envoi sur tous les canaux"
            notification.save()
        
        return notification
    
    def _send_via_websocket(self, user: User, notification: Notification) -> bool:
        """
        Envoie la notification via WebSocket
        
        Returns:
            bool: True si envoyé avec succès
        """
        try:
            room_group_name = f'notifications_{user.id}'
            
            # Préparer les données de notification
            notification_data = {
                'id': notification.id,
                'type': notification.notification_type,
                'title': notification.title,
                'body': notification.body,
                'data': notification.data,
                'created_at': notification.created_at.isoformat(),
            }
            
            # Envoyer au groupe WebSocket
            async_to_sync(self.channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'notification_message',
                    'notification': notification_data
                }
            )
            
            logger.info(f"Notification WebSocket envoyée à {user.phone}")
            return True
        
        except Exception as e:
            logger.error(f"Erreur WebSocket pour {user.phone}: {str(e)}")
            return False
    
    def _send_via_fcm(self, user: User, notification: Notification) -> bool:
        """
        Envoie la notification via Firebase Cloud Messaging
        
        Returns:
            bool: True si envoyé avec succès à au moins un device
        """
        # Récupérer tous les tokens actifs de l'utilisateur
        device_tokens = DeviceToken.objects.filter(
            user=user,
            is_active=True
        )
        
        if not device_tokens.exists():
            logger.warning(f"Aucun token FCM actif pour {user.phone}")
            return False
        
        success_count = 0
        failed_tokens = []
        
        for device in device_tokens:
            try:
                # Construire le message FCM
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=notification.title,
                        body=notification.body,
                    ),
                    data={
                        'notification_id': str(notification.id),
                        'type': notification.notification_type,
                        **(notification.data or {})
                    },
                    token=device.token,
                    android=messaging.AndroidConfig(
                        priority='high',
                        notification=messaging.AndroidNotification(
                            sound='default',
                            channel_id='terimedi_notifications'
                        )
                    ),
                    apns=messaging.APNSConfig(
                        payload=messaging.APNSPayload(
                            aps=messaging.Aps(
                                sound='default',
                                badge=1
                            )
                        )
                    ),
                    webpush=messaging.WebpushConfig(
                        notification=messaging.WebpushNotification(
                            icon='/icon.png',
                            badge='/badge.png'
                        )
                    )
                )
                
                # Envoyer le message
                response = messaging.send(message)
                logger.info(f"FCM envoyé à {user.phone} ({device.platform}): {response}")
                success_count += 1
            
            except messaging.UnregisteredError:
                # Token invalide ou expiré
                logger.warning(f"Token FCM invalide pour {user.phone}, désactivation")
                device.is_active = False
                device.save()
                failed_tokens.append(device.token)
            
            except Exception as e:
                logger.error(f"Erreur FCM pour {user.phone}: {str(e)}")
                failed_tokens.append(device.token)
        
        return success_count > 0
    
    def _get_user_preferences(self, user: User) -> NotificationPreference:
        """Récupère ou crée les préférences de notification de l'utilisateur"""
        preferences, created = NotificationPreference.objects.get_or_create(
            user=user
        )
        return preferences
    
    def _should_send_notification(
        self,
        preferences: NotificationPreference,
        notification_type: str
    ) -> bool:
        """Vérifie si l'utilisateur accepte ce type de notification"""
        type_field = notification_type
        return getattr(preferences, type_field, True)
    
    def register_device_token(
        self,
        user: User,
        token: str,
        platform: str
    ) -> DeviceToken:
        """
        Enregistre ou met à jour un token de device FCM
        
        Args:
            user: L'utilisateur
            token: Le token FCM
            platform: 'android', 'ios', ou 'web'
        
        Returns:
            DeviceToken: Le token enregistré
        """
        device_token, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                'user': user,
                'platform': platform,
                'is_active': True
            }
        )
        
        action = "créé" if created else "mis à jour"
        logger.info(f"Token FCM {action} pour {user.phone} ({platform})")
        
        return device_token
    
    def unregister_device_token(self, token: str) -> bool:
        """
        Désactive un token de device
        
        Args:
            token: Le token FCM à désactiver
        
        Returns:
            bool: True si désactivé avec succès
        """
        try:
            device_token = DeviceToken.objects.get(token=token)
            device_token.is_active = False
            device_token.save()
            logger.info(f"Token FCM désactivé: {token[:20]}...")
            return True
        except DeviceToken.DoesNotExist:
            logger.warning(f"Token FCM introuvable: {token[:20]}...")
            return False
    
    def get_user_notifications(
        self,
        user: User,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Notification]:
        """
        Récupère les notifications d'un utilisateur
        
        Args:
            user: L'utilisateur
            unread_only: Ne récupérer que les non lues
            limit: Nombre maximum de notifications
        
        Returns:
            List[Notification]: Liste des notifications
        """
        queryset = Notification.objects.filter(user=user)
        
        if unread_only:
            queryset = queryset.filter(is_read=False)
        
        return queryset[:limit]
    
    def mark_notification_as_read(self, notification_id: int) -> bool:
        """
        Marque une notification comme lue
        
        Args:
            notification_id: L'ID de la notification
        
        Returns:
            bool: True si marquée avec succès
        """
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False


# Instance singleton du service
notification_service = NotificationService()