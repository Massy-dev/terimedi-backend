"""
Helpers pour envoyer des notifications lors des événements de commande
"""
from apps.users.models import CustomUser as User
from .services import notification_service


def notify_order_created(order, client: User, pharmacy_users: list = None):
    """
    Notifier la création d'une commande
    - Client reçoit une confirmation
    - Pharmacie/Admin reçoit une alerte de nouvelle commande
    """
    # Notification au client
    notification_service.send_notification(
        user=client,
        notification_type='order_created',
        title='Commande créée',
        body=f'Votre commande #{order.order_number} a été créée avec succès.',
        data={
            'order_id': str(order.id),
            'order_number': str(order.order_number),
            'total_amount': str(order.total_amount) if hasattr(order, 'total_amount') else None,
        }
    )
    
    # Notification aux pharmaciens/admins
    if pharmacy_users:
        for pharmacy_user in pharmacy_users:
            notification_service.send_notification(
                user=pharmacy_user,
                notification_type='order_created',
                title='Nouvelle commande',
                body=f'Nouvelle commande #{order.order_number} de {client.phone}',
                data={
                    'order_id': str(order.id),
                    'customer_name': client.phone,
                    'order_number': str(order.order_number),
                },
                force_fcm=True  # Forcer FCM pour alerter même si app fermée
            )


def notify_order_confirmed(order, customer: User):
    """
    Notifier la confirmation d'une commande
    """
    notification_service.send_notification(
        user=customer,
        notification_type='order_confirmed',
        title='Commande confirmée',
        body=f'Votre commande #{order.order_number} a été confirmée par la pharmacie.',
        data={
            'order_id': str(order.id),
            'order_number': str(order.order_number),
        }
    )

def notify_order_quote(order, customer: User):
    """
    Notifier l'envoie d'un devis
    """
    notification_service.send_notification(
        user=customer,
        notification_type='quote_sent',
        title='Devis envoyé',
        body=f'Vous avez reçu un devis pour votre commande #{order.order_number} de la pharmacie.',
        data={
            'order_id': str(order.id),
            'order_number': str(order.order_number),
        }
    )


def notify_order_preparing(order, customer: User):
    """
    Notifier que la commande est en préparation
    """
    notification_service.send_notification(
        user=customer,
        notification_type='order_preparing',
        title='Commande en préparation',
        body=f'Votre commande #{order.order_number} est en cours de préparation.',
        data={
            'order_id': str(order.id),
            'order_number': str(order.id),
        }
    )


def notify_order_ready(order, customer: User):
    """
    Notifier que la commande est prête
    """
    notification_service.send_notification(
        user=customer,
        notification_type='order_ready',
        title='Commande prête',
        body=f'Votre commande #{order.id} est prête pour le retrait/la livraison.',
        data={
            'order_id': str(order.id),
            'order_number': str(order.id),
        },
        force_fcm=True  # Important pour alerter le client
    )


def notify_order_delivering(order, customer: User, delivery_info: dict = None):
    """
    Notifier que la commande est en cours de livraison
    """
    body = f'Votre commande #{order.order_number} est en cours de livraison.'
    if delivery_info and delivery_info.get('estimated_time'):
        body += f' Arrivée estimée: {delivery_info["estimated_time"]}'
    
    notification_service.send_notification(
        user=customer,
        notification_type='order_delivering',
        title='Commande en livraison',
        body=body,
        data={
            'order_id': str(order.id),
            'order_number': str(order.order_number),
            **(delivery_info or {}),
        },
        force_fcm=True
    )

def notify_order_delivered(order, customer: User):
    """
    Notifier que la commande a été livrée
    """
    notification_service.send_notification(
        user=customer,
        notification_type='order_delivered',
        title='Commande livrée',
        body=f'Votre commande #{order.order_number} a été livrée avec succès. Merci!',
        data={
            'order_id': str(order.id),
            'order_number': str(order.order_number),
        }
    )


def notify_order_cancelled(order, customer: User, reason: str = None):
    """
    Notifier l'annulation d'une commande
    """
    body = f'Votre commande #{order.order_number} a été annulée.'
    if reason:
        body += f' Raison: {reason}'
    
    notification_service.send_notification(
        user=customer,
        notification_type='order_cancelled',
        title='Commande annulée',
        body=body,
        data={
            'order_id': str(order.id),
            'order_number': str(order.order_number),
            'reason': reason,
        },
        force_fcm=True
    )


def get_pharmacy_staff():
    """
    Récupérer les utilisateurs pharmaciens/admins à notifier
    Adaptez selon votre système de rôles
    """
    # Exemple avec des groupes Django
    from django.contrib.auth.models import Group
    
    try:
        pharmacy_group = Group.objects.get(name='Pharmacien')
        return pharmacy_group.user_set.filter(is_active=True)
    except Group.DoesNotExist:
        # Fallback: tous les staff
        return User.objects.filter(is_staff=True, is_active=True)


# Fonction utilitaire pour notifier selon le statut
def notify_order_status_change(order, old_status, new_status):
    """
    Fonction générique pour notifier un changement de statut
    
    Args:
        order: L'objet commande
        old_status: Ancien statut
        new_status: Nouveau statut
    """
    customer = order.client  # Adaptez selon votre modèle
    
    status_handlers = {
        'confirmed': lambda: notify_order_confirmed(order, customer),
        'preparing': lambda: notify_order_preparing(order, customer),
        'ready': lambda: notify_order_ready(order, customer),
        'delivering': lambda: notify_order_delivering(order, customer),
        'delivered': lambda: notify_order_delivered(order, customer),
        'cancelled': lambda: notify_order_cancelled(order, customer),
    }
    
    handler = status_handlers.get(new_status)
    if handler:
        handler()
    else:
        print(f"Aucun handler pour le statut: {new_status}")