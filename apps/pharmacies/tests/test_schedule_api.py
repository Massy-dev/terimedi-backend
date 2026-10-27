from datetime import timedelta

from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.pharmacies.models import (
    Pharmacy,
    PharmacyDutyPeriod,
    PharmacyMembership,
    PharmacyOpeningHours,
)


class PharmacyScheduleAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone_number="07 10 00 00 01",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.manager = User.objects.create_user(
            phone_number="07 10 00 00 02",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.staff = User.objects.create_user(
            phone_number="07 10 00 00 03",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.patient = User.objects.create_user(
            phone_number="07 10 00 00 04",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.pharmacy = Pharmacy.objects.create(
            name="Pharmacie TeriMedi Schedule Test",
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

        for day in range(7):
            PharmacyOpeningHours.objects.create(
                pharmacy=self.pharmacy,
                day_of_week=day,
                opens_at="08:00",
                closes_at="20:00",
                is_closed=False,
            )

        now = timezone.now()

        self.duty_period = PharmacyDutyPeriod.objects.create(
            pharmacy=self.pharmacy,
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=1, hours=12),
        )

        self.opening_hours_url = reverse(
            "pharmacies:my-opening-hours"
        )

        self.duty_periods_url = reverse(
            "pharmacies:my-duty-periods"
        )

    def authenticate(self, user):
        refresh = RefreshToken.for_user(user)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}"
        )

    def opening_hours_payload(self):
        return {
            "opening_hours": [
                {
                    "day_of_week": day,
                    "opens_at": (
                        None if day == 6 else "09:00"
                    ),
                    "closes_at": (
                        None if day == 6 else "18:00"
                    ),
                    "is_closed": day == 6,
                }
                for day in range(7)
            ]
        }

    def test_staff_can_read_opening_hours(self):
        self.authenticate(self.staff)

        response = self.client.get(
            self.opening_hours_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            7,
        )

    def test_staff_cannot_update_opening_hours(self):
        self.authenticate(self.staff)

        response = self.client.put(
            self.opening_hours_url,
            self.opening_hours_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_manager_can_update_opening_hours(self):
        self.authenticate(self.manager)

        response = self.client.put(
            self.opening_hours_url,
            self.opening_hours_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        sunday = PharmacyOpeningHours.objects.get(
            pharmacy=self.pharmacy,
            day_of_week=6,
        )

        self.assertTrue(sunday.is_closed)
        self.assertIsNone(sunday.opens_at)
        self.assertIsNone(sunday.closes_at)

    def test_owner_can_update_opening_hours(self):
        self.authenticate(self.owner)

        response = self.client.put(
            self.opening_hours_url,
            self.opening_hours_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        monday = PharmacyOpeningHours.objects.get(
            pharmacy=self.pharmacy,
            day_of_week=0,
        )

        self.assertEqual(
            monday.opens_at.strftime("%H:%M"),
            "09:00",
        )

        self.assertEqual(
            monday.closes_at.strftime("%H:%M"),
            "18:00",
        )

    def test_update_requires_all_seven_days(self):
        self.authenticate(self.owner)

        payload = self.opening_hours_payload()
        payload["opening_hours"].pop()

        response = self.client.put(
            self.opening_hours_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_update_rejects_duplicate_day(self):
        self.authenticate(self.owner)

        payload = self.opening_hours_payload()

        payload["opening_hours"][6][
            "day_of_week"
        ] = 0

        response = self.client.put(
            self.opening_hours_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_update_rejects_invalid_opening_range(self):
        self.authenticate(self.owner)

        payload = self.opening_hours_payload()

        payload["opening_hours"][0].update(
            {
                "opens_at": "20:00",
                "closes_at": "08:00",
                "is_closed": False,
            }
        )

        response = self.client.put(
            self.opening_hours_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_staff_can_read_duty_periods(self):
        self.authenticate(self.staff)

        response = self.client.get(
            self.duty_periods_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            str(response.data[0]["id"]),
            str(self.duty_period.id),
        )

    def test_patient_cannot_access_opening_hours(self):
        self.authenticate(self.patient)

        response = self.client.get(
            self.opening_hours_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_patient_cannot_access_duty_periods(self):
        self.authenticate(self.patient)

        response = self.client.get(
            self.duty_periods_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )