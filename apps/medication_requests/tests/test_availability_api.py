
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
    PharmacyMembership,
)
from apps.medication_requests.models import (
    MedicationRequest,
    MedicationRequestItem,
    PharmacyAssignment,
)


class StructuredAvailabilityAPITests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            phone_number="07 11 22 33 44",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.staff = User.objects.create_user(
            phone_number="07 22 33 44 55",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.other_staff = User.objects.create_user(
            phone_number="07 33 44 55 66",
            password="TerimediTest2026!",
            role=User.Role.PHARMACY_STAFF,
            is_phone_verified=True,
        )

        self.pharmacy = Pharmacy.objects.create(
            name="Pharmacie TeriMedi Test",
            address="Cocody",
            commune="Cocody",
            location=Point(-4.0083, 5.3599, srid=4326),
            status=Pharmacy.Status.APPROVED,
            is_active=True,
        )

        self.other_pharmacy = Pharmacy.objects.create(
            name="Autre Pharmacie Test",
            address="Marcory",
            commune="Marcory",
            location=Point(-4.0200, 5.3000, srid=4326),
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

        self.medication_request = MedicationRequest.objects.create(
            patient=self.patient,
            status=MedicationRequest.Status.MATCHING,
            input_type=MedicationRequest.InputType.TEXT,
            text="Demande de deux médicaments",
            patient_location=Point(-4.0080, 5.3600, srid=4326),
        )

        self.item_one = MedicationRequestItem.objects.create(
            medication_request=self.medication_request,
            name="Paracétamol",
            dosage="500 mg",
            quantity=2,
            unit=MedicationRequestItem.Unit.BOX,
            position=0,
        )

        self.item_two = MedicationRequestItem.objects.create(
            medication_request=self.medication_request,
            name="Amoxicilline",
            dosage="500 mg",
            quantity=3,
            unit=MedicationRequestItem.Unit.BOX,
            position=1,
        )

        self.assignment = PharmacyAssignment.objects.create(
            medication_request=self.medication_request,
            pharmacy=self.pharmacy,
        )

        self.respond_url = reverse(
            "medication_requests:pharmacy-assignment-respond",
            kwargs={"assignment_id": self.assignment.id},
        )

        self.detail_url = reverse(
            "medication_requests:detail",
            kwargs={"pk": self.medication_request.id},
        )

    def authenticate(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}"
        )

    def entry(self, item, quantity):
        return {
            "item_id": str(item.id),
            "quantity": quantity,
        }

    def respond(self, response_type, quantities=None, **extra):
        payload = {
            "response": response_type,
            **extra,
        }

        if quantities is not None:
            payload["available_item_quantities"] = quantities

        self.authenticate(self.staff)

        return self.client.post(
            self.respond_url,
            payload,
            format="json",
        )

    def assert_pending_unchanged(self):
        self.assignment.refresh_from_db()
        self.medication_request.refresh_from_db()

        self.assertEqual(
            self.assignment.status,
            PharmacyAssignment.Status.PENDING,
        )

        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.MATCHING,
        )

        self.assertEqual(
            self.assignment.available_item_quantities,
            [],
        )

    def test_full_availability_is_saved(self):
        response = self.respond(
            "ACCEPTED",
            [
                self.entry(self.item_one, 2),
                self.entry(self.item_two, 3),
            ],
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assignment.refresh_from_db()
        self.medication_request.refresh_from_db()

        self.assertEqual(
            self.assignment.status,
            PharmacyAssignment.Status.ACCEPTED,
        )

        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.PHARMACY_FOUND,
        )

        self.assertEqual(
            self.assignment.available_item_quantities,
            [
                self.entry(self.item_one, 2),
                self.entry(self.item_two, 3),
            ],
        )

        self.assertEqual(
            response.data["available_item_quantities"],
            self.assignment.available_item_quantities,
        )

    def test_partial_availability_is_saved(self):
        response = self.respond(
            "PARTIAL",
            [
                self.entry(self.item_one, 2),
                self.entry(self.item_two, 1),
            ],
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assignment.refresh_from_db()
        self.medication_request.refresh_from_db()

        self.assertEqual(
            self.assignment.status,
            PharmacyAssignment.Status.PARTIAL,
        )

        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.PARTIAL,
        )

        self.assertEqual(
            self.assignment.available_item_quantities,
            [
                self.entry(self.item_one, 2),
                self.entry(self.item_two, 1),
            ],
        )

    def test_missing_item_is_normalized_to_zero(self):
        response = self.respond(
            "PARTIAL",
            [self.entry(self.item_one, 2)],
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assignment.refresh_from_db()

        self.assertEqual(
            self.assignment.available_item_quantities,
            [
                self.entry(self.item_one, 2),
                self.entry(self.item_two, 0),
            ],
        )

    def test_patient_can_read_partial_availability(self):
        response = self.respond(
            "PARTIAL",
            [self.entry(self.item_one, 1)],
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.authenticate(self.patient)

        detail_response = self.client.get(self.detail_url)

        self.assertEqual(
            detail_response.status_code,
            status.HTTP_200_OK,
        )

        current_assignment = detail_response.data["current_assignment"]

        self.assertIsNotNone(current_assignment)

        self.assertEqual(
            current_assignment["status"],
            PharmacyAssignment.Status.PARTIAL,
        )

        self.assertEqual(
            current_assignment["available_item_quantities"],
            [
                self.entry(self.item_one, 1),
                self.entry(self.item_two, 0),
            ],
        )

    def test_excess_quantity_returns_400(self):
        response = self.respond(
            "PARTIAL",
            [self.entry(self.item_one, 10)],
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assert_pending_unchanged()

    def test_unknown_item_returns_400(self):
        import uuid

        response = self.respond(
            "PARTIAL",
            [{
                "item_id": str(uuid.uuid4()),
                "quantity": 1,
            }],
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assert_pending_unchanged()

    def test_duplicate_item_returns_400(self):
        response = self.respond(
            "PARTIAL",
            [
                self.entry(self.item_one, 1),
                self.entry(self.item_one, 1),
            ],
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assert_pending_unchanged()

    def test_negative_quantity_returns_400(self):
        response = self.respond(
            "PARTIAL",
            [self.entry(self.item_one, -1)],
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assert_pending_unchanged()

    def test_full_response_with_missing_quantity_returns_400(self):
        response = self.respond(
            "ACCEPTED",
            [self.entry(self.item_one, 2)],
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assert_pending_unchanged()

    def test_partial_response_with_full_quantities_returns_400(self):
        response = self.respond(
            "PARTIAL",
            [
                self.entry(self.item_one, 2),
                self.entry(self.item_two, 3),
            ],
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assert_pending_unchanged()

    def test_partial_response_with_zero_quantities_returns_400(self):
        response = self.respond(
            "PARTIAL",
            [
                self.entry(self.item_one, 0),
                self.entry(self.item_two, 0),
            ],
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assert_pending_unchanged()

    def test_rejection_with_available_quantity_returns_400(self):
        response = self.respond(
            "REJECTED",
            [self.entry(self.item_one, 1)],
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assert_pending_unchanged()

    def test_expired_assignment_cannot_respond(self):
        self.assignment.expires_at = (
            timezone.now() - timedelta(minutes=1)
        )
        self.assignment.save(update_fields=["expires_at"])

        response = self.respond(
            "ACCEPTED",
            [
                self.entry(self.item_one, 2),
                self.entry(self.item_two, 3),
            ],
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assert_pending_unchanged()

    def test_other_pharmacy_cannot_respond(self):
        self.authenticate(self.other_staff)

        response = self.client.post(
            self.respond_url,
            {
                "response": "ACCEPTED",
                "available_item_quantities": [
                    self.entry(self.item_one, 2),
                    self.entry(self.item_two, 3),
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.assert_pending_unchanged()

    def test_legacy_response_remains_supported(self):
        response = self.respond(
            "ACCEPTED",
            available_items="Tous les médicaments disponibles.",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assignment.refresh_from_db()

        self.assertEqual(
            self.assignment.available_items,
            "Tous les médicaments disponibles.",
        )

        self.assertEqual(
            self.assignment.available_item_quantities,
            [],
        )

    def test_second_response_is_rejected(self):
        first_response = self.respond(
            "ACCEPTED",
            [
                self.entry(self.item_one, 2),
                self.entry(self.item_two, 3),
            ],
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        second_response = self.respond(
            "PARTIAL",
            [self.entry(self.item_one, 1)],
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assignment.refresh_from_db()

        self.assertEqual(
            self.assignment.status,
            PharmacyAssignment.Status.ACCEPTED,
        )

        self.assertEqual(
            self.assignment.available_item_quantities,
            [
                self.entry(self.item_one, 2),
                self.entry(self.item_two, 3),
            ],
        )
