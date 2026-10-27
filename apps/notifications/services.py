
import logging

import firebase_admin
from firebase_admin import credentials, messaging

from .models import DeviceToken

logger = logging.getLogger(__name__)


def get_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        return firebase_admin.initialize_app(
            credentials.ApplicationDefault()
        )


def send_push_notification(*, user, title, body, data=None):
    """
    Envoie une notification FCM aux appareils actifs
    d'un utilisateur TeriMedi.

    Retourne le nombre d'envois acceptés par FCM.
    """
    tokens = list(
        DeviceToken.objects.filter(
            user=user,
            is_active=True,
        ).values_list("token", flat=True)
    )

    if not tokens:
        return 0

    app = get_firebase_app()
    success_count = 0

    payload = {
        str(key): str(value)
        for key, value in (data or {}).items()
    }

    for token in tokens:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=payload,
            token=token,
        )

        try:
            messaging.send(message, app=app)
            success_count += 1
        except messaging.UnregisteredError:
            DeviceToken.objects.filter(
                token=token
            ).update(is_active=False)
            logger.warning(
                "FCM token unregistered; device deactivated."
            )
        except Exception:
            logger.exception(
                "FCM notification delivery failed."
            )

    return success_count
