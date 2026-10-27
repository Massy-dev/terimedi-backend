
from datetime import timedelta
from uuid import uuid4

from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.pharmacies.models import Pharmacy, PharmacyMembership
from apps.medication_requests.models import (
    MedicationRequest,
    MedicationRequestItem,
    PharmacyAssignment,
    PharmacyQuote,
    PharmacyQuoteItem,
)
from apps.orders.models import Order
from apps.orders.services.orders import OrderService
from apps.medication_requests.services.matching import MatchingService


class PharmacyQuoteAPITests(APITestCase):
    def setUp(self):
        self.patient = self.create_user("0711223344")
        self.other_patient = self.create_user("0722334455")
        self.staff = self.create_user(
            "0733445566",
            role=User.Role.PHARMACY_STAFF,
        )
        self.other_staff = self.create_user(
            "0744556677",
            role=User.Role.PHARMACY_STAFF,
        )

        self.pharmacy = Pharmacy.objects.create(
            name="Pharmacie Cocody Test",
            address="Cocody",
            commune="Cocody",
            location=Point(-4.0083, 5.3599, srid=4326),
            status=Pharmacy.Status.APPROVED,
            is_active=True,
        )
        self.other_pharmacy = Pharmacy.objects.create(
            name="Pharmacie Marcory Test",
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
            is_active=True,
        )
        PharmacyMembership.objects.create(
            pharmacy=self.other_pharmacy,
            user=self.other_staff,
            role=PharmacyMembership.Role.STAFF,
            is_active=True,
        )

        self.medication_request = MedicationRequest.objects.create(
            patient=self.patient,
            input_type=MedicationRequest.InputType.TEXT,
            text="Demande de médicaments",
            quote_requested=True,
            status=MedicationRequest.Status.MATCHING,
            patient_location=Point(
                -4.0080, 5.3600, srid=4326
            ),
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
            expires_at=timezone.now() + timedelta(minutes=30),
        )

        self.create_url = reverse(
            "medication_requests:pharmacy-assignment-quote",
            kwargs={"assignment_id": self.assignment.id},
        )
        self.detail_url = reverse(
            "medication_requests:patient-quote",
            kwargs={"request_id": self.medication_request.id},
        )
        self.decision_url = reverse(
            "medication_requests:patient-quote-decision",
            kwargs={"request_id": self.medication_request.id},
        )
        self.respond_url = reverse(
            "medication_requests:pharmacy-assignment-respond",
            kwargs={"assignment_id": self.assignment.id},
        )
        self.request_detail_url = reverse(
            "medication_requests:detail",
            kwargs={"pk": self.medication_request.id},
        )

    @staticmethod
    def create_user(phone, role=User.Role.PATIENT):
        return User.objects.create_user(
            phone_number=phone,
            password="TerimediTest2026!",
            role=role,
            is_phone_verified=True,
        )

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def full_payload(self):
        return {
            "response": "ACCEPTED",
            "items": [
                {
                    "item_id": str(self.item_one.id),
                    "quantity": 2,
                    "unit_price": 2000,
                },
                {
                    "item_id": str(self.item_two.id),
                    "quantity": 3,
                    "unit_price": 1500,
                },
            ],
            "note": "Tous les médicaments disponibles.",
        }

    def partial_payload(self):
        return {
            "response": "PARTIAL",
            "items": [
                {
                    "item_id": str(self.item_one.id),
                    "quantity": 2,
                    "unit_price": 2000,
                },
                {
                    "item_id": str(self.item_two.id),
                    "quantity": 1,
                    "unit_price": 1500,
                },
            ],
        }

    def submit_quote(self, payload=None):
        self.authenticate(self.staff)
        return self.client.post(
            self.create_url,
            payload if payload is not None else self.full_payload(),
            format="json",
        )

    def decide(self, decision, patient=None):
        self.authenticate(patient or self.patient)
        return self.client.post(
            self.decision_url,
            {"decision": decision},
            format="json",
        )

    def assert_request_pending(self):
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
        self.assertFalse(
            PharmacyQuote.objects.filter(
                assignment=self.assignment
            ).exists()
        )

    def test_pharmacy_creates_full_quote(self):
        response = self.submit_quote()

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )
        self.assertEqual(response.data["total_amount"], 8500)
        self.assertEqual(response.data["currency"], "XOF")
        self.assertEqual(response.data["status"], "PROPOSED")
        self.assertEqual(len(response.data["items"]), 2)

        quote = PharmacyQuote.objects.get(
            assignment=self.assignment
        )

        self.assertEqual(quote.total_amount, 8500)
        self.assertEqual(
            list(
                quote.items.order_by("position").values_list(
                    "subtotal", flat=True
                )
            ),
            [4000, 4500],
        )

        self.assignment.refresh_from_db()
        self.medication_request.refresh_from_db()

        self.assertEqual(
            self.assignment.status,
            PharmacyAssignment.Status.ACCEPTED,
        )
        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.QUOTE_PENDING,
        )

    def test_pharmacy_creates_partial_quote(self):
        response = self.submit_quote(self.partial_payload())

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )
        self.assertEqual(response.data["total_amount"], 5500)

        self.assignment.refresh_from_db()

        self.assertEqual(
            self.assignment.status,
            PharmacyAssignment.Status.PARTIAL,
        )
        self.assertEqual(
            self.assignment.available_item_quantities,
            [
                {
                    "item_id": str(self.item_one.id),
                    "quantity": 2,
                },
                {
                    "item_id": str(self.item_two.id),
                    "quantity": 1,
                },
            ],
        )

    def test_patient_can_read_own_quote(self):
        created = self.submit_quote()
        self.assertEqual(created.status_code, 201)

        self.authenticate(self.patient)
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_amount"], 8500)
        self.assertEqual(response.data["currency"], "XOF")
        self.assertEqual(
            response.data["pharmacy_name"],
            self.pharmacy.name,
        )
        self.assertEqual(len(response.data["items"]), 2)

    def test_patient_accepts_quote_and_can_confirm_order(self):
        created = self.submit_quote()
        self.assertEqual(created.status_code, 201)

        response = self.decide("ACCEPT")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "ACCEPTED")

        self.medication_request.refresh_from_db()
        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.PHARMACY_FOUND,
        )

        order = OrderService.confirm_request(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
        )

        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertEqual(order.pharmacy, self.pharmacy)

    def test_patient_rejects_quote(self):
        created = self.submit_quote()
        self.assertEqual(created.status_code, 201)

        response = self.decide("REJECT")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "REJECTED")

        self.assignment.refresh_from_db()
        self.medication_request.refresh_from_db()

        self.assertEqual(
            self.assignment.status,
            PharmacyAssignment.Status.REJECTED,
        )

        # Le matching peut trouver une autre pharmacie,
        # ou conclure qu'aucune n'est disponible.
        self.assertIn(
            self.medication_request.status,
            [
                MedicationRequest.Status.MATCHING,
                MedicationRequest.Status.UNAVAILABLE,
            ],
        )

        self.assertFalse(
            Order.objects.filter(
                medication_request=self.medication_request
            ).exists()
        )

    def test_other_pharmacy_cannot_create_quote(self):
        self.authenticate(self.other_staff)

        response = self.client.post(
            self.create_url,
            self.full_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assert_request_pending()

    def test_other_patient_cannot_read_quote(self):
        created = self.submit_quote()
        self.assertEqual(created.status_code, 201)

        self.authenticate(self.other_patient)
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 404)

    def test_other_patient_cannot_decide(self):
        created = self.submit_quote()
        self.assertEqual(created.status_code, 201)

        response = self.decide(
            "ACCEPT",
            patient=self.other_patient,
        )

        self.assertEqual(response.status_code, 404)

        quote = PharmacyQuote.objects.get(
            assignment=self.assignment
        )
        self.assertEqual(
            quote.status,
            PharmacyQuote.Status.PROPOSED,
        )

    def test_unauthenticated_requests_are_rejected(self):
        self.client.credentials()

        endpoints = [
            ("post", self.create_url, self.full_payload()),
            ("get", self.detail_url, None),
            (
                "post",
                self.decision_url,
                {"decision": "ACCEPT"},
            ),
        ]

        for method, url, payload in endpoints:
            with self.subTest(method=method, url=url):
                if method == "get":
                    response = self.client.get(url)
                else:
                    response = self.client.post(
                        url, payload, format="json"
                    )

                self.assertIn(
                    response.status_code,
                    [401, 403],
                )

        self.assert_request_pending()

    def test_duplicate_quote_is_rejected(self):
        first = self.submit_quote()
        self.assertEqual(first.status_code, 201)

        second = self.submit_quote()

        self.assertEqual(second.status_code, 400)
        self.assertEqual(
            PharmacyQuote.objects.filter(
                assignment=self.assignment
            ).count(),
            1,
        )

    def test_invalid_price_is_rejected(self):
        payload = self.full_payload()
        payload["items"][0]["unit_price"] = -100

        response = self.submit_quote(payload)

        self.assertEqual(response.status_code, 400)
        self.assert_request_pending()

    def test_unknown_medication_is_rejected(self):
        payload = self.full_payload()
        payload["items"][0]["item_id"] = str(uuid4())

        response = self.submit_quote(payload)

        self.assertEqual(response.status_code, 400)
        self.assert_request_pending()

    def test_quote_not_allowed_when_not_requested(self):
        self.medication_request.quote_requested = False
        self.medication_request.save(
            update_fields=["quote_requested"]
        )

        response = self.submit_quote()

        self.assertEqual(response.status_code, 400)
        self.assert_request_pending()

    def test_classic_response_cannot_bypass_quote(self):
        self.authenticate(self.staff)

        response = self.client.post(
            self.respond_url,
            {
                "response": "ACCEPTED",
                "available_item_quantities": [
                    {
                        "item_id": str(self.item_one.id),
                        "quantity": 2,
                    },
                    {
                        "item_id": str(self.item_two.id),
                        "quantity": 3,
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assert_request_pending()

    def test_pharmacy_sees_quote_requested_flag(self):
        self.authenticate(self.staff)

        pending_url = reverse(
            "medication_requests:pharmacy-pending"
        )

        response = self.client.get(pending_url)

        self.assertEqual(response.status_code, 200)

        assignment_data = next(
            (
                entry
                for entry in response.data
                if str(entry["id"]) == str(self.assignment.id)
            ),
            None,
        )

        self.assertIsNotNone(assignment_data)
        self.assertTrue(assignment_data["quote_requested"])

    def test_invalid_patient_decision_is_rejected(self):
        created = self.submit_quote()
        self.assertEqual(created.status_code, 201)

        response = self.decide("INVALID")

        self.assertEqual(response.status_code, 400)

        quote = PharmacyQuote.objects.get(
            assignment=self.assignment
        )
        self.assertEqual(
            quote.status,
            PharmacyQuote.Status.PROPOSED,
        )

    def test_patient_cannot_decide_twice(self):
        created = self.submit_quote()
        self.assertEqual(created.status_code, 201)

        first = self.decide("ACCEPT")
        self.assertEqual(first.status_code, 200)

        second = self.decide("REJECT")
        self.assertEqual(second.status_code, 400)

        quote = PharmacyQuote.objects.get(
            assignment=self.assignment
        )
        self.assertEqual(
            quote.status,
            PharmacyQuote.Status.ACCEPTED,
        )

    def test_pharmacy_can_reject_quote_request_without_quote(self):
        assignment = MatchingService.respond(
            assignment_id=self.assignment.id,
            response=PharmacyAssignment.Status.REJECTED,
            note="Aucun médicament disponible.",
        )

        self.assertEqual(
            assignment.status,
            PharmacyAssignment.Status.REJECTED,
        )

        self.assertFalse(
            PharmacyQuote.objects.filter(
                assignment=self.assignment
            ).exists()
        )

        self.medication_request.refresh_from_db()

        self.assertIn(
            self.medication_request.status,
            [
                MedicationRequest.Status.MATCHING,
                MedicationRequest.Status.UNAVAILABLE,
            ],
        )

    def test_pharmacy_can_reject_quote_request_via_classic_endpoint(self):
        self.authenticate(self.staff)

        response = self.client.post(
            self.respond_url,
            {
                "response": "REJECTED",
                "note": "Aucun médicament disponible.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assignment.refresh_from_db()

        self.assertEqual(
            self.assignment.status,
            PharmacyAssignment.Status.REJECTED,
        )

        self.assertFalse(
            PharmacyQuote.objects.filter(
                assignment=self.assignment
            ).exists()
        )

        self.medication_request.refresh_from_db()

        self.assertIn(
            self.medication_request.status,
            [
                MedicationRequest.Status.MATCHING,
                MedicationRequest.Status.UNAVAILABLE,
            ],
        )


