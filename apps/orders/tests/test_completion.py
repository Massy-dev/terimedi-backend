from datetime import timedelta

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.medication_requests.models import (
    MedicationRequest,
    PharmacyAssignment,
)
from apps.pharmacies.models import (
    Pharmacy,
    PharmacyMembership,
)
from apps.orders.models import Order
from apps.orders.services.orders import OrderService


class OrderCompletionTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            phone_number="07 01 02 03 04",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.staff = User.objects.create_user(
            phone_number="07 02 03 04 05",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.other_staff = User.objects.create_user(
            phone_number="07 03 04 05 06",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.pharmacy = Pharmacy.objects.create(
            name="Pharmacie A",
            address="Cocody",
            commune="Cocody",
            location=Point(
                -4.0083,
                5.3599,
                srid=4326,
            ),
            status=Pharmacy.Status.APPROVED,
            is_active=True,
        )

        self.other_pharmacy = Pharmacy.objects.create(
            name="Pharmacie B",
            address="Marcory",
            commune="Marcory",
            location=Point(
                -4.0200,
                5.3000,
                srid=4326,
            ),
            status=Pharmacy.Status.APPROVED,
            is_active=True,
        )

        PharmacyMembership.objects.create(
            pharmacy=self.pharmacy,
            user=self.staff,
        )

        PharmacyMembership.objects.create(
            pharmacy=self.other_pharmacy,
            user=self.other_staff,
        )

        self.medication_request = (
            MedicationRequest.objects.create(
                patient=self.patient,
                input_type=MedicationRequest.InputType.TEXT,
                text="Paracetamol",
                patient_location=Point(
                    -4.0080,
                    5.3600,
                    srid=4326,
                ),
                status=MedicationRequest.Status.READY,
            )
        )

        self.assignment = PharmacyAssignment.objects.create(
            medication_request=self.medication_request,
            pharmacy=self.pharmacy,
            status=PharmacyAssignment.Status.ACCEPTED,
        )

        self.order = Order.objects.create(
            medication_request=self.medication_request,
            patient=self.patient,
            pharmacy=self.pharmacy,
            assignment=self.assignment,
            status=Order.Status.READY,
            pickup_code="482731",
            ready_at=timezone.now(),
            reservation_expires_at=(
                timezone.now() + timedelta(hours=12)
            ),
        )

    def test_correct_pickup_code_completes_order(self):
        order = OrderService.complete_order(
            order_id=self.order.id,
            pharmacy_user=self.staff,
            pickup_code="482731",
        )

        order.refresh_from_db()
        self.medication_request.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.Status.COMPLETED,
        )

        self.assertIsNotNone(
            order.completed_at
        )

        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.COMPLETED,
        )

    def test_wrong_pickup_code_increments_attempts(self):
        result = OrderService.complete_order(
            order_id=self.order.id,
            pharmacy_user=self.staff,
            pickup_code="000000",
        )

        self.order.refresh_from_db()

        self.assertIsNone(result)

        self.assertEqual(
            self.order.pickup_code_attempts,
            1,
        )

        self.assertEqual(
            self.order.status,
            Order.Status.READY,
        )

    def test_other_pharmacy_cannot_complete_order(self):
        with self.assertRaises(ValueError):
            OrderService.complete_order(
                order_id=self.order.id,
                pharmacy_user=self.other_staff,
                pickup_code="482731",
            )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.READY,
        )