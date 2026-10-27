from django.contrib.gis.geos import Point
from django.test import TestCase

from apps.accounts.models import User
from apps.pharmacies.models import Pharmacy
from apps.medication_requests.models import (
    MedicationRequest,
    PharmacyAssignment,
)
from apps.medication_requests.services.partial import (
    PartialDecisionService,
)


class PartialDecisionServiceTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            phone_number="07 01 02 03 04",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.pharmacy = Pharmacy.objects.create(
            name="Pharmacie Test",
            address="Cocody",
            commune="Cocody",
            location=Point(
                -4.0083,
                5.3599,
                srid=4326,
            ),
            status=Pharmacy.Status.APPROVED,
        )

    def create_partial_request(self):
        request = MedicationRequest.objects.create(
            patient=self.patient,
            input_type=MedicationRequest.InputType.TEXT,
            text="Paracetamol",
            patient_location=Point(
                -4.0080,
                5.3600,
                srid=4326,
            ),
            status=MedicationRequest.Status.PARTIAL,
        )

        PharmacyAssignment.objects.create(
            medication_request=request,
            pharmacy=self.pharmacy,
            status=PharmacyAssignment.Status.PARTIAL,
        )

        return request

    def test_patient_accepts_partial_availability(self):
        medication_request = (
            self.create_partial_request()
        )

        PartialDecisionService.decide(
            medication_request_id=medication_request.id,
            patient=self.patient,
            decision=PartialDecisionService.ACCEPT,
        )

        medication_request.refresh_from_db()

        self.assertEqual(
            medication_request.status,
            MedicationRequest.Status.PHARMACY_FOUND,
        )

    def test_patient_rejects_partial_and_matching_continues(self):
        medication_request = (
            self.create_partial_request()
        )

        PartialDecisionService.decide(
            medication_request_id=medication_request.id,
            patient=self.patient,
            decision=PartialDecisionService.REJECT,
        )

        medication_request.refresh_from_db()

        self.assertEqual(
            medication_request.status,
            MedicationRequest.Status.UNAVAILABLE,
        )