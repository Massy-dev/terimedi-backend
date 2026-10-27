
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.prelaunch.models import PharmacyPreRegistration


User = get_user_model()


class PharmacyAdminAPITests(APITestCase):

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            phone_number="+2250700000101",
            password="TestPassword123!",
        )

        self.normal_user = User.objects.create_user(
            phone_number="+2250700000102",
            password="TestPassword123!",
        )

        self.pharmacy = PharmacyPreRegistration.objects.create(
            pharmacy_name="Pharmacie Riviera",
            commune="Cocody",
            address="Riviera 2",
            contact_name="Responsable Test",
            phone="+2250700000103",
            email="pharmacie@example.com",
            is_on_duty=True,
            status=PharmacyPreRegistration.Status.NEW,
            consent_at=timezone.now(),
        )

        self.list_url = reverse(
            "prelaunch_admin:pharmacy-list"
        )

        self.detail_url = reverse(
            "prelaunch_admin:pharmacy-detail",
            kwargs={"pk": self.pharmacy.pk},
        )

        self.status_url = reverse(
            "prelaunch_admin:pharmacy-status",
            kwargs={"pk": self.pharmacy.pk},
        )

    def authenticate(self, user):
        token = AccessToken.for_user(user)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def test_anonymous_cannot_list_pharmacies(self):
        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_normal_user_cannot_list_pharmacies(self):
        self.authenticate(self.normal_user)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_can_list_pharmacies(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["pharmacy_name"],
            "Pharmacie Riviera",
        )

    def test_filter_by_commune(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"commune": "Cocody"},
        )

        self.assertEqual(response.data["count"], 1)

        response = self.client.get(
            self.list_url,
            {"commune": "Yopougon"},
        )

        self.assertEqual(response.data["count"], 0)

    def test_search_pharmacy(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"search": "Riviera"},
        )

        self.assertEqual(response.data["count"], 1)

    def test_filter_by_status(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"status": "NEW"},
        )

        self.assertEqual(response.data["count"], 1)

        response = self.client.get(
            self.list_url,
            {"status": "APPROVED"},
        )

        self.assertEqual(response.data["count"], 0)

    def test_admin_can_view_pharmacy_detail(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            str(self.pharmacy.pk),
        )

    def test_admin_can_update_pharmacy_status(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.status_url,
            {"status": "CONTACTED"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.pharmacy.refresh_from_db()

        self.assertEqual(
            self.pharmacy.status,
            PharmacyPreRegistration.Status.CONTACTED,
        )

    def test_invalid_status_is_rejected(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.status_url,
            {"status": "INVALID"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.pharmacy.refresh_from_db()

        self.assertEqual(
            self.pharmacy.status,
            PharmacyPreRegistration.Status.NEW,
        )

    def test_normal_user_cannot_update_status(self):
        self.authenticate(self.normal_user)

        response = self.client.patch(
            self.status_url,
            {"status": "APPROVED"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.pharmacy.refresh_from_db()

        self.assertEqual(
            self.pharmacy.status,
            PharmacyPreRegistration.Status.NEW,
        )

    def test_cannot_modify_other_fields_via_status(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.status_url,
            {
                "status": "CONTACTED",
                "phone": "+2250700000999",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.pharmacy.refresh_from_db()

        self.assertEqual(
            self.pharmacy.phone,
            "+2250700000103",
        )
