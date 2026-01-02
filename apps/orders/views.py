from decimal import Decimal
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
from django.db import transaction
from apps.notifications.utils import send_ws_notification
from apps.notifications.fcm import send_fcm_notification
from apps.notifications.helpers import (
    notify_order_confirmed,
    notify_order_quote,
    notify_order_preparing,
    notify_order_ready,
    notify_order_delivering,
    notify_order_cancelled,
)

User = get_user_model()

def get_pharmacy_or_404(user):
        """Helper pour récupérer la pharmacie de l'utilisateur"""
        if not hasattr(user, 'pharmacies'):
            return None
        return user.pharmacies.first()

class CommandeAPIView(APIView):
    """
    API pour gérer les commandes
    """
    
    permission_classes = [IsAuthenticated]
    


    def get(self, request):
       
        #GET /api/orders/
        #Liste des commandes du client connecté
        
        pharmacy = get_pharmacy_or_404(request.user)
        user = request.user
        
        
        if user.is_superuser:
            commandes = Commande.objects.all().order_by('-date_commande')
            print('iciiii 1')

        elif pharmacy:
            commandes = Commande.objects.filter(pharmacie=pharmacy).order_by('-date_commande')
            print('iciiii 2', pharmacy)
        else:
            commandes = Commande.objects.filter(client=user).order_by('-date_commande')
            
        serializer = CommandeSerializer(commandes, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    """def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Commande.objects.all()
        return Commande.objects.filter(client=user).order_by('-date_commande')"""

    def post(self, request):
        """
        POST /api/orders/
        Créer une nouvelle commande avec médicaments
        """
        
         
        # Debug: voir si user est anonymousUser
        print("USER:", request.user)
        print("AUTH:", request.auth)
        print(request.headers.get("Authorization"))
        if request.user.is_anonymous:
            return Response({"error": "User non authentifié"}, status=401)
        
        
        if 'medicaments' in request.data:
            medicaments_raw = request.data.get('medicaments')
           
        
        serializer = CommandeCreateSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        if 1==1:
            patient_lat=serializer.validated_data['patient_latitude'],
            patient_long=serializer.validated_data['patient_longitude'],
            
            # Filtrer les pharmacies ouvertes et approuvées
            pharmacies = Pharmacy.objects.filter(is_open=True, is_approved=True)
            if not pharmacies.exists():
                raise serializers.ValidationError("Aucune pharmacie disponible actuellement.")

            
            decimalLat = Decimal(patient_lat[0])
            decimalLong = Decimal(patient_long[0])
            
            # Trouver la pharmacie la plus proche
            pharmacie_proche = min(
                pharmacies,
                key=lambda p: calculer_distance(decimalLat, decimalLong, Decimal(p.latitude), Decimal(p.longitude)) 
            )
            
            
            with transaction.atomic():
                # Créer la commande
                print("mon clienttttttttttttt***", request.user)
                print("serializer---------------- ",serializer.errors)
                print("request--------------- ",request.user)
                commande = Commande.objects.create(
                    client=serializer.validated_data.get('client', request.user),
                    patient_latitude=decimalLat,
                    patient_longitude=decimalLong,
                    clt_phone=serializer.validated_data['clt_phone'],
                    statut= 'en_attente',
                    pharmacie=pharmacie_proche

                )
                print('dans la view----',commande)
                send_ws_notification(
                    user_id=str(commande.order_number),
                    message=f"Nouvelle commande : ",
                    extra={"order_id": commande}
                )
        try:
            
                # Ajouter les médicaments
                 
                medicaments_data = serializer.validated_data['medicaments']
                 
                for index, med_data in enumerate(medicaments_data):
                    # Gérer l'image si elle existe
                    image_key = f'medicament_{index}_image'
                    image_file = request.FILES.get(image_key)
                   
                    result = OrderItem.objects.create(
                        order=commande,
                        produit=med_data['produit'],
                        quantity=med_data['quantity'],
                        unit_price=0.0,  # Prix unitaire par défaut (à mettre à jour selon votre logique)
                        prescription_image=image_file if image_file else None
                    )
                 
                commande.update_total()
                print("orderr ", commande.order_number)
               
            
               

                
               
                # TODO: Envoyer notification aux pharmacies proches
               
                # Sérialiser la réponse
                response_serializer = CommandeSerializer(commande, context={'request': request})
                return Response(
                    {
                        "message": "Commande créée avec succès",
                        "commande": response_serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )

        except Exception as e:
            
            return Response(
                {"error": f"Erreur lors de la création: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    



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

class CommandeDetailAPIView(APIView):
    """
    API pour gérer une commande spécifique
    """
    #permission_classes = [IsAuthenticated]
    
    def dispatch(self, request, *args, **kwargs):
        print(">>> DISPATCH TRIGGERED")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, commande_id):
       
        """
        GET /api/commandes/:id/
        Détails d'une commande
        """
        pharmacy = get_pharmacy_or_404(request.user)
        
        
        try:
            commande = Commande.objects.get(id=commande_id, pharmacie=pharmacy)
            serializer = CommandeSerializer(commande, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Commande.DoesNotExist:
            return Response(
                {"error": "Commande non trouvée"},
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, commande_id):
        print("delete------ ")
        """
        DELETE /api/commandes/:id/
        Annuler une commande (si en_attente)
        """
        try:
            commande = Commande.objects.get(id=commande_id, client=request.user)
            
            if commande.statut != 'en_attente':
                return Response(
                    {"error": "Seules les commandes en attente peuvent être annulées"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            commande.statut = 'annulee'
            commande.save()
            
            return Response(
                {"message": "Commande annulée avec succès"},
                status=status.HTTP_200_OK
            )
        except Commande.DoesNotExist:
            return Response(
                {"error": "Commande non trouvée"},
                status=status.HTTP_404_NOT_FOUND
            )


class AccepterDevisAPIView(APIView):
    """Client accepte le devis"""
    permission_classes = [IsAuthenticated]
    print("mon statut ")
    def post(self, request, commande_id):
        """
        POST /api/commandes/{id}/accepter-devis/
        Client accepte le devis de la pharmacie
        """
        
        try:
            commande = Commande.objects.get(id=commande_id, client=request.user)
            
            if commande.statut != 'devis_envoye':
                return Response(
                    {"error": "Aucun devis en attente pour cette commande"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Changer le statut
            commande.statut = 'accepte_par_client'
            commande.accepte_par_client_at = timezone.now()
            commande.save()
            print("mon statut ",commande.statut)
            # TODO: Envoyer notification à la pharmacie
            notify_status_change(commande,commande.statut)
            serializer = CommandeSerializer(commande, context={'request': request})
            return Response(
                {
                    "message": "Devis accepté avec succès !",
                    "commande": serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Commande.DoesNotExist:
            return Response(
                {"error": "Commande non trouvée"},
                status=status.HTTP_404_NOT_FOUND
            )


class RefuserDevisAPIView(APIView):
    """Client refuse le devis"""
    permission_classes = [IsAuthenticated]

    def post(self, request, commande_id):
        """
        POST /api/commandes/{id}/refuser-devis/
        Client refuse le devis ou demande une révision
        """
        try:
            commande = Commande.objects.get(id=commande_id, client=request.user)
            
            if commande.statut != 'devis_envoye':
                return Response(
                    {"error": "Aucun devis en attente pour cette commande"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = RefusCommandeSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Enregistrer la raison
            commande.raison_refus = serializer.validated_data.get('raison_refus', '')
            
            # Déterminer le statut
            if serializer.validated_data.get('demander_revision', False):
                commande.statut = 'reviser_prix'
                message = "Révision du prix demandée. La pharmacie sera notifiée."
            else:
                commande.statut = 'refuse_par_client'
                #commande.pharmacie = None  # Libérer pour une autre pharmacie
                message = "Devis refusé. La commande est de nouveau disponible pour les pharmacies."
            
            commande.save()
            
            # TODO: Envoyer notification à la pharmacie
            notify_status_change(commande,commande.statut)

            serializer = CommandeSerializer(commande, context={'request': request})
            return Response(
                {
                    "message": message,
                    "commande": serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Commande.DoesNotExist:
            return Response(
                {"error": "Commande non trouvée"},
                status=status.HTTP_404_NOT_FOUND
            )


def notify_status_change(order, new_status):
    user = order.client  # destinataire
    print("order.pharmacie",order.pharmacie)
    pharmacy = order.pharmacie

    if user.device_token:
        send_fcm_notification(
            device_token=user.device_token,
            title="Mise à jour de votre commande",
            body=f"Votre devis a été {new_status}.",
            data={"order_id": str(order.id)}
        )

    
    if pharmacy.device_tokens:
        send_fcm_notification(
            device_token=pharmacy.device_tokens,
            title="Nouvelle commande",
            body=f"Le client a modifié sa commande.",
            data={"order_id": str(order.id)}
        )

# ==========================================
# CÔTÉ PHARMACIE
# ==========================================
class CommandesDisponiblesAPIView(APIView):
    """Liste des commandes disponibles pour les pharmacies"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        GET /api/pharmacies/commandes-disponibles/
        Liste des commandes en statut 'soumis' ou 'refuse_par_client'
        """
        # Vérifier que l'utilisateur a une pharmacie
        if not hasattr(request.user, 'pharmacy'):
            return Response(
                {"error": "Vous n'êtes pas associé à une pharmacie"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Commandes disponibles (pas encore acceptées par une pharmacie)
        commandes = Commande.objects.filter(
            statut__in=['soumis', 'refuse_par_client'],
            pharmacie__isnull=True
        ).order_by('-created_at')
        
        # TODO: Filtrer par distance (pharmacies proches)
        
        serializer = CommandeSerializer(commandes, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

class AccepterCommandeAPIView(APIView):
    """Pharmacie accepte une commande"""
    permission_classes = [IsAuthenticated]

    def post(self, request, commande_id):
        """
        POST /api/pharmacies/commandes/{id}/accepter/
        Pharmacie accepte la commande (STATUT: en_attente_de_prix)
        """
        try:
            # Vérifier que l'utilisateur a une pharmacie
            if not hasattr(request.user, 'pharmacy'):
                return Response(
                    {"error": "Vous n'êtes pas associé à une pharmacie"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            commande = Commande.objects.get(id=commande_id)
            
            # Vérifier que la commande est disponible
            if commande.statut not in ['soumis', 'refuse_par_client']:
                return Response(
                    {"error": "Cette commande n'est plus disponible"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if commande.pharmacie is not None:
                return Response(
                    {"error": "Cette commande a déjà été acceptée par une autre pharmacie"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Accepter la commande
            commande.pharmacie = request.user.pharmacy
            commande.statut = 'en_attente_de_prix'
            commande.accepte_par_pharmacie_at = timezone.now()
            commande.save()
            
            # TODO: Envoyer notification au client
            notify_order_confirmed(commande, commande.client)
            serializer = CommandeSerializer(commande, context={'request': request})
            return Response(
                {
                    "message": "Commande acceptée. Vous pouvez maintenant soumettre un devis.",
                    "commande": serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Commande.DoesNotExist:
            return Response(
                {"error": "Commande non trouvée"},
                status=status.HTTP_404_NOT_FOUND
            )


class SoumettreDevisAPIView(APIView):
    """Pharmacie soumet le devis avec les prix"""
    
    permission_classes = [IsAuthenticated]
    
    
  
    def post(self, request, commande_id):
        

        """
        POST /api/pharmacies/commandes/{id}/soumettre-devis/
        Pharmacie soumet les prix (STATUT: devis_envoye)
        """
        
        
        try:
            # Vérifier que l'utilisateur a une pharmacie
            pharmacy = get_pharmacy_or_404(request.user)
           
            commande = Commande.objects.get(
                id=commande_id,
                pharmacie=pharmacy
            )
            
            if commande.statut not in ['en_attente','en_attente_de_prix', 'reviser_prix','soumis']:
                return Response(
                    {"error": "Vous ne pouvez pas soumettre de devis pour cette commande"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = DevisSerializer(data=request.data)
            print("SERIALIZER:", serializer.is_valid())
            print("SERIALIZER ERRORS:", serializer)
            print("REQUEST DATA:", request.data)

            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # Mettre à jour les prix des médicaments
                print("MEDICAMENTS:", serializer.validated_data['items'])
                for med_data in serializer.validated_data['items']:
                    medicament = OrderItem.objects.get(
                        id=med_data['id'],
                        order=commande
                    )
                    medicament.unit_price = Decimal(str(med_data['unit_price']))
                    
                    medicament.disponibilite = med_data['disponibilite']
                    medicament.note_pharmacie = med_data.get('note_pharmacie', '')
                    medicament.save()
                
                # Mettre à jour les frais de livraison
                commande.frais_livraison = serializer.validated_data['delivery_fee']
                
                # Calculer le montant total
                commande.update_total()
                print('montant total', commande.update_total)
                # Changer le statut
                
                commande.statut = 'devis_envoye'
                commande.devis_envoye_at = timezone.now()
                commande.save()
                
                # TODO: Envoyer notification au client
                notify_order_quote(commande, commande.client)
                response_serializer = CommandeSerializer(commande, context={'request': request})
                return Response(
                    {
                        "message": "Devis envoyé avec succès au client",
                        "commande": response_serializer.data
                    },
                    status=status.HTTP_200_OK
                )
            
        except Commande.DoesNotExist:
            return Response(
                {"error": "Commande non trouvée"},
                status=status.HTTP_404_NOT_FOUND
            )
        except OrderItem.DoesNotExist:
            return Response(
                {"error": "Médicament non trouvé"},
                status=status.HTTP_404_NOT_FOUND
            )


class RetirerMedicamentAPIView(APIView):
    """
    API pour retirer un médicament d'une commande
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, commande_id, medicament_id):
        """
        DELETE /api/commandes/:commande_id/medicaments/:medicament_id/
        Retirer un médicament d'une commande (si en_attente)
        """
        try:
            commande = Commande.objects.get(id=commande_id, client=request.user)
            
            if commande.statut != 'en_attente':
                return Response(
                    {"error": "Impossible de modifier une commande validée"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            medicament = OrderItem.objects.get(
                id=medicament_id,
                commande=commande
            )
            
            # Vérifier qu'il reste au moins 1 médicament
            if commande.medicaments.count() <= 1:
                return Response(
                    {"error": "Une commande doit contenir au moins un médicament"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            medicament.delete()
            
            return Response(
                {"message": "Médicament retiré avec succès"},
                status=status.HTTP_200_OK
            )
            
        except Commande.DoesNotExist:
            return Response(
                {"error": "Commande non trouvée"},
                status=status.HTTP_404_NOT_FOUND
            )
        except OrderItem.DoesNotExist:
            return Response(
                {"error": "Médicament non trouvé"},
                status=status.HTTP_404_NOT_FOUND
            )


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

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def changer_statut_commande(request, commande_id):
    
    pharmacy = get_pharmacy_or_404(request.user)
    print("commande id", pharmacy)
    try:
        commande = Commande.objects.get(
            id=commande_id,
            pharmacie=pharmacy
        )
        
        nouveau_statut = request.data.get('statut')
        print("nouveau statut ",nouveau_statut)
        # Valider les transitions de statut
        if nouveau_statut in ['en_preparation', 'en_livraison', 'livree']:
            commande.statut = nouveau_statut
            commande.save()
            
            return Response({'message': 'Statut mis à jour'})
        else:
            return Response(
                {'error': 'Statut invalide'},
                status=400
            )
            
    except Commande.DoesNotExist:
        return Response({'error': 'Commande non trouvée'}, status=404)

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
  
