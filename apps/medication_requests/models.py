
import uuid

from django.conf import settings
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone


class MedicationRequest(models.Model):
    class InputType(models.TextChoices):
        PRESCRIPTION = "PRESCRIPTION", "Prescription"
        PHOTO = "PHOTO", "Medication photo"
        TEXT = "TEXT", "Free text"

    class FulfillmentType(models.TextChoices):
        PICKUP = "PICKUP", "Pickup"
        DELIVERY = "DELIVERY", "Delivery"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        MATCHING = "MATCHING", "Matching"
        PHARMACY_FOUND = "PHARMACY_FOUND", "Pharmacy found"
        PARTIAL = "PARTIAL", "Partial availability"
        QUOTE_PENDING = "QUOTE_PENDING", "Awaiting quote decision"
        CONFIRMED = "CONFIRMED", "Confirmed"
        READY = "READY", "Ready"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="medication_requests",
    )

    input_type = models.CharField(
        max_length=20,
        choices=InputType.choices,
    )

    text = models.TextField(blank=True)

    prescription = models.FileField(
        upload_to="prescriptions/%Y/%m/",
        null=True,
        blank=True,
    )

    medication_photo = models.ImageField(
        upload_to="medication_requests/%Y/%m/",
        null=True,
        blank=True,
    )

    quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    is_urgent = models.BooleanField(default=False)

    quote_requested = models.BooleanField(default=False)

    fulfillment_type = models.CharField(
        max_length=20,
        choices=FulfillmentType.choices,
        default=FulfillmentType.PICKUP,
    )

    patient_location = models.PointField(
        geography=True,
        srid=4326,
    )

    delivery_address = models.CharField(
        max_length=255,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id} - {self.patient.phone_number}"


class PharmacyAssignment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        PARTIAL = "PARTIAL", "Partial"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    medication_request = models.ForeignKey(
        MedicationRequest,
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    pharmacy = models.ForeignKey(
        "pharmacies.Pharmacy",
        on_delete=models.PROTECT,
        related_name="medication_request_assignments",
    )

    # Ancien champ conservé pour les demandes historiques.
    available_items = models.TextField(blank=True)

    # Disponibilités structurées par médicament.
    # Format :
    # [
    #     {"item_id": "uuid", "quantity": 2},
    #     {"item_id": "uuid", "quantity": 1},
    # ]
    available_item_quantities = models.JSONField(
        default=list,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    assigned_at = models.DateTimeField(
        default=timezone.now,
    )

    responded_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    response_note = models.TextField(blank=True)

    class Meta:
        ordering = ["assigned_at"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "medication_request",
                    "pharmacy",
                ],
                name="unique_request_pharmacy_assignment",
            ),
        ]

    def __str__(self):
        return (
            f"{self.medication_request_id} "
            f"-> {self.pharmacy.name}"
        )


class MedicationRequestItem(models.Model):
    class Unit(models.TextChoices):
        BOX = "BOX", "Boîte"
        BOTTLE = "BOTTLE", "Flacon"
        BLISTER = "BLISTER", "Plaquette"
        UNIT = "UNIT", "Unité"
        OTHER = "OTHER", "Autre"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    medication_request = models.ForeignKey(
        MedicationRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )

    name = models.CharField(
        max_length=255,
        blank=True,
    )

    dosage = models.CharField(
        max_length=100,
        blank=True,
    )

    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    unit = models.CharField(
        max_length=20,
        choices=Unit.choices,
        default=Unit.BOX,
    )

    photo = models.ImageField(
        upload_to="medication_requests/items/%Y/%m/",
        null=True,
        blank=True,
    )

    position = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()

        if not self.name.strip() and not self.photo:
            raise ValidationError(
                "Le nom ou une photo du médicament est obligatoire."
            )

    class Meta:
        ordering = ["position", "created_at"]

    def __str__(self):
        return self.name or f"Médicament {self.id}"


class PharmacyQuote(models.Model):
    """
    Proposition financière d'une pharmacie pour une attribution.

    Une attribution ne peut avoir qu'un seul devis dans le MVP.
    Le montant total est exprimé en FCFA.
    """

    class Status(models.TextChoices):
        PROPOSED = "PROPOSED", "Proposed"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    assignment = models.OneToOneField(
        PharmacyAssignment,
        on_delete=models.PROTECT,
        related_name="quote",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PROPOSED,
    )

    total_amount = models.PositiveBigIntegerField(
        default=0,
        help_text="Montant total du devis en FCFA.",
    )

    note = models.TextField(blank=True)

    proposed_at = models.DateTimeField(
        default=timezone.now,
    )

    decided_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-proposed_at"]

    def __str__(self):
        return (
            f"Devis {self.id} - "
            f"{self.total_amount} FCFA - {self.status}"
        )


class PharmacyQuoteItem(models.Model):
    """
    Ligne d'un devis.

    Pour une demande structurée, medication_item identifie
    le médicament demandé.

    Pour une ancienne demande par ordonnance, photo ou texte
    libre, les informations du médicament sont saisies dans
    name, dosage et unit.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    quote = models.ForeignKey(
        PharmacyQuote,
        on_delete=models.CASCADE,
        related_name="items",
    )

    medication_item = models.ForeignKey(
        MedicationRequestItem,
        on_delete=models.PROTECT,
        related_name="quote_items",
        null=True,
        blank=True,
    )

    name = models.CharField(
        max_length=255,
    )

    dosage = models.CharField(
        max_length=100,
        blank=True,
    )

    unit = models.CharField(
        max_length=20,
        choices=MedicationRequestItem.Unit.choices,
        default=MedicationRequestItem.Unit.BOX,
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    unit_price = models.PositiveBigIntegerField(
        help_text="Prix unitaire en FCFA.",
    )

    subtotal = models.PositiveBigIntegerField(
        help_text="Sous-total en FCFA.",
    )

    position = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        ordering = ["position", "id"]

        constraints = [
            models.UniqueConstraint(
                fields=["quote", "medication_item"],
                name="unique_quote_medication_item",
            ),
        ]

    def __str__(self):
        return (
            f"{self.name} - {self.quantity} x "
            f"{self.unit_price} FCFA"
        )
