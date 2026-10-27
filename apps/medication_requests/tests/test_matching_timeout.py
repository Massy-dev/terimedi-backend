from datetime import timedelta

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone
from apps.medication_requests.models import PharmacyQuote
from apps.accounts.models import User
from apps.pharmacies.models import (
    Pharmacy,
    PharmacyDutyPeriod,
)
from apps.medication_requests.models import (
    MedicationRequest,
    PharmacyAssignment,
)
from apps.medication_requests.tasks import (
    expire_pending_assignments,
)


class MatchingTimeoutTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            phone_number="07 01 02 03 04",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.request = MedicationRequest.objects.create(
            patient=self.patient,
            input_type=MedicationRequest.InputType.TEXT,
            text="Paracetamol",
            patient_location=Point(
                -4.0080,
                5.3600,
                srid=4326,
            ),
            status=MedicationRequest.Status.MATCHING,
        )

        self.pharmacy_a = self.create_pharmacy(
            name="Pharmacie A",
            longitude=-4.0083,
            latitude=5.3599,
        )

        self.pharmacy_b = self.create_pharmacy(
            name="Pharmacie B",
            longitude=-4.0200,
            latitude=5.3500,
        )

        now = timezone.now()

        # Les deux pharmacies sont de garde et donc éligibles.
        PharmacyDutyPeriod.objects.create(
            pharmacy=self.pharmacy_a,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )

        PharmacyDutyPeriod.objects.create(
            pharmacy=self.pharmacy_b,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )

        # La pharmacie A avait reçu la demande mais n'a pas répondu.
        self.assignment_a = PharmacyAssignment.objects.create(
            medication_request=self.request,
            pharmacy=self.pharmacy_a,
            status=PharmacyAssignment.Status.PENDING,
            expires_at=now - timedelta(minutes=1),
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

    def test_expired_quote_request_moves_to_next_pharmacy(self):
        """
        Une demande avec devis doit être réattribuée
        si la pharmacie ne répond pas avant expiration.
        """

        self.request.quote_requested = True
        self.request.save(
            update_fields=["quote_requested"]
        )

        expired_count = expire_pending_assignments()

        self.assignment_a.refresh_from_db()
        self.request.refresh_from_db()

        # L'attribution initiale a expiré.
        self.assertEqual(expired_count, 1)

        self.assertEqual(
            self.assignment_a.status,
            PharmacyAssignment.Status.EXPIRED,
        )

        # Une nouvelle attribution a été créée.
        assignment_b = PharmacyAssignment.objects.filter(
            medication_request=self.request,
            pharmacy=self.pharmacy_b,
        ).first()

        self.assertIsNotNone(assignment_b)

        self.assertEqual(
            assignment_b.status,
            PharmacyAssignment.Status.PENDING,
        )

        self.assertIsNotNone(assignment_b.expires_at)

        # La demande attend toujours une pharmacie.
        self.assertEqual(
            self.request.status,
            MedicationRequest.Status.MATCHING,
        )

        # Aucun devis ne doit avoir été créé.
        self.assertFalse(
            PharmacyQuote.objects.filter(
                assignment__medication_request=self.request
            ).exists()
        )

        # Une seule attribution est en attente.
        self.assertEqual(
            PharmacyAssignment.objects.filter(
                medication_request=self.request,
                status=PharmacyAssignment.Status.PENDING,
            ).count(),
            1,
        )

    def test_expired_assignment_moves_to_next_pharmacy(self):
        expired_count = expire_pending_assignments()

        self.assignment_a.refresh_from_db()
        self.request.refresh_from_db()

        self.assertEqual(
            expired_count,
            1,
        )

        self.assertEqual(
            self.assignment_a.status,
            PharmacyAssignment.Status.EXPIRED,
        )

        assignment_b = (
            PharmacyAssignment.objects
            .filter(
                medication_request=self.request,
                pharmacy=self.pharmacy_b,
            )
            .first()
        )

        self.assertIsNotNone(assignment_b)

        self.assertEqual(
            assignment_b.status,
            PharmacyAssignment.Status.PENDING,
        )

        self.assertIsNotNone(
            assignment_b.expires_at
        )

        self.assertEqual(
            self.request.status,
            MedicationRequest.Status.MATCHING,
        )

        self.assertEqual(
            PharmacyAssignment.objects.filter(
                medication_request=self.request,
                status=PharmacyAssignment.Status.PENDING,
            ).count(),
            1,
        )