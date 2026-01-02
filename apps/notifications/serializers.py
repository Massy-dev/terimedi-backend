from rest_framework import serializers
from .models import DeviceToken, Notification, NotificationPreference


class DeviceTokenSerializer(serializers.ModelSerializer):
    """Serializer pour l'enregistrement des tokens FCM"""
    
    class Meta:
        model = DeviceToken
        fields = ['id', 'token', 'platform', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_platform(self, value):
        """Valider que la plateforme est supportée"""
        allowed_platforms = ['android', 'ios', 'web']
        if value not in allowed_platforms:
            raise serializers.ValidationError(
                f"Plateforme non supportée. Utilisez: {', '.join(allowed_platforms)}"
            )
        return value


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer pour afficher les notifications"""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'user',
            'user_username',
            'notification_type',
            'title',
            'body',
            'data',
            'channel',
            'is_sent',
            'is_read',
            'sent_at',
            'read_at',
            'error_message',
            'created_at'
        ]
        read_only_fields = [
            'id',
            'user',
            'user_username',
            'is_sent',
            'sent_at',
            'created_at'
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer pour les préférences de notifications"""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id',
            'user',
            'quote_sent',
            'quote_accepted',
            'quote_rejected',
            'order_created',
            'order_confirmed',
            'order_preparing',
            'order_ready',
            'order_delivering',
            'order_delivered',
            'order_cancelled',
            'general',
            'enable_fcm',
            'enable_websocket',
            'updated_at'
        ]
        read_only_fields = ['id', 'user', 'updated_at']


class SendNotificationSerializer(serializers.Serializer):
    """Serializer pour envoyer une notification manuelle"""
    
    user_id = serializers.IntegerField()
    notification_type = serializers.ChoiceField(
        choices=[
            'order_created',
            'order_confirmed',
            'order_preparing',
            'order_ready',
            'order_delivering',
            'order_delivered',
            'order_cancelled',
            'general'
        ]
    )
    title = serializers.CharField(max_length=100)
    body = serializers.CharField()
    data = serializers.JSONField(required=False, allow_null=True)
    force_fcm = serializers.BooleanField(default=False)


class MarkAsReadSerializer(serializers.Serializer):
    """Serializer pour marquer une notification comme lue"""
    
    notification_id = serializers.IntegerField()