
from datetime import timedelta
from apps.notifications.events import queue_pharmacy_notification
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.pharmacies.models import Pharmacy

from ..models import (
    MedicationRequest,
    PharmacyAssignment,
)
from .availability import AvailabilityService


class MatchingService:
    @classmethod
    @transaction.atomic
    def assign_next_pharmacy(
        cls,
        medication_request_id,
    ):
        medication_request = (
            MedicationRequest.objects
            .select_for_update()
            .get(id=medication_request_id)
        )

        if medication_request.status not in {
            MedicationRequest.Status.PENDING,
            MedicationRequest.Status.MATCHING,
        }:
            return None

        current_assignment = (
            medication_request.assignments
            .filter(
                status=PharmacyAssignment.Status.PENDING
            )
            .first()
        )

        if current_assignment:
            return current_assignment

        excluded_pharmacy_ids = (
            medication_request.assignments
            .values_list("pharmacy_id", flat=True)
        )

        candidates = (
            Pharmacy.objects
            .filter(
                status=Pharmacy.Status.APPROVED,
                is_active=True,
            )
            .exclude(
                id__in=excluded_pharmacy_ids
            )
        )

        candidates = cls._available_pharmacies(
            candidates
        )

        pharmacy = cls._nearest_pharmacy(
            candidates,
            medication_request.patient_location,
        )

        if pharmacy is None:
            medication_request.status = (
                MedicationRequest.Status.UNAVAILABLE
            )

            medication_request.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            return None

        assignment = PharmacyAssignment.objects.create(
            medication_request=medication_request,
            pharmacy=pharmacy,
            expires_at=(
                timezone.now()
                + timedelta(
                    minutes=settings.MATCHING_ASSIGNMENT_TIMEOUT_MINUTES
                )
            ),
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
        queue_pharmacy_notification(
            pharmacy_id=pharmacy.id,
            title="Nouvelle demande TeriMedi",
            body="Une nouvelle demande de médicaments vous a été attribuée.",
            data={
                "type": "NEW_ASSIGNMENT",
                "assignment_id": str(assignment.id),
                "request_id": str(medication_request.id),
            },
        )
        return assignment

    @staticmethod
    def _available_pharmacies(queryset):
        now = timezone.now()

        open_ids = []

        for pharmacy in queryset.prefetch_related(
            "opening_hours",
            "duty_periods",
        ):
            if pharmacy.is_available_at(now):
                open_ids.append(pharmacy.id)

        return queryset.filter(
            id__in=open_ids
        )

    @staticmethod
    def _nearest_pharmacy(
        queryset,
        patient_location,
    ):
        from django.contrib.gis.db.models.functions import Distance

        return (
            queryset
            .annotate(
                distance=Distance(
                    "location",
                    patient_location,
                )
            )
            .order_by("distance")
            .first()
        )

    @classmethod
    @transaction.atomic
    def respond(
        cls,
        *,
        assignment_id,
        response,
        note="",
        available_items="",
        available_item_quantities=None,
    ):
        assignment = (
            PharmacyAssignment.objects
            .select_for_update()
            .select_related("medication_request")
            .get(id=assignment_id)
        )

        if assignment.status != PharmacyAssignment.Status.PENDING:
            raise ValueError(
                "Assignment has already been processed."
            )

        medication_request = assignment.medication_request

        
        if (
            medication_request.quote_requested
            and response != PharmacyAssignment.Status.REJECTED
        ):
            raise ValueError(
                "Cette demande nécessite un devis. "
                "Utilisez le service de proposition de devis "
                "pour accepter totalement ou partiellement."
            )

        if (
            medication_request.quote_requested
            and response == PharmacyAssignment.Status.REJECTED
            and (
                available_item_quantities is not None
                or available_items
            )
        ):
            raise ValueError(
                "Un refus sans devis ne doit contenir "
                "aucune disponibilité de médicament."
            )


        if medication_request.status != MedicationRequest.Status.MATCHING:
            raise ValueError(
                "This request is no longer awaiting a pharmacy response."
            )

        if (
            assignment.expires_at is not None
            and assignment.expires_at <= timezone.now()
        ):
            raise ValueError(
                "This assignment has expired."
            )

        if response not in {
            PharmacyAssignment.Status.ACCEPTED,
            PharmacyAssignment.Status.PARTIAL,
            PharmacyAssignment.Status.REJECTED,
        }:
            raise ValueError(
                "Invalid pharmacy response."
            )

        normalized_quantities = []

        if available_item_quantities is not None:
            normalized_quantities = AvailabilityService.validate(
                medication_request=medication_request,
                response=response,
                quantities=available_item_quantities,
            )

        assignment.status = response
        assignment.response_note = note
        assignment.responded_at = timezone.now()
        assignment.available_items = available_items
        assignment.available_item_quantities = normalized_quantities

        assignment.save(
            update_fields=[
                "status",
                "response_note",
                "responded_at",
                "available_items",
                "available_item_quantities",
            ]
        )

        if response == PharmacyAssignment.Status.ACCEPTED:
            medication_request.status = (
                MedicationRequest.Status.PHARMACY_FOUND
            )

        elif response == PharmacyAssignment.Status.PARTIAL:
            medication_request.status = (
                MedicationRequest.Status.PARTIAL
            )

        elif response == PharmacyAssignment.Status.REJECTED:
            medication_request.status = (
                MedicationRequest.Status.MATCHING
            )

        medication_request.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        if response == PharmacyAssignment.Status.REJECTED:
            cls.assign_next_pharmacy(
                medication_request.id
            )

        return assignment
