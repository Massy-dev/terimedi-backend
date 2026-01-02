from rest_framework.decorators import action
from rest_framework import viewsets, permissions,status
from .models import *
from .serializers import *
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.pharmacies.models import Pharmacy
from .utils import calculer_distance
from rest_framework.views import APIView
import math
from django.contrib.auth import get_user_model

User = get_user_model()

class CommandeViewSet(viewsets.ModelViewSet):
    queryset = Commande.objects.all().order_by('-date_commande')
    serializer_class = CommandeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)

    def get_queryset(self):
        # Les clients voient leurs commandes, les superusers voient tout
        user = self.request.user
        if user.is_superuser:
            return Commande.objects.all()

        if user.role == "pharmacien":
            pharmacy = getattr(user, 'pharmacies', None)
            if not pharmacy.exists():
                return Commande.objects.none()
            return Commande.objects.filter(pharmacie=pharmacy.first())  
            
            #return Commande.objects.filter(pharmacie=pharmacy.id)  
        return Commande.objects.filter(client=user)
    
    @action(detail=True, methods=['post'])
    def relancer(self, request, pk=None):
        commande = self.get_object()

        if commande.relance_count >= 3:
            commande.statut = 'echouee'
            commande.save()
            return Response({'message': 'Commande échouée après 3 relances.'}, status=status.HTTP_400_BAD_REQUEST)

        pharmacies = Pharmacy.objects.filter(is_open=True, is_approved=True).exclude(id=commande.pharmacie.id)
        pharmacies = sorted(
            pharmacies,
            key=lambda p: calculer_distance(
                commande.patient_latitude,
                commande.patient_longitude,
                p.latitude,
                p.longitude)
        )

        if pharmacies:
            commande.pharmacie = pharmacies[0]
            commande.statut = 'en_attente'
            commande.relance_count += 1
            commande.save()
            return Response({'message': f'Commande réaffectée à la pharmacie {pharmacies[0].name}.'})

        # Aucun autre disponible
        commande.statut = 'echouee'
        commande.relance_count += 1
        commande.save()
        return Response({'message': 'Aucune pharmacie disponible pour relancer la commande.'}, status=400)

    @action(detail=True, methods=['patch'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        commande = self.get_object()
        new_status = request.data.get('statut')

        if new_status not in ['en_attente', 'acceptee', 'refusee', 'livree', 'echouee']:
            return Response({'error': 'Statut invalide.'}, status=400)

        commande.statut = new_status
        commande.save()
        return Response({'message': f'Statut changé en {new_status}.'})

class DetailOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            commande = Commande.objects.get(pk=pk)
        except Commande.DoesNotExist:
            return Response({'error': 'Commande introuvable'}, status=404)

        user = commande.client
        items = OrderItem.objects.filter(order=commande)

        items_data = [
            {
                "id": item.id,
                "product": item.product,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "subtotal": item.subtotal,
                "prescription_image": request.build_absolute_uri(item.prescription_image.url) if item.prescription_image else None
            }
            for item in items
        ]

        data = {
            "id": commande.id,
            "order_number": commande.order_number,
            "produits": items_data,
            "statut": commande.statut,
            "client": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
            },
            "date_commande": commande.date_commande,
            "total": commande.total_amount,
        }
        return Response(data, status=200)
        

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pharmacie_plus_proche(request):
    try:
        lat = float(request.query_params.get('lat'))
        lng = float(request.query_params.get('lng'))
    except (TypeError, ValueError):
        return Response({"error": "Coordonnées invalides."}, status=400)

    pharmacies = Pharmacy.objects.filter(is_open=True, is_approved=True)
    if not pharmacies.exists():
        return Response({"error": "Aucune pharmacie disponible."}, status=404)

    pharmacie_proche = min(pharmacies, key=lambda p: calculer_distance(lat, lng, p.latitude, p.longitude))

    return Response({
        "id": pharmacie_proche.id,
        "name": pharmacie_proche.name,
        "latitude": pharmacie_proche.latitude,
        "longitude": pharmacie_proche.longitude,
        "distance_km": round(calculer_distance(lat, lng, pharmacie_proche.latitude, pharmacie_proche.longitude), 2)
    })

def relancer_commande(commande):
    pharmacies_disponibles = Pharmacy.objects.filter(is_open=True, is_approved=True).exclude(id=commande.pharmacie.id)

    if not pharmacies_disponibles.exists():
        commande.statut = 'echouee'
        commande.save()
        return

    client_lat = commande.patient_latitude
    client_lon = commande.patient_longitude

    pharmacies_triees = sorted(
        pharmacies_disponibles,
        key=lambda p: calculer_distance(client_lat, client_lon, p.latitude, p.longitude)
    )

    nouvelle_pharmacie = pharmacies_triees[0]
    commande.pharmacie = nouvelle_pharmacie
    commande.statut = 'en_attente'
    commande.relance_count += 1
    commande.save()
  
