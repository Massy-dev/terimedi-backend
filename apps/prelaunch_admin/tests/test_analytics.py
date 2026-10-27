
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.prelaunch.models import (
    PharmacyPreRegistration,
    WaitlistEntry,
)


User = get_user_model()
ABIDJAN_TZ = ZoneInfo("Africa/Abidjan")


class PrelaunchAnalyticsAPITests(APITestCase):

    def setUp(self):
        self.url = reverse("prelaunch_admin:analytics")

        self.admin = User.objects.create_superuser(
            phone_number="+2250700000301",
            password="TestPassword123!",
        )

        self.normal_user = User.objects.create_user(
            phone_number="+2250700000302",
            password="TestPassword123!",
        )

        self.staff_user = User.objects.create_user(
            phone_number="+2250700000303",
            password="TestPassword123!",
            is_staff=True,
        )

    def authenticate(self, user):
        token = AccessToken.for_user(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def create_patient(self, phone, created_at):
        patient = WaitlistEntry.objects.create(
            phone=phone,
            first_name="Patient test",
            commune="Cocody",
            consent_at=timezone.now(),
        )

        WaitlistEntry.objects.filter(
            pk=patient.pk
        ).update(created_at=created_at)

        return patient

    def create_pharmacy(self, phone, created_at):
        pharmacy = PharmacyPreRegistration.objects.create(
            pharmacy_name="Pharmacie test",
            commune="Cocody",
            address="Adresse test",
            contact_name="Responsable test",
            phone=phone,
            consent_at=timezone.now(),
        )

        PharmacyPreRegistration.objects.filter(
            pk=pharmacy.pk
        ).update(created_at=created_at)

        return pharmacy

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

    def test_response_contains_30_days(self):
        self.authenticate(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.data["period_days"], 30)
        self.assertEqual(
            response.data["timezone"],
            "Africa/Abidjan",
        )

        self.assertEqual(
            len(response.data["patients"]),
            30,
        )

        self.assertEqual(
            len(response.data["pharmacies"]),
            30,
        )

    def test_empty_days_contain_zero(self):
        self.authenticate(self.admin)

        response = self.client.get(self.url)

        self.assertTrue(
            all(
                row["total"] == 0
                for row in response.data["patients"]
            )
        )

        self.assertTrue(
            all(
                row["total"] == 0
                for row in response.data["pharmacies"]
            )
        )

    def test_patients_are_counted_by_creation_day(self):
        self.authenticate(self.admin)

        today = timezone.localdate(timezone=ABIDJAN_TZ)

        yesterday = today - timedelta(days=1)

        yesterday_datetime = datetime.combine(
            yesterday,
            time(hour=12),
            tzinfo=ABIDJAN_TZ,
        )

        self.create_patient(
            "+2250700000311",
            yesterday_datetime,
        )

        self.create_patient(
            "+2250700000312",
            yesterday_datetime,
        )

        response = self.client.get(self.url)

        daily_counts = {
            row["date"]: row["total"]
            for row in response.data["patients"]
        }

        self.assertEqual(
            daily_counts[yesterday.isoformat()],
            2,
        )

    def test_pharmacies_are_counted_by_creation_day(self):
        self.authenticate(self.admin)

        today = timezone.localdate(timezone=ABIDJAN_TZ)

        yesterday = today - timedelta(days=1)

        yesterday_datetime = datetime.combine(
            yesterday,
            time(hour=12),
            tzinfo=ABIDJAN_TZ,
        )

        self.create_pharmacy(
            "+2250700000321",
            yesterday_datetime,
        )

        response = self.client.get(self.url)

        daily_counts = {
            row["date"]: row["total"]
            for row in response.data["pharmacies"]
        }

        self.assertEqual(
            daily_counts[yesterday.isoformat()],
            1,
        )

    def test_old_records_are_excluded(self):
        self.authenticate(self.admin)

        today = timezone.localdate(timezone=ABIDJAN_TZ)

        old_date = today - timedelta(days=35)

        old_datetime = datetime.combine(
            old_date,
            time(hour=12),
            tzinfo=ABIDJAN_TZ,
        )

        self.create_patient(
            "+2250700000331",
            old_datetime,
        )

        self.create_pharmacy(
            "+2250700000332",
            old_datetime,
        )

        response = self.client.get(self.url)

        self.assertEqual(
            sum(
                row["total"]
                for row in response.data["patients"]
            ),
            0,
        )

        self.assertEqual(
            sum(
                row["total"]
                for row in response.data["pharmacies"]
            ),
            0,
        )

    def test_response_does_not_expose_personal_data(self):
        self.authenticate(self.admin)

        self.create_patient(
            "+2250700000341",
            timezone.now(),
        )

        response = self.client.get(self.url)

        response_text = str(response.data)

        self.assertNotIn(
            "+2250700000341",
            response_text,
        )

        self.assertNotIn(
            "Patient test",
            response_text,
        )
