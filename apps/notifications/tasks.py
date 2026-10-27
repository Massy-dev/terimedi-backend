
import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from .services import send_push_notification

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_user_push_task(
    self,
    user_id,
    title,
    body,
    data=None,
):
    User = get_user_model()

    user = User.objects.filter(
        pk=user_id,
        is_active=True,
    ).first()

    if user is None:
        logger.info(
            "FCM skipped: user does not exist or is inactive."
        )
        return 0

    return send_push_notification(
        user=user,
        title=title,
        body=body,
        data=data or {},
    )
