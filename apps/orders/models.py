from datetime import date
from enum import unique
from django.db import models
from decimal import Decimal
# Create your models here.
from django.db import models
from django.conf import settings
from apps.pharmacies.models import Pharmacy
from apps.users.models import CustomUser
import uuid
from django.db import models, transaction
from django.utils import timezone


def upload_prescription_image(instance, filename):
    return f"prescriptions/{timezone.now().strftime('%Y/%m/%d')}/{filename}"

class Commande(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('en_attente_de_prix', 'En attente de prix'), 
        ('devis_envoye', 'Devis envoyé'),  
        ('accepte_par_client', 'Accepté par client'),   # 4A. Client accepte
        ('refuse_par_client', 'Refusé par client'), 
        ('en_livraison', 'En livraison'),
        ('relancee', 'Relancée'),
        ('livree', 'Livrée'),
        ('annulee', 'Annulée'),
        ('echouee', 'Échouée'),
        ("en_preparation", "En préparation"),
    ]

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='commandes'
    )
    pharmacie = models.ForeignKey(
        Pharmacy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commandes'
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=30, default="000000", blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    texte = models.TextField(blank=True, null=True)

    clt_phone = models.CharField(max_length=10,blank=True, null=True)
    

    patient_latitude = models.DecimalField(max_digits=20, decimal_places=18, default=1.0)
    patient_longitude = models.DecimalField(max_digits=20, decimal_places=18, default=1.0)
    estimated_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=1000.0)

    relance_count = models.IntegerField(default=0)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')

    localisation_client = models.JSONField(help_text="Coordonnées GPS du client (lat, lng)",null=True, blank=True)
    date_commande = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    devis_envoye_at = models.DateTimeField(null=True, blank=True)
    accepte_par_client_at = models.DateTimeField(null=True, blank=True)
    refuse_par_client_at = models.DateTimeField(null=True, blank=True)
    en_livraison_at = models.DateTimeField(null=True, blank=True)
    relancee_at = models.DateTimeField(null=True, blank=True)
    livree_at = models.DateTimeField(null=True, blank=True)
    annulee_at = models.DateTimeField(null=True, blank=True)
    echouee_at = models.DateTimeField(null=True, blank=True)
    en_preparation_at = models.DateTimeField(null=True, blank=True)

    raison_refus = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'commandes'
        ordering = ['-date_commande']

    # --- GÉNÉRATION DU NUMÉRO DE COMMANDE ---
    def save(self, *args, **kwargs):
        """Génère un numéro de commande unique par jour CMD-00014-201125"""
        
        if self.order_number != "" and "CMD-" not in self.order_number:
            today = date.today()
            today_str = timezone.now().strftime("%d%m%y")
            # Debug all order dates for today
            
            last_order = Commande.objects.filter(date_commande__date=today).order_by("-date_commande").first()
            #last_order = Commande.objects.all().order_by("-id").first()
           
            if last_order:
                print(last_order.date_commande, last_order.order_number)
                last_num = int(last_order.order_number.split("-")[1])
                new_num = str(last_num + 1).zfill(5)    
                print("Last ",last_num, " new_num ",new_num)
            else:
                new_num = "00001"

            self.order_number = f"CMD-{new_num}-{today_str}"
        
        super().save(*args, **kwargs)


    def update_total(self):
    
        total = sum(item.subtotal for item in self.items.all())
        self.total_amount = Decimal(total) + Decimal(self.delivery_fee)
        super().save()


    def __str__(self):
        return f"Commande # {self.order_number} ({self.pharmacie.name if self.pharmacie else 'Sans pharmacie'})"



class OrderItem(models.Model):

    """Item d'une commande"""
    DISPONIBILITE_CHOICES = [
        ('disponible', 'Disponible'),
        ('rupture', 'En rupture'),
        ('similaire', 'Similaire disponible'),
    ]
    order = models.ForeignKey(Commande, on_delete=models.CASCADE, related_name="items")
    produit = models.TextField(help_text="Liste des produits demandés (ex: Paracétamol x2, Doliprane x1)")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    prescription_image = models.ImageField(upload_to='prescriptions/', null=True, blank=True)
    note_pharmacie = models.TextField(blank=True, null=True)  # Ex: "Similaire: Paracétamol générique"
    disponibilite = models.CharField(
        max_length=20, 
        choices=DISPONIBILITE_CHOICES, 
        default='disponible'
    )

    def save(self, *args, **kwargs):
        
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.produit} x {self.quantity}"



