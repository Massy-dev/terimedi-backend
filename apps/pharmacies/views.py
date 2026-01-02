from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, permissions
from .models import Pharmacy
from .serializers import PharmacySerializer, DeviceTokenSerializer, PharmacyDetailSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.conf import settings

from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics

from rest_framework.decorators import action
from django.shortcuts import get_object_or_404

from .permissions import *
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view

class PharmacienAPIView(APIView):
    """
    Vue unique pour gérer toutes les opérations du pharmacien
    """
    permission_classes = [IsAuthenticated]

    def get_pharmacy_or_404(self, user):
        """Helper pour récupérer la pharmacie de l'utilisateur"""
        if not hasattr(user, 'pharmacies'):
            return None
        return user.pharmacies.first()

    def get(self, request, action=None):
        """
        GET /api/pharmacies/me/ - Récupère utilisateur + pharmacie
        GET /api/pharmacies/profil/ - Récupère le profil de la pharmacie
        """
        pharmacy = self.get_pharmacy_or_404(request.user)
        
        if not pharmacy:
            data = {
                "user": {
                    "id": request.user.id,
                    "username": request.user.username,
                    "phone": getattr(request.user, 'phone', None),
                    "role": request.user.role,
                },
                "pharmacy": None
            }
            return Response(data, status=status.HTTP_200_OK)
        
        # Si l'action est 'me', retourner user + pharmacy
        if action == 'me':
            data = {
                "user": {
                    "id": request.user.id,
                    "username": request.user.username,
                    "phone": getattr(request.user, 'phone', None),
                    "role": request.user.role,
                },
                "pharmacy": {
                    "id": pharmacy.id,
                    "nom": pharmacy.name,
                    "logo": pharmacy.logo.url if pharmacy.logo else None,
                    "description": pharmacy.description,
                    "adresse": pharmacy.address,
                    "telephone": pharmacy.phone_number,
                    "email": pharmacy.email,
                    "latitude": str(pharmacy.latitude) if pharmacy.latitude else None,
                    "longitude": str(pharmacy.longitude) if pharmacy.longitude else None,
                    "is_approved": pharmacy.is_approved,
                    "is_deleted": pharmacy.is_deleted,
                    "is_open": pharmacy.is_open,
                }
            }
            return Response(data, status=status.HTTP_200_OK)
        
        # Sinon retourner uniquement le profil de la pharmacie
        serializer = PharmacyDetailSerializer(pharmacy, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        """
        PATCH /api/pharmacies/profil/ - Met à jour le profil de la pharmacie
        """
        pharmacy = self.get_pharmacy_or_404(request.user)
        
        if not pharmacy:
            return Response(
                {"error": "Pharmacie non trouvée"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PharmacySerializer(
            pharmacy, 
            data=request.data, 
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        """
        PUT /api/pharmacies/profil/ - Met à jour le profil de la pharmacie (complet)
        """
        return self.patch(request)


# Pharmacien — Créer sa pharmacie
class PharmacyCreateView(generics.CreateAPIView):
    queryset = Pharmacy.objects.all()
    serializer_class = PharmacySerializer
    permission_classes = [IsAuthenticated, IsPharmacist]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


# Pharmacien — Voir sa pharmacie
class MyPharmacyView(generics.ListAPIView):
    serializer_class = PharmacySerializer
    permission_classes = [IsAuthenticated, IsPharmacist]

    def get_queryset(self):
        return Pharmacy.objects.filter(owner=self.request.user)


# Admin — Liste toutes les pharmacies
class PharmacyListView(generics.ListAPIView):
    queryset = Pharmacy.objects.all().order_by('-created_at')
    serializer_class = PharmacySerializer
    permission_classes = [IsAuthenticated]


# Admin — Valider


class PharmacyValidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):

        try:
            pharmacy = Pharmacy.objects.get(pk=pk)
            pharmacy.is_approved = True
            pharmacy.save()
            return Response({'message': 'Pharmacie validée ✅'})
        except Pharmacy.DoesNotExist:
            return Response({'error': 'Pharmacie introuvable'}, status=404)


# Admin — Rejeter
class PharmacyRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            
            pharmacy = Pharmacy.objects.get(pk=pk)
            print('bien--',pharmacy.is_deleted)
            pharmacy.is_deleted = True
            pharmacy.save()
            return Response({'message': 'Pharmacie rejetée ❌'})
        except Pharmacy.DoesNotExist:
            return Response({'error': 'Pharmacie introuvable'}, status=404)


class PharmacyNearbyView(APIView):
    permission_classes = [AllowAny]  # Toujours public car utile pour les clients
    
    def get(self, request):
        try:
            lat = float(request.query_params.get("lat"))
            lng = float(request.query_params.get("lng"))
            radius_km = float(request.query_params.get("radius", 5))  # par défaut 5 km
        except (TypeError, ValueError):
            return Response(
                {"error": "Coordonnées invalides. Utilisez lat, lng et radius (optionnel) en paramètres."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validation des coordonnées
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return Response(
                {"error": "Coordonnées hors limites. Latitude: -90 à 90, Longitude: -180 à 180."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if radius_km <= 0 or radius_km > 100:
            return Response(
                {"error": "Rayon invalide. Doit être entre 0 et 100 km."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        user_location = Point(lng, lat, srid=4326)

        nearby_pharmacies = (
            Pharmacy.objects
            .filter(is_open=True, is_approved=True, is_deleted=False)
            .annotate(distance=Distance("location", user_location))
            .filter(location__distance_lte=(user_location, radius_km * 1000))
            .order_by("distance")
        )

        serializer = PharmacySerializer(nearby_pharmacies, many=True)
        return Response(serializer.data)
    

class RegisterDeviceTokenView(APIView):
    def get_permissions(self):
        """
        Permet l'accès public en mode développement
        """
        if settings.DEBUG:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        token = serializer.validated_data["token"]

        # En mode développement, on peut contourner la vérification d'utilisateur
        if settings.DEBUG:
            # Créer un utilisateur temporaire ou utiliser une pharmacie existante
            try:
                pharmacy = Pharmacy.objects.first()
                if pharmacy:
                    tokens = pharmacy.device_tokens or []
                    if token not in tokens:
                        tokens.append(token)
                        pharmacy.device_tokens = tokens
                        pharmacy.save(update_fields=["device_tokens"])
                    return Response({"detail": "Token enregistré avec succès (mode développement)."}, status=status.HTTP_200_OK)
                else:
                    return Response({"detail": "Aucune pharmacie trouvée. Créez d'abord une pharmacie."}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                return Response({"detail": f"Erreur en mode développement: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Vérifier si l'utilisateur est un pharmacien
        if request.user.role != 'pharmacien':
            return Response(
                {"detail": "Seuls les pharmaciens peuvent enregistrer des tokens d'appareil."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # Trouver la pharmacie de l'utilisateur
        try:
            pharmacy = Pharmacy.objects.get(owner=request.user)
        except Pharmacy.DoesNotExist:
            return Response(
                {"detail": "Aucune pharmacie trouvée pour cet utilisateur."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        tokens = pharmacy.device_tokens or []
        if token not in tokens:
            tokens.append(token)
            pharmacy.device_tokens = tokens
            pharmacy.save(update_fields=["device_tokens"])

        return Response({"detail": "Token enregistré avec succès."}, status=status.HTTP_200_OK)


# VUES DE TEST POUR LE DÉVELOPPEMENT
class TestPublicView(APIView):
    """
    Vue de test publique pour vérifier que l'API fonctionne
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response({
            "message": "API TeriMedi fonctionne !",
            "status": "success",
            "debug_mode": settings.DEBUG,
            "timestamp": "2024-01-01T00:00:00Z"
        })


class TestPharmacyListView(APIView):
    """
    Vue de test pour lister toutes les pharmacies (publique en développement)
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        pharmacies = Pharmacy.objects.all()[:10]  # Limite à 10 pharmacies
        serializer = PharmacySerializer(pharmacies, many=True)
        return Response({
            "count": pharmacies.count(),
            "results": serializer.data,
            "message": "Liste des pharmacies (mode développement)"
        })