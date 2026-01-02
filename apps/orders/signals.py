"""
Signals Django pour déclencher automatiquement les notifications
lors des changements de commandes
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.orders.models import Commande as Order  # Adaptez selon votre modèle
from apps.notifications.helpers import (
    notify_order_created,
    notify_order_status_change,
    get_pharmacy_staff,
)


@receiver(post_save, sender=Order)
def order_created_handler(sender, instance, created, **kwargs):
    """
    Déclenché quand une nouvelle commande est créée
    """
    if created:
        # Nouvelle commande créée
        print(f"Signal: Nouvelle commande #{instance.order_number} créée")
        
        # Notifier le client et la pharmacie
        pharmacy_users = get_pharmacy_staff()
        print("instance dans signal--------- ",pharmacy_users)
        notify_order_created(
            order=instance,
            client=instance.client,  # Adaptez selon votre modèle
            pharmacy_users=pharmacy_users
        )


@receiver(pre_save, sender=Order)
def order_status_changed_handler(sender, instance, **kwargs):
    """
    Déclenché AVANT la sauvegarde pour détecter les changements de statut
    """
    if instance.pk:  # L'objet existe déjà (pas une création)
        try:
            # Récupérer l'ancien statut
            old_instance = Order.objects.get(pk=instance.pk)
            old_status = old_instance.statut
            new_status = instance.statut
            
            # Si le statut a changé
            if old_status != new_status:
                print(f"Signal: Commande #{instance.order_number} - Statut changé de {old_status} à {new_status}")
                
                # Stocker pour utilisation dans post_save
                instance._status_changed = True
                instance._old_status = old_status
                instance._new_status = new_status
        except Order.DoesNotExist:
            pass


@receiver(post_save, sender=Order)
def order_status_changed_notification(sender, instance, created, **kwargs):
    """
    Déclenché APRÈS la sauvegarde pour envoyer les notifications de changement de statut
    """
    if not created and hasattr(instance, '_status_changed') and instance._status_changed:
        # Le statut a changé, envoyer la notification appropriée
        notify_order_status_change(
            order=instance,
            old_status=instance._old_status,
            new_status=instance._new_status
        )
        
        # Nettoyer les attributs temporaires
        delattr(instance, '_status_changed')
        delattr(instance, '_old_status')
        delattr(instance, '_new_status')


# Alternative: Si vous préférez une approche manuelle sans signals,
# vous pouvez appeler directement les helpers dans vos views/serializers