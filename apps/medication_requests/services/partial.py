from django.db import transaction

from ..models import (
    MedicationRequest,
    PharmacyAssignment,
)
from .matching import MatchingService


class PartialDecisionService:
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"

    @classmethod
    @transaction.atomic
    def decide(
        cls,
        *,
        medication_request_id,
        patient,
        decision,
    ):
        try:
            medication_request = (
                MedicationRequest.objects
                .select_for_update()
                .get(
                    id=medication_request_id,
                    patient=patient,
                )
            )
        except MedicationRequest.DoesNotExist as exc:
            raise ValueError(
                "Medication request not found."
            ) from exc

        if (
            medication_request.status
            != MedicationRequest.Status.PARTIAL
        ):
            raise ValueError(
                "This request is not awaiting a partial decision."
            )

        assignment = (
            medication_request.assignments
            .filter(
                status=PharmacyAssignment.Status.PARTIAL,
            )
            .order_by("-responded_at")
            .first()
        )

        if assignment is None:
            raise ValueError(
                "No partial pharmacy response found."
            )

        if decision == cls.ACCEPT:
            medication_request.status = (
                MedicationRequest.Status.PHARMACY_FOUND
            )

            medication_request.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            return medication_request

        if decision == cls.REJECT:
            assignment.status = (
                PharmacyAssignment.Status.REJECTED
            )

            assignment.save(
                update_fields=["status"]
            )

            medication_request.status = (
                MedicationRequest.Status.MATCHING
            )

            medication_request.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            MatchingService.assign_next_pharmacy(
                medication_request.id
            )

            return medication_request

        raise ValueError("Invalid decision.")