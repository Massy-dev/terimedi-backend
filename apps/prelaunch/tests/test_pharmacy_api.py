
from django.core.cache import caches
from django.test import override_settings
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.prelaunch.models import PharmacyPreRegistration


# Cache isolé pour éviter d'utiliser le Redis de développement.
# Le throttling DRF utilise le cache "default".
TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "terimedi-pharmacy-prelaunch-tests",
    }
}


@override_settings(
    CACHES=TEST_CACHES,
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "pharmacy_prelaunch": "1000/hour",
        },
    },
)
class PharmacyPreRegistrationAPITests(APITestCase):

    def setUp(self):
        super().setUp()

        # Nettoie uniquement le cache local des tests.
        caches["default"].clear()

        self.url = reverse("prelaunch-pharmacy-register")

        self.valid_payload = {
            "pharmacy_name": "Pharmacie Riviera Test",
            "commune": "Cocody",
            "address": "Riviera 2, Abidjan",
            "contact_name": "Responsable Test",
            "phone": "0700000096",
            "email": "contact@example.com",
            "is_on_duty": False,
            "consent": True,
        }

    def test_pharmacy_registration_success(self):
        response = self.client.post(
            self.url,
            self.valid_payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn("message", response.data)
        self.assertNotIn("id", response.data)

        self.assertEqual(
            PharmacyPreRegistration.objects.count(),
            1,
        )

        pharmacy = PharmacyPreRegistration.objects.first()

        self.assertEqual(
            pharmacy.pharmacy_name,
            "Pharmacie Riviera Test",
        )

        self.assertEqual(
            pharmacy.phone,
            "+2250700000096",
        )

        self.assertEqual(
            pharmacy.status,
            PharmacyPreRegistration.Status.NEW,
        )

        self.assertIsNotNone(pharmacy.consent_at)

    def test_duplicate_phone_returns_generic_response(self):
        first_response = self.client.post(
            self.url,
            self.valid_payload,
            format="json",
        )

        second_response = self.client.post(
            self.url,
            self.valid_payload,
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            first_response.data,
            second_response.data,
        )

        self.assertNotIn(
            "id",
            first_response.data,
        )

        self.assertEqual(
            PharmacyPreRegistration.objects.count(),
            1,
        )

    def test_registration_requires_consent(self):
        payload = self.valid_payload.copy()
        payload["consent"] = False

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            PharmacyPreRegistration.objects.count(),
            0,
        )

    def test_registration_requires_consent_field(self):
        payload = self.valid_payload.copy()
        payload.pop("consent")

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            PharmacyPreRegistration.objects.count(),
            0,
        )

    def test_registration_requires_pharmacy_name(self):
        payload = self.valid_payload.copy()
        payload["pharmacy_name"] = ""

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            PharmacyPreRegistration.objects.count(),
            0,
        )

    def test_invalid_phone_is_rejected(self):
        payload = self.valid_payload.copy()
        payload["phone"] = "123"

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            PharmacyPreRegistration.objects.count(),
            0,
        )

    def test_pharmacy_cannot_set_approved_status(self):
        payload = self.valid_payload.copy()
        payload["status"] = "APPROVED"

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        pharmacy = PharmacyPreRegistration.objects.first()

        self.assertEqual(
            pharmacy.status,
            PharmacyPreRegistration.Status.NEW,
        )

    def test_duplicate_does_not_expose_existing_registration(self):
        first_response = self.client.post(
            self.url,
            self.valid_payload,
            format="json",
        )

        second_response = self.client.post(
            self.url,
            self.valid_payload,
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            first_response.data,
            second_response.data,
        )

        self.assertNotIn(
            "id",
            first_response.data,
        )

        self.assertEqual(
            PharmacyPreRegistration.objects.count(),
            1,
        )

    def test_throttling_blocks_excessive_requests(self):
      
      from rest_framework.throttling import ScopedRateThrottle

      with override_settings(
          REST_FRAMEWORK={
              "DEFAULT_THROTTLE_RATES": {
                  "pharmacy_prelaunch": "2/hour",
              },
          },
      ):
          caches["default"].clear()

          # Force DRF à relire le taux configuré pour ce test.
          ScopedRateThrottle.THROTTLE_RATES = {
              "pharmacy_prelaunch": "2/hour",
          }

          try:
              responses = [
                  self.client.post(
                      self.url,
                      self.valid_payload,
                      format="json",
                  )
                  for _ in range(3)
              ]

              self.assertEqual(responses[0].status_code, 200)
              self.assertEqual(responses[1].status_code, 200)
              self.assertEqual(responses[2].status_code, 429)

              self.assertEqual(
                  PharmacyPreRegistration.objects.count(),
                  1,
              )
          finally:
              ScopedRateThrottle.THROTTLE_RATES = None