import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        PATIENT = "PATIENT", "Patient"
        PHARMACY_STAFF = "PHARMACY_STAFF", "Pharmacy staff"
        ADMIN = "ADMIN", "Admin"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    phone_number = models.CharField(
        max_length=20,
        unique=True,
    )

    email = models.EmailField(
        blank=True,
        null=True,
    )

    first_name = models.CharField(
        max_length=150,
        blank=True,
    )

    last_name = models.CharField(
        max_length=150,
        blank=True,
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PATIENT,
    )

    is_phone_verified = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "phone_number"

    def __str__(self):
        return self.phone_number+" - "+self.last_name+" "+self.first_name


class PhoneVerification(models.Model):
    class Purpose(models.TextChoices):
        REGISTRATION = "REGISTRATION", "Registration"
        PASSWORD_RESET = "PASSWORD_RESET", "Password reset"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    phone_number = models.CharField(max_length=20)

    code_hash = models.CharField(max_length=255)

    purpose = models.CharField(
        max_length=30,
        choices=Purpose.choices,
    )

    attempts = models.PositiveSmallIntegerField(default=0)

    expires_at = models.DateTimeField()

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    consumed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.phone_number} - {self.purpose}"