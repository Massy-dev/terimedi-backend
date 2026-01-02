from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .managers import CustomUserManager

class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('client', 'Client'),
        ('pharmacien', 'Pharmacien'),
        ('admin', 'Admin'),
    )

    username = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    date_joined = models.DateTimeField(auto_now_add=True)

    # Notifications
    device_token = models.TextField(null=True, blank=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []  # ⚠️ ne jamais mettre phone ici

    objects = CustomUserManager()

    def __str__(self):
        return self.phone
