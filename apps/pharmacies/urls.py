from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

"""router = DefaultRouter()
router.register('pharmacien', PharmacienViewSet, basename='pharmacien')"""

urlpatterns = [
    path('me/', PharmacienAPIView.as_view(), {'action': 'me'}, name='pharmacy-me'),
    path('liste/', PharmacyListView.as_view()),
    path('create/', PharmacyCreateView.as_view()),
    path('mine/', MyPharmacyView.as_view()),

    path('<int:pk>/validate/', PharmacyValidateView.as_view()),
    path('<int:pk>/reject/', PharmacyRejectView.as_view()),

    path('nearby/', PharmacyNearbyView.as_view(), name='pharmacy-nearby'),
    path("device-token/", RegisterDeviceTokenView.as_view(), name="register_device_token"),
    
    # VUES DE TEST POUR LE DÉVELOPPEMENT
    path('test/', TestPublicView.as_view(), name='test-public'),
    path('test/pharmacies/', TestPharmacyListView.as_view(), name='test-pharmacies'),
]
