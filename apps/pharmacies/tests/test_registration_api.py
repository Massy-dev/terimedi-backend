import tempfile

from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.pharmacies.models import (
    Pharmacy,
    PharmacyMembership,
)


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class PharmacyRegistrationAPITests(APITestCase):
    register_url = "/api/v1/pharmacies/register/"
    registration_url = "/api/v1/pharmacies/registration/"

    def setUp(self):
        self.user = User.objects.create_user(
            phone_number="+2250701020304",
            password="StrongPassword123!",
            first_name="Jean",
            last_name="Kouassi",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.client.force_authenticate(
            user=self.user,
        )

    def make_document(
        self,
        name="justificatif.pdf",
        size=None,
    ):
        if size is None:
            content = b"fake pharmacy verification document"
        else:
            content = b"x" * size

        return SimpleUploadedFile(
            name,
            content,
            content_type="application/pdf",
        )

    def registration_payload(self, **overrides):
        payload = {
            "name": "Pharmacie TeriMedi Test",
            "phone_number": "07 01 02 03 05",
            "address": "Cocody Angré, Abidjan",
            "commune": "Cocody",
            "latitude": 5.3890,
            "longitude": -3.9670,
            "verification_document": self.make_document(),
        }

        payload.update(overrides)

        return payload

    def create_existing_pharmacy(
        self,
        *,
        status_value=Pharmacy.Status.PENDING,
        rejection_reason="",
    ):
        pharmacy = Pharmacy.objects.create(
            owner=self.user,
            name="Pharmacie Existante",
            phone_number="+2250701020305",
            address="Cocody, Abidjan",
            commune="Cocody",
            location=Point(
                -3.9670,
                5.3890,
                srid=4326,
            ),
            status=status_value,
            rejection_reason=rejection_reason,
            is_active=True,
        )

        PharmacyMembership.objects.create(
            pharmacy=pharmacy,
            user=self.user,
            role=PharmacyMembership.Role.OWNER,
            is_active=True,
        )

        return pharmacy

    def test_authenticated_patient_can_register_pharmacy(self):
        response = self.client.post(
            self.register_url,
            data=self.registration_payload(),
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            Pharmacy.objects.count(),
            1,
        )

        pharmacy = Pharmacy.objects.get()

        self.assertEqual(
            pharmacy.owner,
            self.user,
        )
        self.assertEqual(
            pharmacy.name,
            "Pharmacie TeriMedi Test",
        )
        self.assertEqual(
            pharmacy.status,
            Pharmacy.Status.PENDING,
        )
        self.assertTrue(
            pharmacy.is_active,
        )
        self.assertTrue(
            bool(pharmacy.verification_document),
        )

        self.assertAlmostEqual(
            pharmacy.location.y,
            5.3890,
        )
        self.assertAlmostEqual(
            pharmacy.location.x,
            -3.9670,
        )

        membership = PharmacyMembership.objects.get(
            pharmacy=pharmacy,
            user=self.user,
        )

        self.assertEqual(
            membership.role,
            PharmacyMembership.Role.OWNER,
        )
        self.assertTrue(
            membership.is_active,
        )

        self.user.refresh_from_db()

        self.assertEqual(
            self.user.role,
            User.Role.PHARMACY_STAFF,
        )

        self.assertEqual(
            response.data["status"],
            Pharmacy.Status.PENDING,
        )
        self.assertEqual(
            response.data["name"],
            "Pharmacie TeriMedi Test",
        )
        self.assertEqual(
            response.data["rejection_reason"],
            "",
        )

    def test_registration_normalizes_pharmacy_phone_number(self):
        response = self.client.post(
            self.register_url,
            data=self.registration_payload(
                phone_number="07 01 02 03 05",
            ),
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        pharmacy = Pharmacy.objects.get()

        self.assertEqual(
            pharmacy.phone_number,
            "+2250701020305",
        )

    def test_registration_requires_authentication(self):
        self.client.force_authenticate(
            user=None,
        )

        response = self.client.post(
            self.register_url,
            data=self.registration_payload(),
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            Pharmacy.objects.count(),
            0,
        )

        self.user.refresh_from_db()

        self.assertEqual(
            self.user.role,
            User.Role.PATIENT,
        )

    def test_registration_requires_verification_document(self):
        payload = self.registration_payload()
        payload.pop("verification_document")

        response = self.client.post(
            self.register_url,
            data=payload,
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            Pharmacy.objects.count(),
            0,
        )

        self.assertEqual(
            PharmacyMembership.objects.count(),
            0,
        )

        self.user.refresh_from_db()

        self.assertEqual(
            self.user.role,
            User.Role.PATIENT,
        )

    def test_registration_rejects_document_larger_than_10_mb(self):
        document = self.make_document(
            size=(10 * 1024 * 1024) + 1,
        )

        response = self.client.post(
            self.register_url,
            data=self.registration_payload(
                verification_document=document,
            ),
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "verification_document",
            response.data,
        )

        self.assertEqual(
            Pharmacy.objects.count(),
            0,
        )

    def test_registration_rejects_invalid_phone_number(self):
        response = self.client.post(
            self.register_url,
            data=self.registration_payload(
                phone_number="123",
            ),
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "phone_number",
            response.data,
        )

        self.assertEqual(
            Pharmacy.objects.count(),
            0,
        )

    def test_registration_rejects_invalid_latitude(self):
        response = self.client.post(
            self.register_url,
            data=self.registration_payload(
                latitude=91,
            ),
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "latitude",
            response.data,
        )

        self.assertEqual(
            Pharmacy.objects.count(),
            0,
        )

    def test_registration_rejects_invalid_longitude(self):
        response = self.client.post(
            self.register_url,
            data=self.registration_payload(
                longitude=-181,
            ),
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "longitude",
            response.data,
        )

        self.assertEqual(
            Pharmacy.objects.count(),
            0,
        )

    def test_user_cannot_create_second_pharmacy_registration(self):
        self.create_existing_pharmacy()

        response = self.client.post(
            self.register_url,
            data=self.registration_payload(),
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            Pharmacy.objects.count(),
            1,
        )

        self.assertIn(
            "detail",
            response.data,
        )

    def test_user_with_active_membership_cannot_register_another_pharmacy(
        self,
    ):
        other_owner = User.objects.create_user(
            phone_number="+2250701020306",
            password="StrongPassword123!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        pharmacy = Pharmacy.objects.create(
            owner=other_owner,
            name="Pharmacie Principale",
            phone_number="+2250701020306",
            address="Abidjan",
            commune="Cocody",
            location=Point(
                -3.9670,
                5.3890,
                srid=4326,
            ),
            status=Pharmacy.Status.APPROVED,
            is_active=True,
        )

        PharmacyMembership.objects.create(
            pharmacy=pharmacy,
            user=self.user,
            role=PharmacyMembership.Role.STAFF,
            is_active=True,
        )

        response = self.client.post(
            self.register_url,
            data=self.registration_payload(),
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            Pharmacy.objects.count(),
            1,
        )

    def test_registration_status_returns_pending_registration(self):
        pharmacy = self.create_existing_pharmacy(
            status_value=Pharmacy.Status.PENDING,
        )

        response = self.client.get(
            self.registration_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            str(pharmacy.id),
        )
        self.assertEqual(
            response.data["status"],
            Pharmacy.Status.PENDING,
        )
        self.assertEqual(
            response.data["rejection_reason"],
            "",
        )

    def test_registration_status_returns_approved_registration(self):
        pharmacy = self.create_existing_pharmacy(
            status_value=Pharmacy.Status.APPROVED,
        )

        response = self.client.get(
            self.registration_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            str(pharmacy.id),
        )
        self.assertEqual(
            response.data["status"],
            Pharmacy.Status.APPROVED,
        )

    def test_registration_status_returns_rejected_registration_and_reason(
        self,
    ):
        reason = (
            "Le justificatif fourni n'est pas suffisamment lisible."
        )

        pharmacy = self.create_existing_pharmacy(
            status_value=Pharmacy.Status.REJECTED,
            rejection_reason=reason,
        )

        response = self.client.get(
            self.registration_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            str(pharmacy.id),
        )
        self.assertEqual(
            response.data["status"],
            Pharmacy.Status.REJECTED,
        )
        self.assertEqual(
            response.data["rejection_reason"],
            reason,
        )

    def test_registration_status_returns_404_when_none_exists(self):
        response = self.client.get(
            self.registration_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.assertIn(
            "detail",
            response.data,
        )

    def test_registration_status_requires_authentication(self):
        self.client.force_authenticate(
            user=None,
        )

        response = self.client.get(
            self.registration_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )