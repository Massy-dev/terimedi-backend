
from django.contrib.gis.geos import Point
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.medication_requests.models import (
    MedicationRequest,
    PharmacyAssignment,
)
from apps.orders.models import Order
from apps.pharmacies.models import (
    Pharmacy,
    PharmacyMembership,
)


class PharmacyOrderDetailAPITests(APITestCase):

    def setUp(self):
        self.patient = User.objects.create_user(
            phone_number="07 21 22 23 24",
            password="TestPassword2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.staff_a = User.objects.create_user(
            phone_number="05 21 22 23 24",
            password="TestPassword2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.staff_b = User.objects.create_user(
            phone_number="01 21 22 23 24",
            password="TestPassword2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.pharmacy_a = self.create_pharmacy(
            name="Pharmacie A",
            phone="+2250700000011",
            longitude=-4.0100,
        )

        self.pharmacy_b = self.create_pharmacy(
            name="Pharmacie B",
            phone="+2250700000022",
            longitude=-4.0200,
        )

        self.membership_a = PharmacyMembership.objects.create(
            pharmacy=self.pharmacy_a,
            user=self.staff_a,
            role=PharmacyMembership.Role.STAFF,
            is_active=True,
        )

        PharmacyMembership.objects.create(
            pharmacy=self.pharmacy_b,
            user=self.staff_b,
            role=PharmacyMembership.Role.STAFF,
            is_active=True,
        )

        self.medication_request = MedicationRequest.objects.create(
            patient=self.patient,
            input_type=MedicationRequest.InputType.TEXT,
            text="Paracetamol",
            patient_location=Point(
                -4.0080,
                5.3600,
                srid=4326,
            ),
            status=MedicationRequest.Status.CONFIRMED,
        )

        self.assignment = PharmacyAssignment.objects.create(
            medication_request=self.medication_request,
            pharmacy=self.pharmacy_a,
            status=PharmacyAssignment.Status.ACCEPTED,
        )

        self.order = Order.objects.create(
            medication_request=self.medication_request,
            patient=self.patient,
            pharmacy=self.pharmacy_a,
            assignment=self.assignment,
            status=Order.Status.READY,
            pickup_code="123456",
        )

        self.url = f"/api/v1/orders/pharmacy/{self.order.id}/"

    def create_pharmacy(self, *, name, phone, longitude):
        return Pharmacy.objects.create(
            name=name,
            phone_number=phone,
            address="Cocody",
            commune="Cocody",
            location=Point(
                longitude,
                5.3600,
                srid=4326,
            ),
            status=Pharmacy.Status.APPROVED,
            is_active=True,
        )

    def test_authorized_staff_can_read_order_details(self):
        self.client.force_authenticate(user=self.staff_a)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["id"],
            str(self.order.id),
        )
        self.assertIn("requested_medications", response.data)
        self.assertIn("quote", response.data)

    def test_pharmacy_detail_does_not_expose_pickup_code(self):
        self.client.force_authenticate(user=self.staff_a)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("pickup_code", response.data)

        self.order.refresh_from_db()
        self.assertEqual(self.order.pickup_code, "123456")

    def test_other_pharmacy_cannot_read_order(self):
        self.client.force_authenticate(user=self.staff_b)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_inactive_membership_cannot_read_order(self):
        self.membership_a.is_active = False
        self.membership_a.save(update_fields=["is_active"])

        self.client.force_authenticate(user=self.staff_a)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_patient_cannot_access_pharmacy_detail(self):
        self.client.force_authenticate(user=self.patient)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_read_order(self):
        response = self.client.get(self.url)

        self.assertIn(response.status_code, (401, 403))
