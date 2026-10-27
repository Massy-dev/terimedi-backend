
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination

from .models import Notification
from .serializers import NotificationSerializer
from .models import DeviceToken
from .serializers import (
    DeviceTokenDeleteSerializer,
    DeviceTokenSerializer,
)


class DeviceTokenView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = DeviceTokenSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]
        platform = serializer.validated_data["platform"]

        device, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                "user": request.user,
                "platform": platform,
                "is_active": True,
            },
        )

        return Response(
            {
                "message": "Device registered successfully.",
                "device_id": str(device.id),
                "created": created,
            },
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )

    def delete(self, request):
        serializer = DeviceTokenDeleteSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]

        DeviceToken.objects.filter(
            user=request.user,
            token=token,
        ).update(
            is_active=False,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user,
        ).order_by("-created_at", "-id")


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).count()

        return Response({
            "unread_count": count,
        })


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notification_id):
        updated = Notification.objects.filter(
            id=notification_id,
            user=request.user,
            is_read=False,
        ).update(
            is_read=True,
            read_at=timezone.now(),
        )

        exists = Notification.objects.filter(
            id=notification_id,
            user=request.user,
        ).exists()

        if not exists:
            return Response(
                {"detail": "Notification introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            "message": "Notification marquée comme lue.",
            "updated": bool(updated),
        })


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).update(
            is_read=True,
            read_at=timezone.now(),
        )

        return Response({
            "updated_count": updated,
        })