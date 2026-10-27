
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.prelaunch.models import PharmacyPreRegistration
from apps.prelaunch_admin.models import PharmacyStatusAudit


User = get_user_model()


class PharmacyAuditTests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            phone_number="+2250700000201",
            password="TestPassword123!",
        )

        self.normal_user = User.objects.create_user(
            phone_number="+2250700000202",
            password="TestPassword123!",
        )

        self.pharmacy = PharmacyPreRegistration.objects.create(
            pharmacy_name="Pharmacie Audit Test",
            commune="Cocody",
            address="Riviera",
            contact_name="Responsable Audit",
            phone="+2250700000203",
            consent_at=timezone.now(),
            status=PharmacyPreRegistration.Status.NEW,
        )

        self.status_url = reverse(
            "prelaunch_admin:pharmacy-status",
            kwargs={"pk": self.pharmacy.pk},
        )

        self.history_url = reverse(
            "prelaunch_admin:pharmacy-history",
            kwargs={"pk": self.pharmacy.pk},
        )

    def authenticate(self, user):
        token = AccessToken.for_user(user)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def test_status_change_creates_audit(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            self.status_url,
            {"status": "CONTACTED"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        audit = PharmacyStatusAudit.objects.get(
            pharmacy=self.pharmacy
        )

        self.assertEqual(audit.actor, self.admin)
        self.assertEqual(audit.old_status, "NEW")
        self.assertEqual(audit.new_status, "CONTACTED")

    def test_unchanged_status_does_not_create_audit(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            self.status_url,
            {"status": "NEW"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            PharmacyStatusAudit.objects.filter(
                pharmacy=self.pharmacy
            ).exists()
        )

    def test_multiple_changes_create_history(self):
        self.authenticate(self.admin)

        self.client.patch(
            self.status_url,
            {"status": "CONTACTED"},
            format="json",
        )

        self.client.patch(
            self.status_url,
            {"status": "INTERESTED"},
            format="json",
        )

        self.assertEqual(
            PharmacyStatusAudit.objects.filter(
                pharmacy=self.pharmacy
            ).count(),
            2,
        )

    def test_admin_can_read_history(self):
        self.authenticate(self.admin)

        self.client.patch(
            self.status_url,
            {"status": "CONTACTED"},
            format="json",
        )

        response = self.client.get(self.history_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["new_status"],
            "CONTACTED",
        )

    def test_anonymous_cannot_read_history(self):
        response = self.client.get(self.history_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_normal_user_cannot_read_history(self):
        self.authenticate(self.normal_user)

        response = self.client.get(self.history_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_normal_user_cannot_create_audit(self):
        self.authenticate(self.normal_user)

        response = self.client.patch(
            self.status_url,
            {"status": "APPROVED"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        self.assertEqual(
            PharmacyStatusAudit.objects.count(),
            0,
        )

    def test_audit_failure_rolls_back_status(self):
        self.authenticate(self.admin)

        with patch.object(
            PharmacyStatusAudit.objects,
            "create",
            side_effect=IntegrityError("Audit failure"),
        ):
            with self.assertRaises(IntegrityError):
                self.client.patch(
                    self.status_url,
                    {"status": "CONTACTED"},
                    format="json",
                )

        self.pharmacy.refresh_from_db()

        self.assertEqual(
            self.pharmacy.status,
            PharmacyPreRegistration.Status.NEW,
        )

        self.assertEqual(
            PharmacyStatusAudit.objects.count(),
            0,
        )
