from rest_framework.routers import DefaultRouter
from .views import *
from django.conf.urls.static import static
from django.urls import path, include

#router = DefaultRouter()
#router.register(r'', CommandeViewSet, basename='commande')

urlpatterns = [
    #path('', include(router.urls)),
    # Liste et création
    path('', CommandeAPIView.as_view(), name='commandes-list-create'),

    path('detail/<uuid:commande_id>/', CommandeDetailAPIView.as_view(), name='order-detail'),
    path('retirer/<int:commande_id>/medicaments/<int:medicament_id>/',
         RetirerMedicamentAPIView.as_view(), name='retirer-medicament'),
    path('pharmacie-plus-proche/', pharmacie_plus_proche, name='pharmacie_plus_proche'),
    #path('detail/<int:pk>/', DetailOrdersView.as_view()),

    path('<uuid:commande_id>/accepter-devis/', AccepterDevisAPIView.as_view(), name='accepter-devis'),
    path('<uuid:commande_id>/refuser-devis/', RefuserDevisAPIView.as_view(), name='refuser-devis'),
    # CÔTÉ PHARMACIE
    path('commandes-disponibles/', CommandesDisponiblesAPIView.as_view(), name='commandes-disponibles'),
    path('<uuid:commande_id>/accepter/', AccepterCommandeAPIView.as_view(), name='accepter-commande'),
    path('<uuid:commande_id>/soumettre-devis/', SoumettreDevisAPIView.as_view(), name='soumettre-devis'),
    path('<uuid:commande_id>/changer-statut/', changer_statut_commande, name='changer-statut'),
    #path('pharmacies/mes-commandes/', MesCommandesPharmacieAPIView.as_view(), name='mes-commandes-pharmacie'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



# URLs disponibles :
# 
# GET    /api/orders/                    → Liste des commandes
# POST   /api/orders/                    → Créer une commande (avec notification auto)
# GET    /api/orders/{id}/               → Détail d'une commande
# PUT    /api/orders/{id}/               → Modifier une commande
# DELETE /api/orders/{id}/               → Supprimer une commande
#
# Actions personnalisées avec notifications :
# POST   /api/orders/{id}/confirm/       → Confirmer la commande
# POST   /api/orders/{id}/start_preparing/ → Démarrer préparation
# POST   /api/orders/{id}/mark_ready/    → Marquer comme prête
# POST   /api/orders/{id}/start_delivery/ → Démarrer livraison
# POST   /api/orders/{id}/mark_delivered/ → Marquer comme livrée
# POST   /api/orders/{id}/cancel/        → Annuler la commande