
import shutil
import tempfile
from datetime import timedelta

from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITransactionTestCase

from apps.accounts.models import User
from apps.medication_requests.models import (
    MedicationRequest,
    MedicationRequestItem,
    PharmacyAssignment,
)
from apps.pharmacies.models import (
    Pharmacy,
    PharmacyMembership,
)


class PrivateDocumentsAPITests(APITransactionTestCase):
    def setUp(self):
        self.media_directory = tempfile.mkdtemp()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_directory,
        )
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(
            shutil.rmtree,
            self.media_directory,
            ignore_errors=True,
        )

        self.patient = self.create_user(
            "0701000001",
            User.Role.PATIENT,
        )
        self.other_patient = self.create_user(
            "0701000002",
            User.Role.PATIENT,
        )
        self.staff_a = self.create_user(
            "0701000003",
            User.Role.PHARMACY_STAFF,
        )
        self.staff_b = self.create_user(
            "0701000004",
            User.Role.PHARMACY_STAFF,
        )

        self.pharmacy_a = self.create_pharmacy(
            "Pharmacie A",
            self.staff_a,
        )
        self.pharmacy_b = self.create_pharmacy(
            "Pharmacie B",
            self.staff_b,
        )

        self.medication_request = MedicationRequest.objects.create(
            patient=self.patient,
            input_type=MedicationRequest.InputType.PHOTO,
            patient_location=Point(
                -4.0080,
                5.3600,
                srid=4326,
            ),
            status=MedicationRequest.Status.MATCHING,
        )

        self.medication_request.medication_photo.save(
            "medicament.jpg",
            ContentFile(b"private-legacy-photo"),
            save=True,
        )

        self.item = MedicationRequestItem.objects.create(
            medication_request=self.medication_request,
            name="Paracetamol",
            quantity=1,
        )
        self.item.photo.save(
            "article.jpg",
            ContentFile(b"private-item-photo"),
            save=True,
        )

        self.assignment_a = PharmacyAssignment.objects.create(
            medication_request=self.medication_request,
            pharmacy=self.pharmacy_a,
            status=PharmacyAssignment.Status.PENDING,
            assigned_at=timezone.now() - timedelta(minutes=5),
        )

        self.patient_url = reverse(
            "medication_requests:patient-attachment",
            kwargs={
                "request_id": self.medication_request.id,
            },
        )
        self.item_url = reverse(
            "medication_requests:item-photo",
            kwargs={
                "request_id": self.medication_request.id,
                "item_id": self.item.id,
            },
        )

    def create_user(self, phone, role):
        return User.objects.create_user(
            phone_number=phone,
            password="TestPassword2026!",
            role=role,
            is_phone_verified=True,
        )

    def create_pharmacy(self, name, staff):
        pharmacy = Pharmacy.objects.create(
            name=name,
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
            pharmacy=pharmacy,
            user=staff,
            role=PharmacyMembership.Role.STAFF,
            is_active=True,
        )

        return pharmacy

    def pharmacy_attachment_url(self, assignment):
        return reverse(
            "medication_requests:pharmacy-assignment-attachment",
            kwargs={"assignment_id": assignment.id},
        )

    def create_newer_assignment(self):
        return PharmacyAssignment.objects.create(
            medication_request=self.medication_request,
            pharmacy=self.pharmacy_b,
            status=PharmacyAssignment.Status.PENDING,
            assigned_at=timezone.now(),
        )

    def test_patient_can_access_own_legacy_attachment(self):
        self.client.force_authenticate(user=self.patient)

        response = self.client.get(self.patient_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertIn(
            "no-store",
            response["Cache-Control"],
        )
        self.assertEqual(
            response["X-Content-Type-Options"],
            "nosniff",
        )
        self.assertEqual(
            b"".join(response.streaming_content),
            b"private-legacy-photo",
        )
        response.close()

    def test_other_patient_cannot_access_attachment(self):
        self.client.force_authenticate(user=self.other_patient)

        response = self.client.get(self.patient_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_anonymous_user_cannot_access_attachment(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.patient_url)

        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )

    def test_current_pharmacy_can_access_both_photos(self):
        self.client.force_authenticate(user=self.staff_a)

        legacy_response = self.client.get(
            self.pharmacy_attachment_url(self.assignment_a)
        )
        item_response = self.client.get(self.item_url)

        self.assertEqual(
            legacy_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            item_response.status_code,
            status.HTTP_200_OK,
        )

        legacy_response.close()
        item_response.close()

    def test_old_pharmacy_loses_access_after_reassignment(self):
        self.create_newer_assignment()

        self.client.force_authenticate(user=self.staff_a)

        legacy_response = self.client.get(
            self.pharmacy_attachment_url(self.assignment_a)
        )
        item_response = self.client.get(self.item_url)

        self.assertEqual(
            legacy_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            item_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.client.force_authenticate(user=self.staff_b)

        current_legacy = self.client.get(
            self.pharmacy_attachment_url(
                PharmacyAssignment.objects.get(
                    medication_request=self.medication_request,
                    pharmacy=self.pharmacy_b,
                )
            )
        )
        current_item = self.client.get(self.item_url)

        self.assertEqual(
            current_legacy.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            current_item.status_code,
            status.HTTP_200_OK,
        )

        current_legacy.close()
        current_item.close()

    def test_cancelled_request_blocks_pharmacy_access(self):
        self.medication_request.status = (
            MedicationRequest.Status.CANCELLED
        )
        self.medication_request.save(
            update_fields=["status"]
        )

        self.client.force_authenticate(user=self.staff_a)

        legacy_response = self.client.get(
            self.pharmacy_attachment_url(self.assignment_a)
        )
        item_response = self.client.get(self.item_url)

        self.assertEqual(
            legacy_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            item_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        # Le patient conserve l'accès à son propre document.
        self.client.force_authenticate(user=self.patient)

        patient_response = self.client.get(self.patient_url)

        self.assertEqual(
            patient_response.status_code,
            status.HTTP_200_OK,
        )
        patient_response.close()

    def test_revoked_membership_blocks_access(self):
        PharmacyMembership.objects.filter(
            pharmacy=self.pharmacy_a,
            user=self.staff_a,
        ).update(is_active=False)

        self.client.force_authenticate(user=self.staff_a)

        legacy_response = self.client.get(
            self.pharmacy_attachment_url(self.assignment_a)
        )
        item_response = self.client.get(self.item_url)

        self.assertEqual(
            legacy_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            item_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_quote_pending_current_pharmacy_can_access_documents(self):
        """
        La pharmacie ayant proposé le devis conserve
        l'accès aux documents pendant QUOTE_PENDING.
        """
        self.medication_request.quote_requested = True
        self.medication_request.status = (
            MedicationRequest.Status.QUOTE_PENDING
        )
        self.medication_request.save(
            update_fields=["quote_requested", "status"]
        )

        self.assignment_a.status = (
            PharmacyAssignment.Status.ACCEPTED
        )
        self.assignment_a.save(update_fields=["status"])

        self.client.force_authenticate(user=self.staff_a)

        legacy_response = self.client.get(
            self.pharmacy_attachment_url(self.assignment_a)
        )
        item_response = self.client.get(self.item_url)

        self.assertEqual(legacy_response.status_code, 200)
        self.assertEqual(item_response.status_code, 200)

        self.assertIn(
            "no-store",
            legacy_response["Cache-Control"],
        )
        self.assertIn(
            "no-store",
            item_response["Cache-Control"],
        )

        legacy_response.close()
        item_response.close()

    def test_quote_pending_other_pharmacy_cannot_access_documents(self):
        """
        Une autre pharmacie ne doit pas accéder
        aux documents pendant QUOTE_PENDING.
        """
        self.medication_request.quote_requested = True
        self.medication_request.status = (
            MedicationRequest.Status.QUOTE_PENDING
        )
        self.medication_request.save(
            update_fields=["quote_requested", "status"]
        )

        self.assignment_a.status = (
            PharmacyAssignment.Status.ACCEPTED
        )
        self.assignment_a.save(update_fields=["status"])

        self.client.force_authenticate(user=self.staff_b)

        legacy_response = self.client.get(
            self.pharmacy_attachment_url(self.assignment_a)
        )
        item_response = self.client.get(self.item_url)

        self.assertEqual(legacy_response.status_code, 404)
        self.assertEqual(item_response.status_code, 404)

    def test_rejected_quote_removes_old_pharmacy_document_access(self):
        """
        Après refus du devis, l'ancienne pharmacie
        ne doit plus consulter les documents.
        """
        self.medication_request.quote_requested = True
        self.medication_request.status = (
            MedicationRequest.Status.MATCHING
        )
        self.medication_request.save(
            update_fields=["quote_requested", "status"]
        )

        self.assignment_a.status = (
            PharmacyAssignment.Status.REJECTED
        )
        self.assignment_a.save(update_fields=["status"])

        self.client.force_authenticate(user=self.staff_a)

        legacy_response = self.client.get(
            self.pharmacy_attachment_url(self.assignment_a)
        )
        item_response = self.client.get(self.item_url)

        self.assertEqual(legacy_response.status_code, 404)
        self.assertEqual(item_response.status_code, 404)

        # Le patient conserve l'accès à son document.
        self.client.force_authenticate(user=self.patient)

        patient_response = self.client.get(self.patient_url)

        self.assertEqual(patient_response.status_code, 200)
        patient_response.close()

    def test_reassigned_pharmacy_can_access_quote_request_documents(self):
        """
        Après refus et réattribution, la pharmacie B
        doit pouvoir consulter les documents.
        """
        self.medication_request.quote_requested = True
        self.medication_request.status = (
            MedicationRequest.Status.MATCHING
        )
        self.medication_request.save(
            update_fields=["quote_requested", "status"]
        )

        self.assignment_a.status = (
            PharmacyAssignment.Status.REJECTED
        )
        self.assignment_a.save(update_fields=["status"])

        assignment_b = self.create_newer_assignment()

        self.client.force_authenticate(user=self.staff_a)

        old_response = self.client.get(
            self.pharmacy_attachment_url(self.assignment_a)
        )
        self.assertEqual(old_response.status_code, 404)

        self.client.force_authenticate(user=self.staff_b)

        legacy_response = self.client.get(
            self.pharmacy_attachment_url(assignment_b)
        )
        item_response = self.client.get(self.item_url)

        self.assertEqual(legacy_response.status_code, 200)
        self.assertEqual(item_response.status_code, 200)

        self.assertEqual(
            b"".join(legacy_response.streaming_content),
            b"private-legacy-photo",
        )
        self.assertEqual(
            b"".join(item_response.streaming_content),
            b"private-item-photo",
        )

        legacy_response.close()
        item_response.close()

