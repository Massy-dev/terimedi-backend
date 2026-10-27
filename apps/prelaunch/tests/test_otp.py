from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.prelaunch.models import WaitlistEntry, OTPVerification
from apps.prelaunch.services.otp import create_otp, verify_otp


@override_settings(PRELAUNCH_OTP_PROVIDER="development", DEBUG=True)
class OTPServiceTests(TestCase):

    def setUp(self):
        self.entry = WaitlistEntry.objects.create(
            phone="+2250700000001",
            first_name="Test",
            commune="Cocody",
            consent_at=timezone.now(),
        )

    @patch(
        "apps.prelaunch.providers.development."
        "DevelopmentOTPProvider.send_code"
    )
    def test_create_otp(self, mock_send):
        verification = create_otp(self.entry)

        self.assertIsInstance(verification, OTPVerification)
        self.assertEqual(len(verification.code_hash) > 6, True)
        mock_send.assert_called_once()

    @patch(
        "apps.prelaunch.providers.development."
        "DevelopmentOTPProvider.send_code"
    )
    def test_valid_otp(self, mock_send):
        verification = create_otp(self.entry)
        code = mock_send.call_args.args[1]

        result = verify_otp(verification.id, code)

        self.assertTrue(result)

        self.entry.refresh_from_db()
        self.assertEqual(
            self.entry.status,
            WaitlistEntry.Status.VERIFIED,
        )
        self.assertIsNotNone(self.entry.phone_verified_at)

    @patch(
        "apps.prelaunch.providers.development."
        "DevelopmentOTPProvider.send_code"
    )
    def test_wrong_otp(self, mock_send):
        verification = create_otp(self.entry)
        actual_code = mock_send.call_args.args[1]
        wrong_code = (
            "000000" if actual_code != "000000" else "111111"
        )

        self.assertFalse(
            verify_otp(verification.id, wrong_code)
        )

    @patch(
        "apps.prelaunch.providers.development."
        "DevelopmentOTPProvider.send_code"
    )
    def test_expired_otp(self, mock_send):
        verification = create_otp(self.entry)

        verification.expires_at = (
            timezone.now() - timedelta(minutes=1)
        )
        verification.save(update_fields=["expires_at"])

        code = mock_send.call_args.args[1]

        self.assertFalse(
            verify_otp(verification.id, code)
        )

    @patch(
        "apps.prelaunch.providers.development."
        "DevelopmentOTPProvider.send_code"
    )
    def test_otp_cannot_be_reused(self, mock_send):
        verification = create_otp(self.entry)
        code = mock_send.call_args.args[1]

        self.assertTrue(verify_otp(verification.id, code))
        self.assertFalse(verify_otp(verification.id, code))

    @patch(
        "apps.prelaunch.providers.development."
        "DevelopmentOTPProvider.send_code"
    )
    def test_previous_otp_is_invalidated(self, mock_send):
        old_verification = create_otp(self.entry)
        old_code = mock_send.call_args.args[1]

        create_otp(self.entry)

        self.assertFalse(
            verify_otp(old_verification.id, old_code)
        )
    
    
    @patch(
        "apps.prelaunch.providers.development."
        "DevelopmentOTPProvider.send_code"
    )
    def test_failed_otp_delivery_removes_verification(self, mock_send):
        mock_send.side_effect = RuntimeError(
            "SMS provider unavailable"
        )

        with self.assertRaises(RuntimeError):
            create_otp(self.entry)

        self.assertFalse(
            OTPVerification.objects.filter(
                waitlist_entry=self.entry,
            ).exists()
        )

        self.entry.refresh_from_db()
        self.assertNotEqual(
            self.entry.status,
            WaitlistEntry.Status.VERIFIED,
        )

    
    @patch(
        "apps.prelaunch.providers.development."
        "DevelopmentOTPProvider.send_code"
    )
    def test_previous_otp_survives_failed_resend(self, mock_send):
        old_verification = create_otp(self.entry)
        old_code = mock_send.call_args.args[1]

        mock_send.side_effect = RuntimeError(
            "SMS provider unavailable"
        )

        with self.assertRaises(RuntimeError):
            create_otp(self.entry)

        old_verification.refresh_from_db()

        self.assertGreater(
            old_verification.expires_at,
            timezone.now(),
        )

        self.assertTrue(
            verify_otp(old_verification.id, old_code)
        )

        self.assertEqual(
            OTPVerification.objects.filter(
                waitlist_entry=self.entry,
            ).count(),
            1,
        )
    
    def test_second_otp_cannot_verify_already_verified_entry(self):
        from datetime import timedelta
        from django.contrib.auth.hashers import make_password
        from django.utils import timezone
        from apps.prelaunch.models import (
            WaitlistEntry,
            OTPVerification,
        )
        from apps.prelaunch.services.otp import verify_otp

        entry = WaitlistEntry.objects.create(
            phone="+2250700000077",
            commune="Cocody",
            consent_at=timezone.now(),
        )

        first_otp = OTPVerification.objects.create(
            waitlist_entry=entry,
            code_hash=make_password("123456"),
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        second_otp = OTPVerification.objects.create(
            waitlist_entry=entry,
            code_hash=make_password("654321"),
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        # Le premier OTP confirme le numéro.
        self.assertTrue(
            verify_otp(first_otp.id, "123456")
        )

        # Le second ne doit plus pouvoir confirmer ce numéro.
        self.assertFalse(
            verify_otp(second_otp.id, "654321")
        )

        entry.refresh_from_db()

        self.assertEqual(
            entry.status,
            WaitlistEntry.Status.VERIFIED,
        )

        second_otp.refresh_from_db()

        self.assertIsNone(second_otp.verified_at)


