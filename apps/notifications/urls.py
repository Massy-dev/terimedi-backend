from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DeviceTokenViewSet,
    NotificationViewSet,
    NotificationPreferenceViewSet,
    NotificationManagementViewSet
)

# Router pour les ViewSets
router = DefaultRouter()
router.register(r'devices', DeviceTokenViewSet, basename='device-token')
router.register(r'list', NotificationViewSet, basename='notification')
router.register(r'preferences', NotificationPreferenceViewSet, basename='notification-preference')
router.register(r'manage', NotificationManagementViewSet, basename='notification-management')

app_name = 'notifications'

urlpatterns = [
    path('', include(router.urls)),
    
]

# URLs disponibles :
# 
# Devices (Tokens FCM) :
# - POST   /api/notifications/devices/                  → Enregistrer un token
# - GET    /api/notifications/devices/                  → Liste des tokens
# - DELETE /api/notifications/devices/{id}/             → Supprimer un token
# - POST   /api/notifications/devices/unregister/       → Désactiver un token
#
# Notifications :
# - GET    /api/notifications/list/                     → Liste des notifications
# - GET    /api/notifications/list/{id}/                → Détail d'une notification
# - GET    /api/notifications/list/unread_count/        → Nombre de non lues
# - POST   /api/notifications/list/{id}/mark_as_read/   → Marquer comme lue
# - POST   /api/notifications/list/mark_all_as_read/    → Tout marquer comme lu
#
# Préférences :
# - GET    /api/notifications/preferences/my_preferences/     → Mes préférences
# - PATCH  /api/notifications/preferences/update_preferences/ → Mettre à jour
#
# Management (Envoi) :
# - POST   /api/notifications/manage/send_notification/      → Envoyer une notification
# - POST   /api/notifications/manage/send_bulk_notification/ → Envoi groupé