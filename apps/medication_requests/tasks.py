from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import (
    MedicationRequest,
    PharmacyAssignment,
)
from .services.matching import MatchingService


@shared_task
def expire_pending_assignments():
    now = timezone.now()

    assignment_ids = list(
        PharmacyAssignment.objects.filter(
            status=PharmacyAssignment.Status.PENDING,
            expires_at__isnull=False,
            expires_at__lte=now,
        ).values_list(
            "id",
            flat=True,
        )
    )

    expired_count = 0

    for assignment_id in assignment_ids:
        with transaction.atomic():
            assignment = (
                PharmacyAssignment.objects
                .select_for_update()
                .select_related("medication_request")
                .get(id=assignment_id)
            )

            if (
                assignment.status
                != PharmacyAssignment.Status.PENDING
            ):
                continue

            if (
                assignment.expires_at is None
                or assignment.expires_at > timezone.now()
            ):
                continue

            medication_request = (
                assignment.medication_request
            )

            if (
                medication_request.status
                != MedicationRequest.Status.MATCHING
            ):
                continue

            assignment.status = (
                PharmacyAssignment.Status.EXPIRED
            )
            assignment.responded_at = timezone.now()

            assignment.save(
                update_fields=[
                    "status",
                    "responded_at",
                ]
            )

            expired_count += 1

        MatchingService.assign_next_pharmacy(
            medication_request.id
        )

    return expired_count