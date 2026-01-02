from django.contrib import admin
from .models import *

# Register your models here.

admin.site.register(OrderItem)
@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'statut', 'date_commande', 'pharmacie')
    list_filter = ('statut', 'date_commande')
    search_fields = ('client__email', 'pharmacie__nom')