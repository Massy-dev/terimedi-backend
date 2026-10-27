import secrets

from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from apps.notifications.events import (
    queue_pharmacy_notification,
    queue_user_notification,
)
from apps.medication_requests.models import (
    MedicationRequest,
    PharmacyAssignment,
    PharmacyQuote,
)

from ..models import Order

class InvalidPickupCode(Exception):
    pass

class OrderService:
    @staticmethod
    def _generate_pickup_code():
        return f"{secrets.randbelow(1_000_000):06d}"

    @classmethod
    @transaction.atomic
    def confirm_request(
        cls,
        *,
        medication_request_id,
        patient,
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

        existing_order = (
            Order.objects
            .select_related(
                "pharmacy",
                "medication_request",
            )
            .filter(
                medication_request=medication_request,
                patient=patient,
            )
            .first()
        )

        if existing_order is not None:
            return existing_order

        if (
            medication_request.status
            != MedicationRequest.Status.PHARMACY_FOUND
        ):
            raise ValueError(
                "This medication request cannot be confirmed."
            )

        assignment = (
            medication_request.assignments
            .filter(
                status__in=[
                    PharmacyAssignment.Status.ACCEPTED,
                    PharmacyAssignment.Status.PARTIAL,
                ]
            )
            .order_by("-responded_at")
            .first()
        )

        if assignment is None:
            raise ValueError(
                "No accepted pharmacy assignment found."
            )
        
        if medication_request.quote_requested:
            quote_is_accepted = PharmacyQuote.objects.filter(
                assignment=assignment,
                status=PharmacyQuote.Status.ACCEPTED,
            ).exists()

            if not quote_is_accepted:
                raise ValueError(
                    "Le patient doit accepter le devis "
                    "avant de confirmer cette commande."
                )

        order = Order.objects.create(
            medication_request=medication_request,
            patient=patient,
            pharmacy=assignment.pharmacy,
            assignment=assignment,
            status=Order.Status.CONFIRMED,
        )

        medication_request.status = (
            MedicationRequest.Status.CONFIRMED
        )

        medication_request.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )
        queue_pharmacy_notification(
            pharmacy_id=order.pharmacy_id,
            title="Commande confirmée",
            body="Un patient vient de confirmer sa commande TeriMedi.",
            data={
                "type": "ORDER_CONFIRMED",
                "order_id": str(order.id),
            },
        )
        return order

    @classmethod
    @transaction.atomic
    def mark_ready(
        cls,
        *,
        order_id,
        pharmacy_user,
    ):
        try:
            order = (
                Order.objects
                .select_for_update()
                .select_related(
                    "pharmacy",
                    "medication_request",
                )
                .get(
                    id=order_id,
                    pharmacy__memberships__user=pharmacy_user,
                    pharmacy__memberships__is_active=True,
                )
            )
        except Order.DoesNotExist as exc:
            raise ValueError(
                "Order not found."
            ) from exc

        if order.status not in {
            Order.Status.CONFIRMED,
            Order.Status.PREPARING,
        }:
            raise ValueError(
                "This order cannot be marked as ready."
            )

        now = timezone.now()

        order.status = Order.Status.READY
        order.ready_at = now
        order.reservation_expires_at = (
            now + timedelta(hours=12)
        )
        order.pickup_code = cls._generate_pickup_code()

        order.save(
            update_fields=[
                "status",
                "ready_at",
                "reservation_expires_at",
                "pickup_code",
                "updated_at",
            ]
        )

        order.medication_request.status = (
            MedicationRequest.Status.READY
        )

        order.medication_request.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        queue_user_notification(
            user_id=order.patient_id,
            title="Votre commande est prête",
            body="Votre commande TeriMedi est prête pour le retrait.",
            data={
                "type": "ORDER_READY",
                "order_id": str(order.id),
            },
        )
        return order

   
        try:
            order = (
                Order.objects
                .select_for_update()
                .select_related(
                    "pharmacy",
                    "medication_request",
                )
                .get(
                    id=order_id,
                    pharmacy__memberships__user=pharmacy_user,
                    pharmacy__memberships__is_active=True,
                )
            )
        except Order.DoesNotExist as exc:
            raise ValueError(
                "Order not found."
            ) from exc

        if order.status != Order.Status.CONFIRMED:
            raise ValueError(
                "Only a confirmed order can start preparation."
            )

        order.status = Order.Status.PREPARING

        order.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return order

    @classmethod
    @transaction.atomic
    def mark_preparing(
        cls,
        *,
        order_id,
        pharmacy_user,
    ):
        try:
            order = (
                Order.objects
                .select_for_update()
                .select_related(
                    "pharmacy",
                    "medication_request",
                )
                .get(
                    id=order_id,
                    pharmacy__memberships__user=pharmacy_user,
                    pharmacy__memberships__is_active=True,
                )
            )
        except Order.DoesNotExist as exc:
            raise ValueError(
                "Order not found."
            ) from exc

        if order.status != Order.Status.CONFIRMED:
            raise ValueError(
                "Only a confirmed order can start preparation."
            )

        order.status = Order.Status.PREPARING

        order.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return order

    MAX_PICKUP_CODE_ATTEMPTS = 5
    @classmethod
    @transaction.atomic
    def complete_order(
        cls,
        *,
        order_id,
        pharmacy_user,
        pickup_code,
    ):
        try:
            order = (
                Order.objects
                .select_for_update()
                .select_related(
                    "pharmacy",
                    "medication_request",
                )
                .get(
                    id=order_id,
                    pharmacy__memberships__user=pharmacy_user,
                    pharmacy__memberships__is_active=True,
                )
            )
        except Order.DoesNotExist as exc:
            raise ValueError(
                "Order not found."
            ) from exc

        if order.status != Order.Status.READY:
            raise ValueError(
                "Only a ready order can be completed."
            )

        now = timezone.now()

        if (
            order.reservation_expires_at
            and now >= order.reservation_expires_at
        ):
            order.status = Order.Status.EXPIRED

            order.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            raise ValueError(
                "Reservation has expired."
            )

        if (
            order.pickup_code_attempts
            >= cls.MAX_PICKUP_CODE_ATTEMPTS
        ):
            raise ValueError(
                "Maximum pickup code attempts reached."
            )

        if not secrets.compare_digest(
            order.pickup_code,
            pickup_code,
        ):
            order.pickup_code_attempts += 1

            order.save(
                update_fields=[
                    "pickup_code_attempts",
                    "updated_at",
                ]
            )

            return None

        order.status = Order.Status.COMPLETED
        order.completed_at = now

        order.save(
            update_fields=[
                "status",
                "completed_at",
                "updated_at",
            ]
        )

        order.medication_request.status = (
            MedicationRequest.Status.COMPLETED
        )

        order.medication_request.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return order