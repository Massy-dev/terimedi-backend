from django.contrib.gis.geos import Point
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.medication_requests.models import MedicationRequest, PharmacyAssignment
from apps.pharmacies.models import Pharmacy

class PatientMedicationRequestReadAPITests(APITestCase):

    def setUp(self):
        self.patient_a = User.objects.create_user(
            phone_number="07 01 02 03 04",
            password="TestPassword2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.patient_b = User.objects.create_user(
            phone_number="05 01 02 03 04",
            password="TestPassword2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

        self.request_a1 = self.create_request(
            patient=self.patient_a,
            text="Paracetamol",
        )

        self.request_a2 = self.create_request(
            patient=self.patient_a,
            text="Doliprane",
        )

        self.request_b1 = self.create_request(
            patient=self.patient_b,
            text="Ibuprofene",
        )

    def create_request(self, *, patient, text):
        return MedicationRequest.objects.create(
            patient=patient,
            input_type=MedicationRequest.InputType.TEXT,
            text=text,
            patient_location=Point(
                -4.0080,
                5.3600,
                srid=4326,
            ),
            status=MedicationRequest.Status.PENDING,
        )

    def test_patient_list_contains_only_own_requests(self):
        self.client.force_authenticate(
            user=self.patient_a
        )

        response = self.client.get(
            "/api/v1/medication-requests/"
        )

        self.assertEqual(response.status_code, 200)

        returned_ids = {
            str(item["id"])
            for item in response.data
        }

        self.assertEqual(
            returned_ids,
            {
                str(self.request_a1.id),
                str(self.request_a2.id),
            },
        )

        self.assertNotIn(
            str(self.request_b1.id),
            returned_ids,
        )

    def test_patient_cannot_read_another_patients_request(self):
        self.client.force_authenticate(
            user=self.patient_a
        )

        response = self.client.get(
            (
                "/api/v1/medication-requests/"
                f"{self.request_b1.id}/"
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )
    def test_patient_can_see_current_assignment(self):
      pharmacy = Pharmacy.objects.create(
          name="Pharmacie Test",
          address="Cocody",
          commune="Cocody",
          location=Point(
              -4.0100,
              5.3600,
              srid=4326,
          ),
          status=Pharmacy.Status.APPROVED,
          is_active=True,
      )

      PharmacyAssignment.objects.create(
          medication_request=self.request_a1,
          pharmacy=pharmacy,
          status=PharmacyAssignment.Status.ACCEPTED,
      )

      self.request_a1.status = (
          MedicationRequest.Status.PHARMACY_FOUND
      )
      self.request_a1.save(
          update_fields=["status"]
      )

      self.client.force_authenticate(
          user=self.patient_a
      )

      response = self.client.get(
          (
              "/api/v1/medication-requests/"
              f"{self.request_a1.id}/"
          )
      )

      self.assertEqual(
          response.status_code,
          200,
      )

      self.assertEqual(
          response.data["current_assignment"]["status"],
          PharmacyAssignment.Status.ACCEPTED,
      )

      self.assertEqual(
          response.data["current_assignment"]["pharmacy"]["id"],
          pharmacy.id,
      )

      self.assertEqual(
          response.data["current_assignment"]["pharmacy"]["name"],
          "Pharmacie Test",
      )