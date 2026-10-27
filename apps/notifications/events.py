from django.db import transaction

from apps.pharmacies.models import PharmacyMembership

from .models import Notification
from .tasks import send_user_push_task


def queue_user_notification(
    *,
    user_id,
    title,
    body,
    data=None,
):
    payload = {
        str(key): str(value)
        for key, value in (data or {}).items()
    }

    # Enregistrer la notification dans la transaction courante.
    notification = Notification.objects.create(
        user_id=user_id,
        title=title,
        body=body,
        data=payload,
    )

    # Conserver le mécanisme Firebase existant.
    # L'envoi ne démarre qu'après validation de la transaction.
    transaction.on_commit(
        lambda: send_user_push_task.delay(
            str(user_id),
            title,
            body,
            payload,
        )
    )

    return notification


def queue_pharmacy_notification(
    *,
    pharmacy_id,
    title,
    body,
    data=None,
):
    user_ids = list(
        PharmacyMembership.objects.filter(
            pharmacy_id=pharmacy_id,
            is_active=True,
            user__is_active=True,
        )
        .values_list("user_id", flat=True)
        .distinct()
    )

    for user_id in user_ids:
        queue_user_notification(
            user_id=user_id,
            title=title,
            body=body,
            data=data,
        )