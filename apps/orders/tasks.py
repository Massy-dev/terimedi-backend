from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.medication_requests.models import MedicationRequest

from .models import Order


@shared_task
def expire_ready_orders():
    now = timezone.now()

    order_ids = list(
        Order.objects.filter(
            status=Order.Status.READY,
            reservation_expires_at__isnull=False,
            reservation_expires_at__lte=now,
        ).values_list(
            "id",
            flat=True,
        )
    )

    expired_count = 0

    for order_id in order_ids:
        with transaction.atomic():
            order = (
                Order.objects
                .select_for_update()
                .select_related("medication_request")
                .get(id=order_id)
            )

            if order.status != Order.Status.READY:
                continue

            if (
                order.reservation_expires_at is None
                or order.reservation_expires_at > timezone.now()
            ):
                continue

            order.status = Order.Status.EXPIRED

            order.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            medication_request = (
                order.medication_request
            )

            medication_request.status = (
                MedicationRequest.Status.CANCELLED
            )

            medication_request.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            expired_count += 1

    return expired_count