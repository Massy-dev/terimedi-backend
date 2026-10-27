from django.test import TestCase

from apps.accounts.models import User


class UserManagerTests(TestCase):
    def test_create_user_normalizes_phone_number(self):
        user = User.objects.create_user(
            phone_number="07 01 02 03 04",
            password="TestPass123!",
        )

        self.assertEqual(user.phone_number, "+2250701020304")
        self.assertEqual(user.role, User.Role.PATIENT)
        self.assertTrue(user.check_password("TestPass123!"))

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            phone_number="05 01 02 03 04",
            password="AdminPass123!",
        )

        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_phone_verified)