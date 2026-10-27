from io import BytesIO
from PIL import Image
import json
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.medication_requests.models import (
    MedicationRequest,
    MedicationRequestItem,
    PharmacyAssignment,
)
from apps.pharmacies.models import Pharmacy, PharmacyMembership


class MedicationRequestMultiItemsAPITests(APITestCase):
    def setUp(self):
        self.media_directory = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(shutil.rmtree, self.media_directory, ignore_errors=True)

        self.patient = User.objects.create_user(
            phone_number="07 10 11 12 13",
            password="TestPassword2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )
        self.other_patient = User.objects.create_user(
            phone_number="07 20 21 22 23",
            password="TestPassword2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )
        self.staff = User.objects.create_user(
            phone_number="07 30 31 32 33",
            password="TestPassword2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )
        self.other_staff = User.objects.create_user(
            phone_number="07 40 41 42 43",
            password="TestPassword2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )
        self.url = reverse("medication_requests:list-create")

    def photo(self, name="medicament.png"):
        buffer = BytesIO()
        image = Image.new("RGB", (10, 10), color="white")
        image.save(buffer, format="PNG")
        return SimpleUploadedFile(
            name, buffer.getvalue(), content_type="image/png",
        )

    def payload(self, items=None):
        if items is None:
            items = [
                {
                    "name": "Doliprane",
                    "dosage": "500 mg",
                    "quantity": 2,
                    "unit": "BOX",
                },
                {
                    "name": "",
                    "dosage": "",
                    "quantity": 1,
                    "unit": "UNIT",
                },
            ]
        return {
            "input_type": "TEXT",
            "latitude": "5.3600",
            "longitude": "-4.0080",
            "quote_requested": "true",
            "fulfillment_type": "PICKUP",
            "items": json.dumps(items),
        }

    def create_request(self):
        self.client.force_authenticate(user=self.patient)
        payload = self.payload()
        payload["item_photo_1"] = self.photo()
        response = self.client.post(self.url, payload, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response

    def create_pharmacy(self, name, staff):
        pharmacy = Pharmacy.objects.create(
            name=name,
            address="Cocody",
            commune="Cocody",
            location=Point(-4.0083, 5.3599, srid=4326),
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

    def test_create_multiple_items_with_photo(self):
        response = self.create_request()
        medication_request = MedicationRequest.objects.get(id=response.data["id"])
        items = list(medication_request.items.all())
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].name, "Doliprane")
        self.assertEqual(items[0].quantity, 2)
        self.assertEqual(items[0].position, 0)
        self.assertEqual(items[1].name, "")
        self.assertTrue(items[1].photo)
        self.assertEqual(items[1].position, 1)
        self.assertTrue(medication_request.quote_requested)
        self.assertEqual(len(response.data["items"]), 2)
        self.assertTrue(response.data["items"][1]["has_photo"])

    def test_reject_item_without_name_or_photo(self):
        self.client.force_authenticate(user=self.patient)
        response = self.client.post(
            self.url,
            self.payload([{"name": "", "quantity": 1, "unit": "BOX"}]),
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MedicationRequest.objects.count(), 0)
        self.assertEqual(MedicationRequestItem.objects.count(), 0)

    def test_reject_invalid_image(self):
        self.client.force_authenticate(user=self.patient)
        payload = self.payload([{"name": "", "quantity": 1, "unit": "BOX"}])
        payload["item_photo_0"] = SimpleUploadedFile(
            "invalid.png", b"not-a-real-image", content_type="image/png",
        )
        response = self.client.post(self.url, payload, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MedicationRequest.objects.count(), 0)

    def test_patient_can_read_own_photo(self):
        response = self.create_request()
        item_id = response.data["items"][1]["id"]
        url = reverse(
            "medication_requests:item-photo",
            kwargs={"request_id": response.data["id"], "item_id": item_id},
        )
        photo_response = self.client.get(url)
        self.assertEqual(photo_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            photo_response["Cache-Control"], "private, no-store, max-age=0",
        )
        self.client.force_authenticate(user=self.other_patient)
        forbidden_response = self.client.get(url)
        self.assertEqual(forbidden_response.status_code, status.HTTP_404_NOT_FOUND)

    
    def test_only_current_pharmacy_can_read_photo(self):
        response = self.create_request()

        medication_request = MedicationRequest.objects.get(
            id=response.data["id"]
        )
        item_id = response.data["items"][1]["id"]

        pharmacy = self.create_pharmacy(
            "Pharmacie A",
            self.staff,
        )
        self.create_pharmacy(
            "Pharmacie B",
            self.other_staff,
        )

        # Le matching peut avoir déclaré la demande UNAVAILABLE
        # parce qu'aucune pharmacie éligible n'existait.
        # Ici, on teste uniquement les autorisations d'accès.
        medication_request.status = MedicationRequest.Status.MATCHING
        medication_request.save(update_fields=["status"])

        assignment = PharmacyAssignment.objects.create(
            medication_request=medication_request,
            pharmacy=pharmacy,
            status=PharmacyAssignment.Status.PENDING,
        )

        url = reverse(
            "medication_requests:item-photo",
            kwargs={
                "request_id": medication_request.id,
                "item_id": item_id,
            },
        )

        # La pharmacie attribuée peut accéder à la photo.
        self.client.force_authenticate(user=self.staff)

        allowed = self.client.get(url)
        self.assertEqual(
            allowed.status_code,
            status.HTTP_200_OK,
        )
        #allowed.close()

        # Une autre pharmacie ne peut pas y accéder.
        self.client.force_authenticate(user=self.other_staff)

        denied = self.client.get(url)
        self.assertEqual(
            denied.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        # L'annulation de l'attribution révoque l'accès.
        assignment.status = PharmacyAssignment.Status.CANCELLED
        assignment.save(update_fields=["status"])

        self.client.force_authenticate(user=self.staff)

        revoked = self.client.get(url)
        self.assertEqual(
            revoked.status_code,
            status.HTTP_404_NOT_FOUND,
        )


    def test_legacy_text_request_still_works(self):
        self.client.force_authenticate(user=self.patient)
        response = self.client.post(
            self.url,
            {
                "input_type": "TEXT",
                "text": "Paracetamol",
                "quantity": 1,
                "latitude": "5.3600",
                "longitude": "-4.0080",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["items"], [])

    def test_matching_failure_rolls_back_database(self):
        self.client.force_authenticate(user=self.patient)
        payload = self.payload([{
            "name": "Doliprane", "quantity": 1, "unit": "BOX",
        }])
        with patch.object(
            __import__(
                "apps.medication_requests.views",
                fromlist=["MatchingService"],
            ).MatchingService,
            "assign_next_pharmacy",
            side_effect=RuntimeError("Simulated matching failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, payload, format="multipart")
        self.assertEqual(MedicationRequest.objects.count(), 0)
        self.assertEqual(MedicationRequestItem.objects.count(), 0)

    def test_api_does_not_expose_direct_media_urls(self):
        self.client.force_authenticate(user=self.patient)
        response = self.client.post(
            self.url,
            {
                "input_type": "PHOTO",
                "medication_photo": self.photo(),
                "latitude": "5.3600",
                "longitude": "-4.0080",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIsNone(response.data["prescription"])
        self.assertIsNone(response.data["medication_photo"])
        self.assertFalse(response.data["has_prescription"])
        self.assertTrue(response.data["has_medication_photo"])

        detail_url = reverse(
            "medication_requests:detail",
            kwargs={"pk": response.data["id"]},
        )
        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertIsNone(detail_response.data["prescription"])
        self.assertIsNone(detail_response.data["medication_photo"])
        self.assertTrue(detail_response.data["has_medication_photo"])

        list_response = self.client.get(self.url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        matching = next(
            entry for entry in list_response.data
            if str(entry["id"]) == str(response.data["id"])
        )
        self.assertIsNone(matching["prescription"])
        self.assertIsNone(matching["medication_photo"])
        self.assertTrue(matching["has_medication_photo"])
