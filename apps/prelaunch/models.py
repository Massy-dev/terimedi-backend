import uuid

from django.db import models


class WaitlistEntry(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        VERIFIED = "VERIFIED", "Vérifié"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    phone = models.CharField(
        max_length=20,
        unique=True,
    )

    first_name = models.CharField(
        max_length=100,
        blank=True,
    )

    commune = models.CharField(
        max_length=100,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    phone_verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    referral_code = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
    )

    referred_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals",
    )

    consent_at = models.DateTimeField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.phone


class OTPVerification(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    waitlist_entry = models.ForeignKey(
        WaitlistEntry,
        on_delete=models.CASCADE,
        related_name="otp_verifications",
    )

    code_hash = models.CharField(
        max_length=255,
    )

    expires_at = models.DateTimeField()

    attempts = models.PositiveSmallIntegerField(
        default=0,
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"OTP for {self.waitlist_entry_id}"


class PharmacyPreRegistration(models.Model):

    class Status(models.TextChoices):
        NEW = "NEW", "Nouvelle"
        CONTACTED = "CONTACTED", "Contactée"
        INTERESTED = "INTERESTED", "Intéressée"
        APPROVED = "APPROVED", "Validée"
        REJECTED = "REJECTED", "Refusée"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    pharmacy_name = models.CharField(max_length=200)

    commune = models.CharField(max_length=100)

    address = models.CharField(max_length=255)

    contact_name = models.CharField(max_length=150)

    phone = models.CharField(
        max_length=20,
        unique=True,
    )

    email = models.EmailField(
        blank=True,
    )

    is_on_duty = models.BooleanField(
        default=False,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )

    consent_at = models.DateTimeField()

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Préinscription pharmacie"
        verbose_name_plural = "Préinscriptions pharmacies"

    def __str__(self):
        return f"{self.pharmacy_name} - {self.commune}"