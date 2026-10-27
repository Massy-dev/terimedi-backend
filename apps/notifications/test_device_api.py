
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import DeviceToken


class DeviceTokenAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            phone_number="+2250100000001",
            password="test-password-not-for-production",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/notifications/devices/"
        self.token = "fcm-test-token-not-real"

    def test_register_device(self):
        response = self.client.post(
            self.url,
            {
                "token": self.token,
                "platform": "ANDROID",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            DeviceToken.objects.filter(
                user=self.user,
                token=self.token,
                is_active=True,
            ).exists()
        )

    def test_register_same_device_twice(self):
        payload = {
            "token": self.token,
            "platform": "ANDROID",
        }

        self.client.post(self.url, payload, format="json")
        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            DeviceToken.objects.filter(token=self.token).count(),
            1,
        )

    def test_deactivate_device(self):
        DeviceToken.objects.create(
            user=self.user,
            token=self.token,
            platform="ANDROID",
        )

        response = self.client.delete(
            self.url,
            {"token": self.token},
            format="json",
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            DeviceToken.objects.get(
                token=self.token,
            ).is_active
        )

    def test_anonymous_registration_is_rejected(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            self.url,
            {
                "token": self.token,
                "platform": "ANDROID",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)
