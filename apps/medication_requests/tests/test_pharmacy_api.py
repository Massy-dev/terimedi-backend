import shutil
import tempfile
from datetime import time

from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.pharmacies.models import (
    Pharmacy,
    PharmacyMembership,
    PharmacyOpeningHours,
)
from apps.medication_requests.models import (
    MedicationRequest,
    PharmacyAssignment,
)


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class PharmacyAssignmentAPITests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(
            TEST_MEDIA_ROOT,
            ignore_errors=True,
        )

    def setUp(self):
        self.patient = User.objects.create_user(
            phone_number="07 01 02 03 04",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.staff = User.objects.create_user(
            phone_number="07 02 03 04 05",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.other_staff = User.objects.create_user(
            phone_number="07 03 04 05 06",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.pharmacy = Pharmacy.objects.create(
            name="Pharmacie A",
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

        self.other_pharmacy = Pharmacy.objects.create(
            name="Pharmacie B",
            address="Marcory",
            commune="Marcory",
            location=Point(
                -4.0200,
                5.3000,
                srid=4326,
            ),
            status=Pharmacy.Status.APPROVED,
            is_active=True,
        )

        PharmacyMembership.objects.create(
            pharmacy=self.pharmacy,
            user=self.staff,
            role=PharmacyMembership.Role.STAFF,
        )

        PharmacyMembership.objects.create(
            pharmacy=self.other_pharmacy,
            user=self.other_staff,
            role=PharmacyMembership.Role.STAFF,
        )

        now = timezone.localtime()

        PharmacyOpeningHours.objects.create(
            pharmacy=self.pharmacy,
            day_of_week=now.weekday(),
            opens_at=time(0, 0),
            closes_at=time(23, 59),
        )

        self.medication_request = MedicationRequest.objects.create(
            patient=self.patient,
            status=MedicationRequest.Status.MATCHING,
            input_type=MedicationRequest.InputType.TEXT,
            text="Paracetamol",
            patient_location=Point(
                -4.0080,
                5.3600,
                srid=4326,
            ),
        )

        self.assignment = PharmacyAssignment.objects.create(
            medication_request=self.medication_request,
            pharmacy=self.pharmacy,
        )

    def authenticate(self, user):
        refresh = RefreshToken.for_user(user)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}"
        )

    def create_prescription_assignment(self):
        prescription = SimpleUploadedFile(
            "ordonnance.pdf",
            b"%PDF-1.4 test ordonnance TeriMedi",
            content_type="application/pdf",
        )

        medication_request = MedicationRequest.objects.create(
            patient=self.patient,
            input_type=MedicationRequest.InputType.PRESCRIPTION,
            prescription=prescription,
            quantity=1,
            patient_location=Point(
                -4.0080,
                5.3600,
                srid=4326,
            ),
        )

        assignment = PharmacyAssignment.objects.create(
            medication_request=medication_request,
            pharmacy=self.pharmacy,
        )

        return medication_request, assignment

    def create_photo_assignment(self):
        photo = SimpleUploadedFile(
            "medicament.jpg",
            b"fake-jpeg-content",
            content_type="image/jpeg",
        )

        medication_request = MedicationRequest.objects.create(
            patient=self.patient,
            input_type=MedicationRequest.InputType.PHOTO,
            medication_photo=photo,
            quantity=1,
            patient_location=Point(
                -4.0080,
                5.3600,
                srid=4326,
            ),
        )

        assignment = PharmacyAssignment.objects.create(
            medication_request=medication_request,
            pharmacy=self.pharmacy,
        )

        return medication_request, assignment

    def test_member_can_respond_to_own_pharmacy_assignment(self):
        self.authenticate(self.staff)

        url = reverse(
            "medication_requests:pharmacy-assignment-respond",
            kwargs={
                "assignment_id": self.assignment.id,
            },
        )

        response = self.client.post(
            url,
            {
                "response": "ACCEPTED",
                "note": "Disponible.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assignment.refresh_from_db()

        self.assertEqual(
            self.assignment.status,
            PharmacyAssignment.Status.ACCEPTED,
        )

    def test_other_pharmacy_member_cannot_respond(self):
        self.authenticate(self.other_staff)

        url = reverse(
            "medication_requests:pharmacy-assignment-respond",
            kwargs={
                "assignment_id": self.assignment.id,
            },
        )

        response = self.client.post(
            url,
            {
                "response": "ACCEPTED",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_assigned_pharmacy_can_view_prescription(self):
        _, assignment = self.create_prescription_assignment()

        self.authenticate(self.staff)

        url = reverse(
            "medication_requests:pharmacy-assignment-attachment",
            kwargs={
                "assignment_id": assignment.id,
            },
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response["Content-Type"],
            "application/pdf",
        )

        self.assertEqual(
            response["Cache-Control"],
            "private, no-store, max-age=0",
        )

        self.assertEqual(
            response["X-Content-Type-Options"],
            "nosniff",
        )

        self.assertIn(
            "inline;",
            response["Content-Disposition"],
        )

    def test_assigned_pharmacy_can_view_medication_photo(self):
        _, assignment = self.create_photo_assignment()

        self.authenticate(self.staff)

        url = reverse(
            "medication_requests:pharmacy-assignment-attachment",
            kwargs={
                "assignment_id": assignment.id,
            },
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response["Content-Type"],
            "image/jpeg",
        )

        self.assertEqual(
            response["Cache-Control"],
            "private, no-store, max-age=0",
        )

    def test_other_pharmacy_cannot_view_prescription(self):
        _, assignment = self.create_prescription_assignment()

        self.authenticate(self.other_staff)

        url = reverse(
            "medication_requests:pharmacy-assignment-attachment",
            kwargs={
                "assignment_id": assignment.id,
            },
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_patient_cannot_use_pharmacy_attachment_endpoint(self):
        _, assignment = self.create_prescription_assignment()

        self.authenticate(self.patient)

        url = reverse(
            "medication_requests:pharmacy-assignment-attachment",
            kwargs={
                "assignment_id": assignment.id,
            },
        )

        response = self.client.get(url)

        self.assertIn(
            response.status_code,
            [
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
            ],
        )

    def test_text_request_has_no_attachment(self):
        self.authenticate(self.staff)

        url = reverse(
            "medication_requests:pharmacy-assignment-attachment",
            kwargs={
                "assignment_id": self.assignment.id,
            },
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_pending_serializer_exposes_prescription_attachment_metadata(
        self,
    ):
        _, assignment = self.create_prescription_assignment()

        self.authenticate(self.staff)

        url = reverse(
            "medication_requests:pharmacy-pending",
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        item = next(
            item
            for item in response.data
            if str(item["id"]) == str(assignment.id)
        )

        self.assertTrue(
            item["has_attachment"]
        )

        self.assertEqual(
            item["attachment_type"],
            MedicationRequest.InputType.PRESCRIPTION,
        )

    def test_pending_serializer_exposes_photo_attachment_metadata(
        self,
    ):
        _, assignment = self.create_photo_assignment()

        self.authenticate(self.staff)

        url = reverse(
            "medication_requests:pharmacy-pending",
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        item = next(
            item
            for item in response.data
            if str(item["id"]) == str(assignment.id)
        )

        self.assertTrue(
            item["has_attachment"]
        )

        self.assertEqual(
            item["attachment_type"],
            MedicationRequest.InputType.PHOTO,
        )

    def test_pending_serializer_marks_text_request_without_attachment(
        self,
    ):
        self.authenticate(self.staff)

        url = reverse(
            "medication_requests:pharmacy-pending",
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        item = next(
            item
            for item in response.data
            if str(item["id"]) == str(self.assignment.id)
        )

        self.assertFalse(
            item["has_attachment"]
        )

        self.assertIsNone(
            item["attachment_type"]
        )