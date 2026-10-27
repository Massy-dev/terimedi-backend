from django.contrib.gis.geos import Point
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.medication_requests.models import (
    MedicationRequest,
    PharmacyAssignment,
)
from apps.orders.models import Order
from apps.orders.services.orders import OrderService
from apps.pharmacies.models import (
    Pharmacy,
    PharmacyMembership,
)


class OrderWorkflowTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            phone_number="07 11 22 33 44",
            password="TestPassword2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.staff = User.objects.create_user(
            phone_number="05 11 22 33 44",
            password="TestPassword2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.other_staff = User.objects.create_user(
            phone_number="01 11 22 33 44",
            password="TestPassword2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.pharmacy = Pharmacy.objects.create(
            name="Pharmacie Workflow",
            address="Test",
            commune="Test",
            location=Point(
                -4.0083,
                5.3599,
                srid=4326,
            ),
            status=Pharmacy.Status.APPROVED,
            is_active=True,
        )

        PharmacyMembership.objects.create(
            pharmacy=self.pharmacy,
            user=self.staff,
            role=PharmacyMembership.Role.STAFF,
            is_active=True,
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
                status=MedicationRequest.Status.PHARMACY_FOUND,
            )
        )

        self.assignment = (
            PharmacyAssignment.objects.create(
                medication_request=self.medication_request,
                pharmacy=self.pharmacy,
                status=PharmacyAssignment.Status.ACCEPTED,
            )
        )

    def test_confirmation_is_idempotent(self):
        first_order = OrderService.confirm_request(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
        )

        second_order = OrderService.confirm_request(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
        )

        self.assertEqual(
            first_order.id,
            second_order.id,
        )

        self.assertEqual(
            Order.objects.filter(
                medication_request=self.medication_request,
            ).count(),
            1,
        )

    def test_pharmacy_can_list_its_orders(self):
        order = OrderService.confirm_request(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
        )

        self.client.force_authenticate(
            user=self.staff,
        )

        response = self.client.get(
            "/api/v1/orders/pharmacy/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        returned_ids = {
            item["id"]
            for item in response.data
        }

        self.assertIn(
            str(order.id),
            returned_ids,
        )

    def test_pharmacy_can_mark_order_preparing(self):
        order = OrderService.confirm_request(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
        )

        self.client.force_authenticate(
            user=self.staff,
        )

        response = self.client.post(
            f"/api/v1/orders/{order.id}/preparing/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.Status.PREPARING,
        )

    def test_unrelated_pharmacy_staff_cannot_prepare_order(self):
        order = OrderService.confirm_request(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
        )

        self.client.force_authenticate(
            user=self.other_staff,
        )

        response = self.client.post(
            f"/api/v1/orders/{order.id}/preparing/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.Status.CONFIRMED,
        )