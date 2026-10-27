import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Notification


class NotificationAPITests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            phone_number="+2250700000001",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            phone_number="+2250700000002",
            password="TestPassword123!",
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.notification = Notification.objects.create(
            user=self.user,
            title="Nouvelle réponse",
            body="Une pharmacie a répondu à votre demande.",
            data={"type": "QUOTE_RECEIVED"},
        )

        self.other_notification = Notification.objects.create(
            user=self.other_user,
            title="Notification privée",
            body="Cette notification appartient à un autre utilisateur.",
        )

    def test_list_only_own_notifications(self):
        response = self.client.get("/api/v1/notifications/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            str(response.data["results"][0]["id"]),
            str(self.notification.id),
        )

    def test_unread_count(self):
        response = self.client.get(
            "/api/v1/notifications/unread-count/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 1)

    def test_mark_notification_as_read(self):
        response = self.client.patch(
            f"/api/v1/notifications/{self.notification.id}/read/"
        )

        self.assertEqual(response.status_code, 200)

        self.notification.refresh_from_db()

        self.assertTrue(self.notification.is_read)
        self.assertIsNotNone(self.notification.read_at)

    def test_cannot_mark_other_users_notification(self):
        response = self.client.patch(
            f"/api/v1/notifications/{self.other_notification.id}/read/"
        )

        self.assertEqual(response.status_code, 404)

        self.other_notification.refresh_from_db()
        self.assertFalse(self.other_notification.is_read)

    def test_mark_all_as_read(self):
        Notification.objects.create(
            user=self.user,
            title="Deuxième notification",
            body="Autre événement.",
        )

        response = self.client.post(
            "/api/v1/notifications/read-all/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated_count"], 2)

        self.assertFalse(
            Notification.objects.filter(
                user=self.user,
                is_read=False,
            ).exists()
        )

        self.other_notification.refresh_from_db()
        self.assertFalse(self.other_notification.is_read)

    def test_unauthenticated_access_is_denied(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/notifications/")

        self.assertIn(response.status_code, [401, 403])

    def test_unknown_notification_returns_404(self):
        response = self.client.patch(
            f"/api/v1/notifications/{uuid.uuid4()}/read/"
        )

        self.assertEqual(response.status_code, 404)