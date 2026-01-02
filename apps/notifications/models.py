from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.users.models import CustomUser
from django.conf import settings
User = get_user_model()


class DeviceToken(models.Model):
    """
    Stocke les tokens FCM des devices pour envoyer les notifications push
    """
    PLATFORM_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10,default="android", choices=PLATFORM_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'device_tokens'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['token']),
        ]
    
    def __str__(self):
        return f"{self.user.phone} - {self.platform} - {self.token[:20]}..."


class Notification(models.Model):
    """
    Historique des notifications envoyées
    """
    TYPE_CHOICES = [
        ('order_created', 'Nouvelle Commande'),
        ("quote_sent", "Devis envoyé"),
        ("quote_accepted", "Devis accepté"),
        ("quote_rejected", "Devis rejeté" ),
        ('order_confirmed', 'Commande Confirmée'),
        ('order_preparing', 'En Préparation'),
        ('order_ready', 'Commande Prête'),
        ('order_delivering', 'En Livraison'),
        ('order_delivered', 'Livrée'),
        ('order_cancelled', 'Annulée'),
        ('general', 'Général'),
    ]
    
    CHANNEL_CHOICES = [
        ('fcm', 'FCM Push'),
        ('websocket', 'WebSocket'),
        ('both', 'Les deux'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,null=True, blank=True, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="both")
    title = models.CharField(max_length=100,null=True, blank=True)
    body = models.TextField()
    data = models.JSONField(null=True, blank=True)  # Données supplémentaires (order_id, etc.)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='both')
    
    # Statut d'envoi
    is_sent = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Erreurs éventuelles
    error_message = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.phone} - {self.title}"
    
    def mark_as_sent(self):
        """Marquer comme envoyée"""
        self.is_sent = True
        self.sent_at = timezone.now()
        self.save()
    
    def mark_as_read(self):
        """Marquer comme lue"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save()


class NotificationPreference(models.Model):
    """
    Préférences de notifications par utilisateur
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Préférences par type
    order_created   = models.BooleanField(default=True)
    quote_sent      = models.BooleanField(default=True)
    quote_accepted  = models.BooleanField(default=True)
    quote_rejected  = models.BooleanField(default=True)
    order_confirmed = models.BooleanField(default=True)
    order_preparing = models.BooleanField(default=True)
    order_ready     = models.BooleanField(default=True)
    order_delivering = models.BooleanField(default=True)
    order_delivered = models.BooleanField(default=True)
    order_cancelled = models.BooleanField(default=True)
    general = models.BooleanField(default=True)
    
    # Canaux préférés
    enable_fcm = models.BooleanField(default=True)
    enable_websocket = models.BooleanField(default=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
    
    def __str__(self):
        return f"Préférences de {self.user.phone}"