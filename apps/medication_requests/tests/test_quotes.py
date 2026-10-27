
from datetime import time, timedelta
from uuid import uuid4

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.services.orders import OrderService

from apps.accounts.models import User
from apps.pharmacies.models import (
    Pharmacy,
    PharmacyMembership,
    PharmacyOpeningHours,
)
from apps.medication_requests.models import (
    MedicationRequest,
    MedicationRequestItem,
    PharmacyAssignment,
    PharmacyQuote,
    PharmacyQuoteItem,
)
from apps.medication_requests.services.matching import (
    MatchingService,
)
from apps.medication_requests.services.quotes import (
    QuoteService,
)


class QuoteServiceTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            phone_number="07 01 02 03 04",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.pharmacy_user = User.objects.create_user(
            phone_number="07 05 06 07 08",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.other_user = User.objects.create_user(
            phone_number="07 09 10 11 12",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.location = Point(
            -4.0083,
            5.3599,
            srid=4326,
        )

        self.pharmacy = self.create_pharmacy(
            name="Pharmacie Première",
            longitude=-4.0090,
            latitude=5.3600,
        )

        PharmacyMembership.objects.create(
            pharmacy=self.pharmacy,
            user=self.pharmacy_user,
            role=PharmacyMembership.Role.STAFF,
            is_active=True,
        )

        self.medication_request = self.create_request()

        self.item_one = MedicationRequestItem.objects.create(
            medication_request=self.medication_request,
            name="Paracétamol",
            dosage="500 mg",
            quantity=3,
            unit=MedicationRequestItem.Unit.BOX,
            position=0,
        )

        self.item_two = MedicationRequestItem.objects.create(
            medication_request=self.medication_request,
            name="Vitamine C",
            dosage="1000 mg",
            quantity=2,
            unit=MedicationRequestItem.Unit.BOX,
            position=1,
        )

        self.assignment = PharmacyAssignment.objects.create(
            medication_request=self.medication_request,
            pharmacy=self.pharmacy,
            status=PharmacyAssignment.Status.PENDING,
            expires_at=timezone.now() + timedelta(minutes=30),
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

    def create_request(
        self,
        *,
        quote_requested=True,
        status=MedicationRequest.Status.MATCHING,
    ):
        return MedicationRequest.objects.create(
            patient=self.patient,
            input_type=MedicationRequest.InputType.TEXT,
            text="Paracétamol et Vitamine C",
            patient_location=self.location,
            quote_requested=quote_requested,
            status=status,
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

    def complete_items(self):
        return [
            {
                "item_id": str(self.item_one.id),
                "quantity": 3,
                "unit_price": 1500,
            },
            {
                "item_id": str(self.item_two.id),
                "quantity": 2,
                "unit_price": 2000,
            },
        ]

    def partial_items(self):
        return [
            {
                "item_id": str(self.item_one.id),
                "quantity": 2,
                "unit_price": 1500,
            },
            {
                "item_id": str(self.item_two.id),
                "quantity": 0,
                "unit_price": 2000,
            },
        ]

    def submit_quote(
        self,
        *,
        response=PharmacyAssignment.Status.ACCEPTED,
        items=None,
        pharmacy_user=None,
    ):
        return QuoteService.create_quote(
            assignment_id=self.assignment.id,
            pharmacy_user=(
                pharmacy_user
                if pharmacy_user is not None
                else self.pharmacy_user
            ),
            response=response,
            items=(
                items
                if items is not None
                else self.complete_items()
            ),
        )

    def test_create_complete_quote(self):
        quote = self.submit_quote()

        self.assertEqual(
            quote.status,
            PharmacyQuote.Status.PROPOSED,
        )
        self.assertEqual(quote.total_amount, 8500)
        self.assertEqual(quote.items.count(), 2)

        self.medication_request.refresh_from_db()
        self.assignment.refresh_from_db()

        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.QUOTE_PENDING,
        )
        self.assertEqual(
            self.assignment.status,
            PharmacyAssignment.Status.ACCEPTED,
        )

        subtotals = list(
            quote.items.order_by("position")
            .values_list("subtotal", flat=True)
        )
        self.assertEqual(subtotals, [4500, 4000])

    def test_create_partial_quote(self):
        quote = self.submit_quote(
            response=PharmacyAssignment.Status.PARTIAL,
            items=self.partial_items(),
        )

        self.assertEqual(quote.total_amount, 3000)
        self.assertEqual(quote.items.count(), 1)

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
                    "quantity": 0,
                },
            ],
        )

    def test_patient_accepts_quote(self):
        quote = self.submit_quote()

        result = QuoteService.decide(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
            decision="ACCEPT",
        )

        quote.refresh_from_db()
        self.medication_request.refresh_from_db()

        self.assertEqual(result.id, quote.id)
        self.assertEqual(
            quote.status,
            PharmacyQuote.Status.ACCEPTED,
        )
        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.PHARMACY_FOUND,
        )
        self.assertIsNotNone(quote.decided_at)

    def test_patient_accepts_partial_quote(self):
        quote = self.submit_quote(
            response=PharmacyAssignment.Status.PARTIAL,
            items=self.partial_items(),
        )

        QuoteService.decide(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
            decision="ACCEPT",
        )

        quote.refresh_from_db()
        self.medication_request.refresh_from_db()

        self.assertEqual(
            quote.status,
            PharmacyQuote.Status.ACCEPTED,
        )
        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.PHARMACY_FOUND,
        )

    def test_reject_quote_assigns_next_pharmacy(self):
        self.make_open_now(self.pharmacy)

        second_pharmacy = self.create_pharmacy(
            name="Pharmacie Deuxième",
            longitude=-4.0300,
            latitude=5.3800,
        )
        self.make_open_now(second_pharmacy)

        quote = self.submit_quote()

        QuoteService.decide(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
            decision="REJECT",
        )

        quote.refresh_from_db()
        self.assignment.refresh_from_db()
        self.medication_request.refresh_from_db()

        self.assertEqual(
            quote.status,
            PharmacyQuote.Status.REJECTED,
        )
        self.assertEqual(
            self.assignment.status,
            PharmacyAssignment.Status.REJECTED,
        )
        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.MATCHING,
        )

        next_assignment = (
            self.medication_request.assignments
            .filter(status=PharmacyAssignment.Status.PENDING)
            .first()
        )

        self.assertIsNotNone(next_assignment)
        self.assertEqual(
            next_assignment.pharmacy,
            second_pharmacy,
        )

    def test_reject_quote_without_next_pharmacy(self):
        quote = self.submit_quote()

        QuoteService.decide(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
            decision="REJECT",
        )

        quote.refresh_from_db()
        self.medication_request.refresh_from_db()

        self.assertEqual(
            quote.status,
            PharmacyQuote.Status.REJECTED,
        )
        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.UNAVAILABLE,
        )

    def test_unauthorized_pharmacy_user(self):
        with self.assertRaises(ValueError):
            self.submit_quote(
                pharmacy_user=self.other_user,
            )

        self.assertFalse(
            PharmacyQuote.objects.exists()
        )

    def test_quote_not_requested(self):
        self.medication_request.quote_requested = False
        self.medication_request.save(
            update_fields=["quote_requested"]
        )

        with self.assertRaises(ValueError):
            self.submit_quote()

    def test_expired_assignment(self):
        self.assignment.expires_at = (
            timezone.now() - timedelta(minutes=1)
        )
        self.assignment.save(
            update_fields=["expires_at"]
        )

        with self.assertRaises(ValueError):
            self.submit_quote()

    def test_duplicate_medication(self):
        items = [
            {
                "item_id": str(self.item_one.id),
                "quantity": 2,
                "unit_price": 1500,
            },
            {
                "item_id": str(self.item_one.id),
                "quantity": 1,
                "unit_price": 1500,
            },
        ]

        with self.assertRaises(ValueError):
            self.submit_quote(
                response=PharmacyAssignment.Status.PARTIAL,
                items=items,
            )

    def test_unknown_medication(self):
        items = [
            {
                "item_id": str(uuid4()),
                "quantity": 1,
                "unit_price": 1500,
            },
        ]

        with self.assertRaises(ValueError):
            self.submit_quote(
                response=PharmacyAssignment.Status.PARTIAL,
                items=items,
            )

    def test_excessive_quantity(self):
        items = [
            {
                "item_id": str(self.item_one.id),
                "quantity": 10,
                "unit_price": 1500,
            },
        ]

        with self.assertRaises(ValueError):
            self.submit_quote(
                response=PharmacyAssignment.Status.PARTIAL,
                items=items,
            )

    def test_negative_price(self):
        items = self.complete_items()
        items[0]["unit_price"] = -500

        with self.assertRaises(ValueError):
            self.submit_quote(items=items)

    def test_boolean_price_is_rejected(self):
        items = self.complete_items()
        items[0]["unit_price"] = True

        with self.assertRaises(ValueError):
            self.submit_quote(items=items)

    def test_amount_overflow_is_rejected(self):
        items = self.complete_items()
        items[0]["unit_price"] = QuoteService.MAX_AMOUNT

        with self.assertRaises(ValueError):
            self.submit_quote(items=items)

    def test_duplicate_quote_is_rejected(self):
        self.submit_quote()

        with self.assertRaises(ValueError):
            self.submit_quote()

        self.assertEqual(
            PharmacyQuote.objects.count(),
            1,
        )

    def test_other_patient_cannot_decide(self):
        quote = self.submit_quote()

        with self.assertRaises(ValueError):
            QuoteService.decide(
                medication_request_id=self.medication_request.id,
                patient=self.other_user,
                decision="ACCEPT",
            )

        quote.refresh_from_db()

        self.assertEqual(
            quote.status,
            PharmacyQuote.Status.PROPOSED,
        )

    def test_decision_cannot_be_repeated(self):
        self.submit_quote()

        QuoteService.decide(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
            decision="ACCEPT",
        )

        with self.assertRaises(ValueError):
            QuoteService.decide(
                medication_request_id=self.medication_request.id,
                patient=self.patient,
                decision="ACCEPT",
            )

    def test_historical_request_quote(self):
        historical_request = self.create_request()

        historical_assignment = (
            PharmacyAssignment.objects.create(
                medication_request=historical_request,
                pharmacy=self.pharmacy,
                status=PharmacyAssignment.Status.PENDING,
                expires_at=(
                    timezone.now() + timedelta(minutes=30)
                ),
            )
        )

        quote = QuoteService.create_quote(
            assignment_id=historical_assignment.id,
            pharmacy_user=self.pharmacy_user,
            response=PharmacyAssignment.Status.ACCEPTED,
            items=[
                {
                    "name": "Paracétamol",
                    "dosage": "500 mg",
                    "unit": "BOX",
                    "quantity": 2,
                    "unit_price": 1200,
                },
            ],
        )

        self.assertEqual(quote.total_amount, 2400)
        self.assertEqual(quote.items.count(), 1)

        line = quote.items.first()

        self.assertIsNone(line.medication_item)
        self.assertEqual(line.name, "Paracétamol")

    def test_invalid_historical_medication_name(self):
        historical_request = self.create_request()

        historical_assignment = (
            PharmacyAssignment.objects.create(
                medication_request=historical_request,
                pharmacy=self.pharmacy,
                status=PharmacyAssignment.Status.PENDING,
            )
        )

        with self.assertRaises(ValueError):
            QuoteService.create_quote(
                assignment_id=historical_assignment.id,
                pharmacy_user=self.pharmacy_user,
                response=PharmacyAssignment.Status.ACCEPTED,
                items=[
                    {
                        "name": "",
                        "quantity": 1,
                        "unit_price": 1500,
                    },
                ],
            )

    def test_failed_quote_does_not_change_assignment(self):
        items = self.complete_items()
        items[0]["quantity"] = 50

        with self.assertRaises(ValueError):
            self.submit_quote(items=items)

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
            PharmacyQuote.objects.exists()
        )
    
    def test_classic_response_cannot_bypass_quote(self):
        with self.assertRaises(ValueError):
            MatchingService.respond(
                assignment_id=self.assignment.id,
                response=PharmacyAssignment.Status.ACCEPTED,
                available_item_quantities=[
                    {
                        "item_id": str(self.item_one.id),
                        "quantity": 3,
                    },
                    {
                        "item_id": str(self.item_two.id),
                        "quantity": 2,
                    },
                ],
            )

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
        self.assertFalse(PharmacyQuote.objects.exists())

    def test_order_cannot_be_confirmed_while_quote_pending(self):
        self.submit_quote()

        self.medication_request.refresh_from_db()

        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.QUOTE_PENDING,
        )

        with self.assertRaises(ValueError):
            OrderService.confirm_request(
                medication_request_id=self.medication_request.id,
                patient=self.patient,
            )

        self.assertFalse(Order.objects.exists())

    def test_order_cannot_bypass_unaccepted_quote(self):
        quote = self.submit_quote()

        # Simule une anomalie qui place prématurément
        # la demande au statut PHARMACY_FOUND.
        self.medication_request.status = (
            MedicationRequest.Status.PHARMACY_FOUND
        )
        self.medication_request.save(
            update_fields=["status", "updated_at"]
        )

        with self.assertRaises(ValueError):
            OrderService.confirm_request(
                medication_request_id=self.medication_request.id,
                patient=self.patient,
            )

        quote.refresh_from_db()

        self.assertEqual(
            quote.status,
            PharmacyQuote.Status.PROPOSED,
        )
        self.assertFalse(Order.objects.exists())

    def test_order_can_be_confirmed_after_quote_acceptance(self):
        quote = self.submit_quote()

        QuoteService.decide(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
            decision="ACCEPT",
        )

        order = OrderService.confirm_request(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
        )

        quote.refresh_from_db()
        self.medication_request.refresh_from_db()

        self.assertEqual(
            quote.status,
            PharmacyQuote.Status.ACCEPTED,
        )
        self.assertEqual(
            order.status,
            Order.Status.CONFIRMED,
        )
        self.assertEqual(
            order.patient,
            self.patient,
        )
        self.assertEqual(
            order.pharmacy,
            self.pharmacy,
        )
        self.assertEqual(
            order.assignment,
            self.assignment,
        )
        self.assertEqual(
            self.medication_request.status,
            MedicationRequest.Status.CONFIRMED,
        )

        # Une deuxième confirmation ne doit pas
        # créer une commande supplémentaire.
        same_order = OrderService.confirm_request(
            medication_request_id=self.medication_request.id,
            patient=self.patient,
        )

        self.assertEqual(same_order.id, order.id)
        self.assertEqual(Order.objects.count(), 1)

    
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

    def test_pharmacy_cannot_reject_quote_request_with_quantities(self):
        with self.assertRaises(ValueError):
            MatchingService.respond(
                assignment_id=self.assignment.id,
                response=PharmacyAssignment.Status.REJECTED,
                available_item_quantities=[
                    {
                        "item_id": str(self.item_one.id),
                        "quantity": 1,
                    },
                ],
            )

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
