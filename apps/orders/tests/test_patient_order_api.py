from django.contrib.gis.geos import Point
from rest_framework.test import APITestCase

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


class PatientOrderAPITests(APITestCase):

    def setUp(self):
        # ---------------------------------------------------------
        # Patients
        # ---------------------------------------------------------
        self.patient_a = User.objects.create_user(
            phone_number="07 01 02 03 04",
            password="TestPassword2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.patient_b = User.objects.create_user(
            phone_number="05 01 02 03 04",
            password="TestPassword2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        # ---------------------------------------------------------
        # Pharmacy staff
        # ---------------------------------------------------------
        self.pharmacy_user = User.objects.create_user(
            phone_number="01 01 02 03 04",
            password="TestPassword2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        # ---------------------------------------------------------
        # Pharmacy
        # ---------------------------------------------------------
        self.pharmacy = Pharmacy.objects.create(
            name="Pharmacie Test",
            phone_number="+2250700000000",
            address="Cocody",
            commune="Cocody",
            location=Point(
                -4.0100,
                5.3600,
                srid=4326,
            ),
            status=Pharmacy.Status.APPROVED,
            is_active=True,
        )

        PharmacyMembership.objects.create(
            pharmacy=self.pharmacy,
            user=self.pharmacy_user,
            role=PharmacyMembership.Role.STAFF,
            is_active=True,
        )

        # ---------------------------------------------------------
        # Medication requests
        # ---------------------------------------------------------
        self.request_a = self.create_medication_request(
            patient=self.patient_a,
            text="Paracetamol",
        )

        self.request_b = self.create_medication_request(
            patient=self.patient_b,
            text="Ibuprofene",
        )

        # ---------------------------------------------------------
        # Accepted assignments
        # ---------------------------------------------------------
        self.assignment_a = PharmacyAssignment.objects.create(
            medication_request=self.request_a,
            pharmacy=self.pharmacy,
            status=PharmacyAssignment.Status.ACCEPTED,
        )

        self.assignment_b = PharmacyAssignment.objects.create(
            medication_request=self.request_b,
            pharmacy=self.pharmacy,
            status=PharmacyAssignment.Status.ACCEPTED,
        )

        # ---------------------------------------------------------
        # Orders
        # ---------------------------------------------------------
        self.order_a = Order.objects.create(
            medication_request=self.request_a,
            patient=self.patient_a,
            pharmacy=self.pharmacy,
            assignment=self.assignment_a,
            status=Order.Status.CONFIRMED,
        )

        self.order_b = Order.objects.create(
            medication_request=self.request_b,
            patient=self.patient_b,
            pharmacy=self.pharmacy,
            assignment=self.assignment_b,
            status=Order.Status.CONFIRMED,
        )

    def create_medication_request(self, *, patient, text):
        return MedicationRequest.objects.create(
            patient=patient,
            input_type=MedicationRequest.InputType.TEXT,
            text=text,
            patient_location=Point(
                -4.0080,
                5.3600,
                srid=4326,
            ),
            status=MedicationRequest.Status.CONFIRMED,
        )

    def test_patient_list_contains_only_own_orders(self):
        """
        Patient A must only see Patient A's orders.
        """

        self.client.force_authenticate(
            user=self.patient_a,
        )

        response = self.client.get(
            "/api/v1/orders/"
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
            str(self.order_a.id),
            returned_ids,
        )

        self.assertNotIn(
            str(self.order_b.id),
            returned_ids,
        )

    def test_patient_cannot_read_another_patients_order(self):
        """
        Patient A must not be able to discover Patient B's order.

        We deliberately expect 404 instead of 403 so the API
        does not reveal whether another patient's order exists.
        """

        self.client.force_authenticate(
            user=self.patient_a,
        )

        response = self.client.get(
            f"/api/v1/orders/{self.order_b.id}/"
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_pharmacy_ready_response_does_not_expose_pickup_code(self):
        """
        A pharmacy may mark an order as READY, but the API response
        must never reveal the expected pickup code to the pharmacy.
        """

        self.client.force_authenticate(
            user=self.pharmacy_user,
        )

        response = self.client.post(
            f"/api/v1/orders/{self.order_a.id}/ready/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.order_a.refresh_from_db()

        # The code must actually have been generated internally.
        self.assertTrue(
            self.order_a.pickup_code
        )

        self.assertEqual(
            len(self.order_a.pickup_code),
            6,
        )

        # But it must NOT be exposed to the pharmacy.
        self.assertNotIn(
            "pickup_code",
            response.data,
        )