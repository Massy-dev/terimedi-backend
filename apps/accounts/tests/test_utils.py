from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.accounts.utils import normalize_phone_number


class NormalizePhoneNumberTests(SimpleTestCase):
    def test_normalizes_ivorian_number_to_e164(self):
        result = normalize_phone_number("07 01 02 03 04")

        self.assertEqual(result, "+2250701020304")

    def test_rejects_invalid_phone_number(self):
        with self.assertRaises(ValidationError):
            normalize_phone_number("123")