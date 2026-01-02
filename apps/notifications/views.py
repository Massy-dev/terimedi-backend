from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from .models import DeviceToken, Notification, NotificationPreference
from .serializers import (
    DeviceTokenSerializer,
    NotificationSerializer,
    NotificationPreferenceSerializer,
    SendNotificationSerializer,
    MarkAsReadSerializer
)
from .services import notification_service


class DeviceTokenViewSet(viewsets.ModelViewSet):
    """
    API pour gérer les tokens FCM des devices
    """
    serializer_class = DeviceTokenSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Récupérer seulement les tokens de l'utilisateur connecté"""
        return DeviceToken.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Enregistrer un nouveau token FCM"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Utiliser le service pour enregistrer le token
        device_token = notification_service.register_device_token(
            user=request.user,
            token=serializer.validated_data['token'],
            platform=serializer.validated_data['platform']
        )
        
        output_serializer = self.get_serializer(device_token)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def unregister(self, request):
        """Désactiver un token FCM"""
        token = request.data.get('token')
        
        if not token:
            return Response(
                {'error': 'Token requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success = notification_service.unregister_device_token(token)
        
        if success:
            return Response({'message': 'Token désactivé avec succès'})
        else:
            return Response(
                {'error': 'Token introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API pour consulter les notifications
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Récupérer les notifications de l'utilisateur connecté"""
        queryset = Notification.objects.filter(user=self.request.user)
        
        # Filtrer par statut lu/non lu
        is_read = self.request.query_params.get('is_read', None)
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Compter les notifications non lues"""
        count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        return Response({'unread_count': count})
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Marquer une notification comme lue"""
        notification = self.get_object()
        
        if notification.user != request.user:
            return Response(
                {'error': 'Non autorisé'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        notification.mark_as_read()
        
        return Response({
            'message': 'Notification marquée comme lue',
            'notification': NotificationSerializer(notification).data
        })
    
    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        """Marquer toutes les notifications comme lues"""
        updated_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
        
        return Response({
            'message': f'{updated_count} notification(s) marquée(s) comme lue(s)',
            'count': updated_count
        })


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    API pour gérer les préférences de notifications
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Récupérer les préférences de l'utilisateur connecté"""
        return NotificationPreference.objects.filter(user=self.request.user)
    
    def get_object(self):
        """Récupérer ou créer les préférences de l'utilisateur"""
        obj, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return obj
    
    @action(detail=False, methods=['get'])
    def my_preferences(self, request):
        """Récupérer les préférences de l'utilisateur connecté"""
        preferences = self.get_object()
        serializer = self.get_serializer(preferences)
        return Response(serializer.data)
    
    @action(detail=False, methods=['patch'])
    def update_preferences(self, request):
        """Mettre à jour les préférences"""
        preferences = self.get_object()
        serializer = self.get_serializer(
            preferences,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Préférences mises à jour',
            'preferences': serializer.data
        })


class NotificationManagementViewSet(viewsets.ViewSet):
    """
    API pour gérer l'envoi de notifications (Admin/Système)
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def send_notification(self, request):
        """
        Envoyer une notification à un utilisateur
        Usage: Pour les commandes, changements de statut, etc.
        """
        serializer = SendNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Récupérer l'utilisateur destinataire
        try:
            user = User.objects.get(id=serializer.validated_data['user_id'])
        except User.DoesNotExist:
            return Response(
                {'error': 'Utilisateur introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Envoyer la notification
        notification = notification_service.send_notification(
            user=user,
            notification_type=serializer.validated_data['notification_type'],
            title=serializer.validated_data['title'],
            body=serializer.validated_data['body'],
            data=serializer.validated_data.get('data'),
            force_fcm=serializer.validated_data.get('force_fcm', False)
        )
        
        if notification:
            return Response({
                'message': 'Notification envoyée',
                'notification': NotificationSerializer(notification).data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'message': 'Notification non envoyée (préférences utilisateur)',
            }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def send_bulk_notification(self, request):
        """
        Envoyer une notification à plusieurs utilisateurs
        """
        user_ids = request.data.get('user_ids', [])
        notification_type = request.data.get('notification_type')
        title = request.data.get('title')
        body = request.data.get('body')
        data = request.data.get('data')
        
        if not user_ids or not notification_type or not title or not body:
            return Response(
                {'error': 'Champs requis: user_ids, notification_type, title, body'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        users = User.objects.filter(id__in=user_ids)
        sent_count = 0
        
        for user in users:
            notification = notification_service.send_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data
            )
            if notification:
                sent_count += 1
        
        return Response({
            'message': f'{sent_count}/{len(user_ids)} notification(s) envoyée(s)',
            'sent_count': sent_count,
            'total_users': len(user_ids)
        })