
import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.prelaunch.models import (
    OTPVerification,
    WaitlistEntry,
)


User = get_user_model()


class PatientAdminAPITests(APITestCase):
    """
    Tests des endpoints administrateur
    de préinscription patients TeriMedi.
    """

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            phone_number="+2250700000201",
            password="TestPassword123!",
        )

        self.normal_user = User.objects.create_user(
            phone_number="+2250700000202",
            password="TestPassword123!",
        )

        self.staff_user = User.objects.create_user(
            phone_number="+2250700000203",
            password="TestPassword123!",
        )
        self.staff_user.is_staff = True
        self.staff_user.save(update_fields=["is_staff"])

        self.patient_pending = WaitlistEntry.objects.create(
            phone="+2250700000211",
            first_name="Aminata",
            commune="Cocody",
            status=WaitlistEntry.Status.PENDING,
            consent_at=timezone.now(),
            referral_code="AMINATA001",
        )

        self.patient_verified = WaitlistEntry.objects.create(
            phone="+2250700000212",
            first_name="Kouassi",
            commune="Marcory",
            status=WaitlistEntry.Status.VERIFIED,
            phone_verified_at=timezone.now(),
            consent_at=timezone.now(),
            referral_code="KOUASSI001",
            referred_by=self.patient_pending,
        )

        self.list_url = reverse(
            "prelaunch_admin:patient-list"
        )

        self.detail_url = reverse(
            "prelaunch_admin:patient-detail",
            kwargs={"pk": self.patient_pending.pk},
        )

    def authenticate(self, user):
        token = AccessToken.for_user(user)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(token)}"
        )

    # --------------------------------------------------
    # Authentification et permissions
    # --------------------------------------------------

    def test_anonymous_cannot_list_patients(self):
        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_anonymous_cannot_view_patient_detail(self):
        response = self.client.get(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_normal_user_cannot_list_patients(self):
        self.authenticate(self.normal_user)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_normal_user_cannot_view_patient_detail(self):
        self.authenticate(self.normal_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_user_cannot_list_patients(self):
        """
        is_staff=True ne doit pas suffire.
        """
        self.authenticate(self.staff_user)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_invalid_jwt_is_rejected(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Bearer invalid-token"
        )

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_inactive_superuser_is_rejected(self):
        self.admin_user.is_active = False
        self.admin_user.save(update_fields=["is_active"])

        self.authenticate(self.admin_user)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # --------------------------------------------------
    # Liste des patients
    # --------------------------------------------------

    def test_admin_can_list_patients(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_search_by_first_name(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"search": "aminata"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["count"], 1)

        self.assertEqual(
            response.data["results"][0]["first_name"],
            "Aminata",
        )

    def test_search_by_phone(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"search": "0700000212"},
        )

        self.assertEqual(response.data["count"], 1)

        self.assertEqual(
            response.data["results"][0]["phone"],
            "+2250700000212",
        )

    def test_filter_by_commune_case_insensitive(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"commune": "cocody"},
        )

        self.assertEqual(response.data["count"], 1)

        self.assertEqual(
            response.data["results"][0]["commune"],
            "Cocody",
        )

    def test_filter_by_verified_status(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"status": "VERIFIED"},
        )

        self.assertEqual(response.data["count"], 1)

        self.assertEqual(
            response.data["results"][0]["status"],
            WaitlistEntry.Status.VERIFIED,
        )

    def test_filter_by_pending_status(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"status": "PENDING"},
        )

        self.assertEqual(response.data["count"], 1)

        self.assertEqual(
            response.data["results"][0]["status"],
            WaitlistEntry.Status.PENDING,
        )

    def test_invalid_status_returns_empty_list(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"status": "INVALID"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["count"], 0)

    def test_combined_filters(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {
                "search": "Aminata",
                "commune": "Cocody",
                "status": "PENDING",
            },
        )

        self.assertEqual(response.data["count"], 1)

        response = self.client.get(
            self.list_url,
            {
                "search": "Aminata",
                "commune": "Marcory",
                "status": "PENDING",
            },
        )

        self.assertEqual(response.data["count"], 0)

    def test_pagination(self):
        """
        Le backend doit respecter la taille
        de page configurée.
        """
        for index in range(25):
            WaitlistEntry.objects.create(
                phone=f"+22508{index:08d}",
                first_name=f"Patient {index}",
                commune="Cocody",
                consent_at=timezone.now(),
            )

        self.authenticate(self.admin_user)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["count"], 27)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

        response_page_2 = self.client.get(
            self.list_url,
            {"page": 2},
        )

        self.assertEqual(
            response_page_2.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response_page_2.data["results"]),
            7,
        )

    def test_ordering_oldest_first(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"ordering": "created_at"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            str(self.patient_pending.pk),
        )

    # --------------------------------------------------
    # Dossier individuel
    # --------------------------------------------------

    def test_admin_can_view_patient_detail(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            str(self.patient_pending.pk),
        )

        self.assertEqual(
            response.data["first_name"],
            "Aminata",
        )

    def test_nonexistent_patient_returns_404(self):
        self.authenticate(self.admin_user)

        url = reverse(
            "prelaunch_admin:patient-detail",
            kwargs={"pk": uuid.uuid4()},
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_referral_information_is_correct(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["referrals_count"],
            1,
        )

        verified_url = reverse(
            "prelaunch_admin:patient-detail",
            kwargs={"pk": self.patient_verified.pk},
        )

        response = self.client.get(verified_url)

        self.assertEqual(
            response.data["referred_by"],
            self.patient_pending.pk,
        )

        self.assertEqual(
            response.data["referred_by_phone"],
            self.patient_pending.phone,
        )

    # --------------------------------------------------
    # Confidentialité et lecture seule
    # --------------------------------------------------

    def test_otp_secrets_are_not_exposed(self):
        OTPVerification.objects.create(
            waitlist_entry=self.patient_pending,
            code_hash="TEST_SECRET_HASH_123",
            expires_at=timezone.now(),
        )

        self.authenticate(self.admin_user)

        list_response = self.client.get(self.list_url)
        detail_response = self.client.get(self.detail_url)

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)

        for response in (list_response, detail_response):
            content = str(response.data)

            self.assertNotIn(
                "TEST_SECRET_HASH_123",
                content,
            )

            self.assertNotIn(
                "code_hash",
                content,
            )

            self.assertNotIn(
                "otp_verifications",
                content,
            )

    def test_patient_detail_is_read_only(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.detail_url,
            {"status": "VERIFIED"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        self.patient_pending.refresh_from_db()

        self.assertEqual(
            self.patient_pending.status,
            WaitlistEntry.Status.PENDING,
        )

    def test_patient_list_is_read_only(self):
        self.authenticate(self.admin_user)

        response = self.client.post(
            self.list_url,
            {
                "phone": "+2250700000299",
                "first_name": "Intrus",
                "commune": "Cocody",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        self.assertFalse(
            WaitlistEntry.objects.filter(
                phone="+2250700000299"
            ).exists()
        )
