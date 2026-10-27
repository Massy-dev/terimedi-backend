import uuid

from django.conf import settings
from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        PREPARING = "PREPARING", "Preparing"
        READY = "READY", "Ready"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    medication_request = models.OneToOneField(
        "medication_requests.MedicationRequest",
        on_delete=models.PROTECT,
        related_name="order",
    )

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    pharmacy = models.ForeignKey(
        "pharmacies.Pharmacy",
        on_delete=models.PROTECT,
        related_name="orders",
    )

    assignment = models.OneToOneField(
        "medication_requests.PharmacyAssignment",
        on_delete=models.PROTECT,
        related_name="order",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )

    pickup_code_attempts = models.PositiveSmallIntegerField(
        default=0,
    )

    pickup_code = models.CharField(
        max_length=6,
        blank=True,
    )

    reservation_expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    ready_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"Order {self.id}"