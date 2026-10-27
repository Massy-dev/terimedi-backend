
import uuid

from django.contrib.gis.geos import Point
from django.test import TestCase

from apps.accounts.models import User
from apps.medication_requests.models import (
    MedicationRequest,
    MedicationRequestItem,
    PharmacyAssignment,
)
from apps.medication_requests.services.availability import (
    AvailabilityService,
)


class AvailabilityServiceTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            phone_number="07 88 11 22 33",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.medication_request = MedicationRequest.objects.create(
            patient=self.patient,
            input_type=MedicationRequest.InputType.TEXT,
            text="Deux médicaments",
            patient_location=Point(
                -4.0080,
                5.3600,
                srid=4326,
            ),
        )

        self.paracetamol = MedicationRequestItem.objects.create(
            medication_request=self.medication_request,
            name="Paracétamol",
            dosage="500 mg",
            quantity=2,
            unit=MedicationRequestItem.Unit.BOTTLE,
            position=0,
        )

        self.doliprane = MedicationRequestItem.objects.create(
            medication_request=self.medication_request,
            name="Doliprane",
            dosage="300 mg",
            quantity=3,
            unit=MedicationRequestItem.Unit.BOX,
            position=1,
        )

    def validate(self, response, quantities):
        return AvailabilityService.validate(
            medication_request=self.medication_request,
            response=response,
            quantities=quantities,
        )

    @staticmethod
    def entry(item, quantity):
        return {
            "item_id": str(item.id),
            "quantity": quantity,
        }

    def test_complete_availability_is_accepted(self):
        result = self.validate(
            PharmacyAssignment.Status.ACCEPTED,
            [
                self.entry(self.paracetamol, 2),
                self.entry(self.doliprane, 3),
            ],
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["quantity"], 2)
        self.assertEqual(result[1]["quantity"], 3)

    def test_partial_availability_is_accepted(self):
        result = self.validate(
            PharmacyAssignment.Status.PARTIAL,
            [
                self.entry(self.paracetamol, 2),
                self.entry(self.doliprane, 1),
            ],
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["quantity"], 2)
        self.assertEqual(result[1]["quantity"], 1)

    def test_missing_item_is_normalized_to_zero(self):
        result = self.validate(
            PharmacyAssignment.Status.PARTIAL,
            [
                self.entry(self.paracetamol, 2),
            ],
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["quantity"], 2)
        self.assertEqual(result[1]["quantity"], 0)

    def test_empty_list_is_valid_for_rejection(self):
        result = self.validate(
            PharmacyAssignment.Status.REJECTED,
            [],
        )

        self.assertEqual(len(result), 2)
        self.assertTrue(
            all(item["quantity"] == 0 for item in result)
        )

    def test_explicit_zero_quantities_are_valid_for_rejection(self):
        result = self.validate(
            PharmacyAssignment.Status.REJECTED,
            [
                self.entry(self.paracetamol, 0),
                self.entry(self.doliprane, 0),
            ],
        )

        self.assertEqual(
            [item["quantity"] for item in result],
            [0, 0],
        )

    def test_quantity_greater_than_requested_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                [
                    self.entry(self.paracetamol, 3),
                ],
            )

    def test_negative_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                [
                    self.entry(self.paracetamol, -1),
                ],
            )

    def test_decimal_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                [
                    self.entry(self.paracetamol, 1.5),
                ],
            )

    def test_boolean_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                [
                    self.entry(self.paracetamol, True),
                ],
            )

    def test_string_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                [
                    self.entry(self.paracetamol, "1"),
                ],
            )

    def test_unknown_item_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                [
                    {
                        "item_id": str(uuid.uuid4()),
                        "quantity": 1,
                    },
                ],
            )

    def test_duplicate_item_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                [
                    self.entry(self.paracetamol, 1),
                    self.entry(self.paracetamol, 1),
                ],
            )

    def test_invalid_uuid_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                [
                    {
                        "item_id": "invalid-uuid",
                        "quantity": 1,
                    },
                ],
            )

    def test_non_list_input_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                {
                    "item_id": str(self.paracetamol.id),
                    "quantity": 1,
                },
            )

    def test_non_object_entry_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                ["Paracétamol"],
            )

    def test_missing_quantity_field_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                [
                    {
                        "item_id": str(self.paracetamol.id),
                    },
                ],
            )

    def test_extra_field_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                [
                    {
                        "item_id": str(self.paracetamol.id),
                        "quantity": 1,
                        "price": 1500,
                    },
                ],
            )

    def test_accepted_response_requires_full_availability(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.ACCEPTED,
                [
                    self.entry(self.paracetamol, 2),
                    self.entry(self.doliprane, 1),
                ],
            )

    def test_partial_response_cannot_be_empty(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                [],
            )

    def test_partial_response_cannot_be_complete(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.PARTIAL,
                [
                    self.entry(self.paracetamol, 2),
                    self.entry(self.doliprane, 3),
                ],
            )

    def test_rejected_response_cannot_have_available_items(self):
        with self.assertRaises(ValueError):
            self.validate(
                PharmacyAssignment.Status.REJECTED,
                [
                    self.entry(self.paracetamol, 1),
                ],
            )

    def test_invalid_response_status_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(
                "UNKNOWN",
                [
                    self.entry(self.paracetamol, 1),
                ],
            )

    def test_request_without_structured_items_is_rejected(self):
        legacy_request = MedicationRequest.objects.create(
            patient=self.patient,
            input_type=MedicationRequest.InputType.TEXT,
            text="Ancienne demande",
            patient_location=Point(
                -4.0080,
                5.3600,
                srid=4326,
            ),
        )

        with self.assertRaises(ValueError):
            AvailabilityService.validate(
                medication_request=legacy_request,
                response=PharmacyAssignment.Status.PARTIAL,
                quantities=[],
            )
