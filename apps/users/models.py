from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('client', 'Client'),
        ('pharmacien', 'Pharmacien'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='client')
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.role})"
