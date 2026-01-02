# Create your models here.
from django.db import models
from django.contrib.gis.db import models as geomodels
from django.contrib.gis.geos import Point
from django.conf import settings
from django.contrib.auth import get_user_model
from apps.users.models import CustomUser

User = get_user_model()


class Pharmacy(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    phone_number = models.CharField(max_length=20)
    latitude = models.DecimalField(max_digits=20, decimal_places=18)
    longitude = models.DecimalField(max_digits=20, decimal_places=18)
    location = geomodels.PointField(geography=True, null=True, blank=True)

    logo = models.ImageField(upload_to='pharmacies/logos/', null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="pharmacies"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_open = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    device_tokens = models.JSONField(default=list, blank=True)  # stocke tokens FCM
    email = models.EmailField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.latitude and self.longitude:
            self.location = Point(float(self.longitude), float(self.latitude))
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
