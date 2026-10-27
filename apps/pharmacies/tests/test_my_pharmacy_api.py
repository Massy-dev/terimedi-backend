from django.contrib.gis.geos import Point
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.pharmacies.models import (
    Pharmacy,
    PharmacyMembership,
)


class MyPharmacyAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone_number="07 20 00 00 01",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.manager = User.objects.create_user(
            phone_number="07 20 00 00 02",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.staff = User.objects.create_user(
            phone_number="07 20 00 00 03",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.patient = User.objects.create_user(
            phone_number="07 20 00 00 04",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.pharmacy = Pharmacy.objects.create(
            name="Pharmacie TeriMedi Profile Test",
            phone_number="07 20 00 00 10",
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

        PharmacyMembership.objects.create(
            pharmacy=self.pharmacy,
            user=self.owner,
            role=PharmacyMembership.Role.OWNER,
        )

        PharmacyMembership.objects.create(
            pharmacy=self.pharmacy,
            user=self.manager,
            role=PharmacyMembership.Role.MANAGER,
        )

        PharmacyMembership.objects.create(
            pharmacy=self.pharmacy,
            user=self.staff,
            role=PharmacyMembership.Role.STAFF,
        )

        self.url = reverse("pharmacies:my-pharmacy")

    def authenticate(self, user):
        refresh = RefreshToken.for_user(user)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}"
        )

    def test_owner_can_read_my_pharmacy(self):
        self.authenticate(self.owner)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            str(self.pharmacy.id),
        )

        self.assertEqual(
            response.data["name"],
            self.pharmacy.name,
        )

        self.assertEqual(
            response.data["membership_role"],
            PharmacyMembership.Role.OWNER,
        )

        self.assertTrue(
            response.data["can_manage_opening_hours"]
        )

    def test_manager_can_manage_opening_hours(self):
        self.authenticate(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["membership_role"],
            PharmacyMembership.Role.MANAGER,
        )

        self.assertTrue(
            response.data["can_manage_opening_hours"]
        )

    def test_staff_has_read_only_schedule_access(self):
        self.authenticate(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["membership_role"],
            PharmacyMembership.Role.STAFF,
        )

        self.assertFalse(
            response.data["can_manage_opening_hours"]
        )

    def test_patient_cannot_access_my_pharmacy(self):
        self.authenticate(self.patient)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_access_my_pharmacy(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_pharmacy_staff_without_membership_gets_404(self):
        user = User.objects.create_user(
            phone_number="07 20 00 00 05",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.authenticate(user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_inactive_membership_is_not_accepted(self):
        membership = PharmacyMembership.objects.get(
            pharmacy=self.pharmacy,
            user=self.staff,
        )

        membership.is_active = False
        membership.save(update_fields=["is_active"])

        self.authenticate(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_inactive_pharmacy_is_not_returned(self):
        self.pharmacy.is_active = False
        self.pharmacy.save(update_fields=["is_active"])

        self.authenticate(self.owner)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )