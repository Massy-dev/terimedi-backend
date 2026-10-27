
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.prelaunch.models import PharmacyPreRegistration
from apps.prelaunch_admin.models import PharmacyStatusAudit


User = get_user_model()


class AdminActivityAPITests(APITestCase):

    def setUp(self):
        self.url = reverse("prelaunch_admin:activity-list")

        self.admin = User.objects.create_superuser(
            phone_number="+2250700000401",
            password="TestPassword123!",
        )

        self.normal_user = User.objects.create_user(
            phone_number="+2250700000402",
            password="TestPassword123!",
        )

        self.staff_user = User.objects.create_user(
            phone_number="+2250700000403",
            password="TestPassword123!",
            is_staff=True,
        )

        self.pharmacy = PharmacyPreRegistration.objects.create(
            pharmacy_name="Pharmacie de Cocody",
            commune="Cocody",
            address="Riviera",
            contact_name="Responsable",
            phone="+2250700000411",
            consent_at=timezone.now(),
        )

    def authenticate(self, user):
        token = AccessToken.for_user(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def create_activity(self, old_status, new_status):
        return PharmacyStatusAudit.objects.create(
            pharmacy=self.pharmacy,
            actor=self.admin,
            old_status=old_status,
            new_status=new_status,
        )

    def test_anonymous_access_denied(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_normal_user_access_denied(self):
        self.authenticate(self.normal_user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_user_access_denied(self):
        self.authenticate(self.staff_user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_access_allowed(self):
        self.authenticate(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_empty_activity_list(self):
        self.authenticate(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_activity_contains_pharmacy_information(self):
        self.authenticate(self.admin)

        self.create_activity("NEW", "CONTACTED")

        response = self.client.get(self.url)

        activity = response.data["results"][0]

        self.assertEqual(
            activity["pharmacy_name"],
            "Pharmacie de Cocody",
        )

        self.assertEqual(
            activity["pharmacy_commune"],
            "Cocody",
        )

        self.assertEqual(
            activity["old_status"],
            "NEW",
        )

        self.assertEqual(
            activity["new_status"],
            "CONTACTED",
        )

        self.assertEqual(
            str(activity["pharmacy"]),
            str(self.pharmacy.pk),
        )

    def test_activities_ordered_newest_first(self):
        self.authenticate(self.admin)

        self.create_activity("NEW", "CONTACTED")
        self.create_activity("CONTACTED", "INTERESTED")

        response = self.client.get(self.url)

        results = response.data["results"]

        self.assertEqual(
            results[0]["new_status"],
            "INTERESTED",
        )

        self.assertEqual(
            results[1]["new_status"],
            "CONTACTED",
        )

    def test_post_not_allowed(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.url,
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_patch_not_allowed(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            self.url,
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_pagination(self):
        self.authenticate(self.admin)

        for index in range(25):
            if index % 2 == 0:
                old_status = "NEW"
                new_status = "CONTACTED"
            else:
                old_status = "CONTACTED"
                new_status = "INTERESTED"

            self.create_activity(
                old_status,
                new_status,
            )

        response = self.client.get(self.url)

        self.assertEqual(
            response.data["count"],
            25,
        )

        self.assertEqual(
            len(response.data["results"]),
            20,
        )

        response_page_2 = self.client.get(
            self.url,
            {"page": 2},
        )

        self.assertEqual(
            len(response_page_2.data["results"]),
            5,
        )
