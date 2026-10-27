from datetime import time, timedelta

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.pharmacies.models import (
    Pharmacy,
    PharmacyDutyPeriod,
    PharmacyOpeningHours,
)
from apps.medication_requests.models import (
    MedicationRequest,
    PharmacyAssignment,
)
from apps.medication_requests.services.matching import MatchingService


class MatchingServiceTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            phone_number="07 01 02 03 04",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.patient_location = Point(
            -4.0083,
            5.3599,
            srid=4326,
        )

    def create_request(self):
        return MedicationRequest.objects.create(
            patient=self.patient,
            input_type=MedicationRequest.InputType.TEXT,
            text="Paracetamol 500 mg",
            patient_location=self.patient_location,
            fulfillment_type=(
                MedicationRequest.FulfillmentType.PICKUP
            ),
        )

    def create_pharmacy(
        self,
        *,
        name,
        longitude,
        latitude,
    ):
        return Pharmacy.objects.create(
            name=name,
            address="Abidjan",
            commune="Cocody",
            location=Point(
                longitude,
                latitude,
                srid=4326,
            ),
            status=Pharmacy.Status.APPROVED,
            is_active=True,
        )

    def make_open_now(self, pharmacy):
        now = timezone.localtime()

        PharmacyOpeningHours.objects.create(
            pharmacy=pharmacy,
            day_of_week=now.weekday(),
            opens_at=time(0, 0),
            closes_at=time(23, 59),
            is_closed=False,
        )

    def make_on_duty_now(self, pharmacy):
        now = timezone.now()

        PharmacyDutyPeriod.objects.create(
            pharmacy=pharmacy,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )

    def test_assigns_nearest_open_pharmacy(self):
        nearest = self.create_pharmacy(
            name="Nearest Pharmacy",
            longitude=-4.0090,
            latitude=5.3600,
        )

        farther = self.create_pharmacy(
            name="Farther Pharmacy",
            longitude=-4.0300,
            latitude=5.3800,
        )

        self.make_open_now(nearest)
        self.make_open_now(farther)

        medication_request = self.create_request()

        assignment = MatchingService.assign_next_pharmacy(
            medication_request.id
        )

        self.assertIsNotNone(assignment)
        self.assertEqual(
            assignment.pharmacy,
            nearest,
        )

    def test_skips_closed_nearest_pharmacy(self):
        closed_nearest = self.create_pharmacy(
            name="Closed Pharmacy",
            longitude=-4.0090,
            latitude=5.3600,
        )

        open_farther = self.create_pharmacy(
            name="Open Pharmacy",
            longitude=-4.0300,
            latitude=5.3800,
        )

        self.make_open_now(open_farther)

        medication_request = self.create_request()

        assignment = MatchingService.assign_next_pharmacy(
            medication_request.id
        )

        self.assertIsNotNone(assignment)
        self.assertEqual(
            assignment.pharmacy,
            open_farther,
        )
        self.assertNotEqual(
            assignment.pharmacy,
            closed_nearest,
        )

    def test_on_duty_pharmacy_is_eligible(self):
        pharmacy = self.create_pharmacy(
            name="Duty Pharmacy",
            longitude=-4.0090,
            latitude=5.3600,
        )

        self.make_on_duty_now(pharmacy)

        medication_request = self.create_request()

        assignment = MatchingService.assign_next_pharmacy(
            medication_request.id
        )

        self.assertIsNotNone(assignment)
        self.assertEqual(
            assignment.pharmacy,
            pharmacy,
        )

    def test_rejection_assigns_next_pharmacy(self):
        first = self.create_pharmacy(
            name="First Pharmacy",
            longitude=-4.0090,
            latitude=5.3600,
        )

        second = self.create_pharmacy(
            name="Second Pharmacy",
            longitude=-4.0300,
            latitude=5.3800,
        )

        self.make_open_now(first)
        self.make_open_now(second)

        medication_request = self.create_request()

        first_assignment = (
            MatchingService.assign_next_pharmacy(
                medication_request.id
            )
        )

        self.assertEqual(
            first_assignment.pharmacy,
            first,
        )

        MatchingService.respond(
            assignment_id=first_assignment.id,
            response=PharmacyAssignment.Status.REJECTED,
        )

        assignments = (
            medication_request.assignments
            .order_by("assigned_at")
        )

        self.assertEqual(
            assignments.count(),
            2,
        )

        self.assertEqual(
            assignments[0].pharmacy,
            first,
        )

        self.assertEqual(
            assignments[0].status,
            PharmacyAssignment.Status.REJECTED,
        )

        self.assertEqual(
            assignments[1].pharmacy,
            second,
        )

        self.assertEqual(
            assignments[1].status,
            PharmacyAssignment.Status.PENDING,
        )