from django.contrib import admin  
from leaflet.admin import LeafletGeoAdmin
from .models import *

@admin.register(Pharmacy)
class PharmacyAdmin(LeafletGeoAdmin):
    list_display = ("name", "latitude", "longitude")