from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import PhoneVerification
from apps.accounts.services.otp import OTPService

from django.core.cache import cache
from django.test import override_settings



class OTPServiceTests(TestCase):
    def test_create_verification_normalizes_phone_and_hashes_code(self):
        verification, code = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        self.assertEqual(
            verification.phone_number,
            "+2250701020304",
        )

        self.assertNotEqual(verification.code_hash, code)
        self.assertTrue(check_password(code, verification.code_hash))

    def test_verify_accepts_valid_code(self):
        verification, code = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        OTPService.verify(verification, code)

        verification.refresh_from_db()

        self.assertIsNotNone(verification.verified_at)
        self.assertEqual(verification.attempts, 1)

    def test_verify_rejects_invalid_code(self):
        verification, _ = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        with self.assertRaises(ValidationError):
            OTPService.verify(verification, "000000")

        verification.refresh_from_db()

        self.assertEqual(verification.attempts, 1)
        self.assertIsNone(verification.verified_at)

    def test_verify_rejects_expired_code(self):
        verification, code = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        verification.expires_at = timezone.now() - timedelta(seconds=1)
        verification.save(update_fields=["expires_at"])

        with self.assertRaises(ValidationError):
            OTPService.verify(verification, code)

    def test_verify_blocks_after_max_attempts(self):
        verification, code = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        verification.attempts = settings.OTP_MAX_ATTEMPTS
        verification.save(update_fields=["attempts"])

        with self.assertRaises(ValidationError):
            OTPService.verify(verification, code)

    def test_verify_rejects_already_verified_code(self):
        verification, code = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        OTPService.verify(verification, code)

        with self.assertRaises(ValidationError):
            OTPService.verify(verification, code)

    def test_create_verification_rejects_request_during_cooldown(self):
        OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        with self.assertRaises(ValidationError):
            OTPService.create_verification(
                phone_number="07 01 02 03 04",
                purpose=PhoneVerification.Purpose.REGISTRATION,
            )

    def test_new_verification_invalidates_previous_one(self):
        first_verification, first_code = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        first_verification.created_at = (
                timezone.now()
                - timedelta(
            seconds=settings.OTP_RESEND_COOLDOWN_SECONDS + 1
        )
        )
        first_verification.save(update_fields=["created_at"])

        second_verification, _ = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        first_verification.refresh_from_db()

        self.assertIsNotNone(first_verification.consumed_at)
        self.assertIsNone(second_verification.consumed_at)

        with self.assertRaises(ValidationError):
            OTPService.verify(
                first_verification,
                first_code,
            )