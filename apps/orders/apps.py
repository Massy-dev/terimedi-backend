from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.orders'
    def ready(self):
        # Importer les signals pour les enregistrer
        from apps.orders import signals