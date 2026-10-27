from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import PhoneVerification, User
from apps.accounts.services.otp import OTPService
from apps.accounts.services.registration import RegistrationService


class RegistrationServiceTests(TestCase):
    def create_verified_registration(self):
        verification, code = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        OTPService.verify(
            verification=verification,
            code=code,
        )

        verification.refresh_from_db()

        return verification

    def test_complete_registration_creates_patient(self):
        verification = self.create_verified_registration()

        user = RegistrationService.complete_registration(
            verification_id=verification.id,
            password="StrongPass123!",
            first_name="Awa",
            last_name="Kone",
        )

        self.assertEqual(
            user.phone_number,
            "+2250701020304",
        )
        self.assertEqual(
            user.role,
            User.Role.PATIENT,
        )
        self.assertTrue(user.is_phone_verified)
        self.assertTrue(
            user.check_password("StrongPass123!")
        )

    def test_complete_registration_consumes_verification(self):
        verification = self.create_verified_registration()

        RegistrationService.complete_registration(
            verification_id=verification.id,
            password="StrongPass123!",
        )

        verification.refresh_from_db()

        self.assertIsNotNone(
            verification.consumed_at
        )

    def test_complete_registration_rejects_unverified_challenge(self):
        verification, _ = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        with self.assertRaises(ValidationError):
            RegistrationService.complete_registration(
                verification_id=verification.id,
                password="StrongPass123!",
            )

        self.assertFalse(
            User.objects.filter(
                phone_number="+2250701020304"
            ).exists()
        )

    def test_complete_registration_rejects_consumed_challenge(self):
        verification = self.create_verified_registration()

        RegistrationService.complete_registration(
            verification_id=verification.id,
            password="StrongPass123!",
        )

        with self.assertRaises(ValidationError):
            RegistrationService.complete_registration(
                verification_id=verification.id,
                password="AnotherPass123!",
            )

    def test_complete_registration_rejects_wrong_purpose(self):
        verification, code = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.PASSWORD_RESET,
        )

        OTPService.verify(
            verification=verification,
            code=code,
        )

        with self.assertRaises(ValidationError):
            RegistrationService.complete_registration(
                verification_id=verification.id,
                password="StrongPass123!",
            )