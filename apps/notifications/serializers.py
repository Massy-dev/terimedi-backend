
from rest_framework import serializers

from .models import DeviceToken
from .models import DeviceToken, Notification

class DeviceTokenSerializer(serializers.Serializer):
    token = serializers.CharField(
        max_length=4096,
        trim_whitespace=True,
        allow_blank=False,
        write_only=True,
    )

    platform = serializers.ChoiceField(
        choices=DeviceToken.Platform.choices,
    )


class DeviceTokenDeleteSerializer(serializers.Serializer):
    token = serializers.CharField(
        max_length=4096,
        trim_whitespace=True,
        allow_blank=False,
        write_only=True,
    )


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "body",
            "data",
            "is_read",
            "created_at",
            "read_at",
        ]
        read_only_fields = fields