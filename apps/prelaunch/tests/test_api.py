import uuid
from unittest.mock import patch
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.prelaunch.models import WaitlistEntry, OTPVerification

from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.utils import timezone



class WaitlistAPITests(APITestCase):

    
    def setUp(self):
        self.url = reverse("prelaunch-waitlist")

    @override_settings(
      DEBUG=True,
      PRELAUNCH_OTP_PROVIDER="development",
    )
    @patch(
        "apps.prelaunch.views.OTPRateLimiter.check",
        return_value=True,
    )
    @patch(
        "apps.prelaunch.providers.development.DevelopmentOTPProvider.send_code",
    )
    
    def test_registration_with_referral(
        self,
        mock_send,
        mock_limit,
    ):

        referrer = WaitlistEntry.objects.create(
            phone="+2250700000089",
            commune="Cocody",
            consent_at=timezone.now(),
            status=WaitlistEntry.Status.VERIFIED,
            phone_verified_at=timezone.now(),
            referral_code="TM-TEST1234",
        )

        response = self.client.post(
            self.url,
            {
                "first_name": "FilleulTest",
                "phone": "07 00 00 00 90",
                "commune": "Cocody",
                "consent": True,
                "referral_code": "TM-TEST1234",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        filleul = WaitlistEntry.objects.get(
            phone="+2250700000090"
        )

        self.assertEqual(filleul.referred_by_id, referrer.id)
        self.assertEqual(filleul.status, WaitlistEntry.Status.PENDING)


    @override_settings(
      DEBUG=True,
      PRELAUNCH_OTP_PROVIDER="development",
    )
    @patch(
      "apps.prelaunch.views.OTPRateLimiter.check",
      return_value=True,
    )
    @patch(
      "apps.prelaunch.providers.development.DevelopmentOTPProvider.send_code",
    )
    def test_registration_success(self, mock_send, mock_limit):
        response = self.client.post(
            self.url,
            {
                "first_name": "Test",
                "phone": "07 00 00 00 95",
                "commune": "Cocody",
                "consent": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn(
            "verification_id",
            response.data,
        )

        self.assertNotIn(
            "code",
            response.data,
        )

        entry = WaitlistEntry.objects.get(
            phone="+2250700000095"
        )

        self.assertEqual(
            entry.status,
            WaitlistEntry.Status.PENDING,
        )

        mock_send.assert_called_once()

    
    @override_settings(
        DEBUG=True,
        PRELAUNCH_OTP_PROVIDER="development",
    )
    @patch(
        "apps.prelaunch.views.OTPRateLimiter.check",
        return_value=True,
    )
    @patch(
        "apps.prelaunch.providers.development."
        "DevelopmentOTPProvider.send_code"
    )
    def test_registration_preserves_otp_on_uncertain_delivery(
        self,
        mock_send,
        mock_limit,
    ):
        from apps.prelaunch.providers.exceptions import (
            OTPDeliveryUncertain,
        )

        mock_send.side_effect = OTPDeliveryUncertain(
            "SMS delivery status uncertain"
        )

        # Capture the OTP generated before the simulated timeout.
        captured_code = {}

        def uncertain_delivery(phone, code):
            captured_code["value"] = code
            raise OTPDeliveryUncertain(
                "SMS delivery status uncertain"
            )

        mock_send.side_effect = uncertain_delivery

        response = self.client.post(
            self.url,
            {
                "first_name": "PatientTimeout",
                "phone": "07 00 00 00 97",
                "commune": "Cocody",
                "consent": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 202)

        entry = WaitlistEntry.objects.get(
            phone="+2250700000097"
        )

        verification = OTPVerification.objects.get(
            waitlist_entry=entry
        )

        from django.contrib.auth.hashers import check_password

        self.assertTrue(
            check_password(
                captured_code["value"],
                verification.code_hash,
            )
        )

        self.assertGreater(
            verification.expires_at,
            timezone.now(),
        )

    def test_registration_requires_consent(self):
        response = self.client.post(
            self.url,
            {
                "phone": "07 00 00 00 95",
                "commune": "Cocody",
                "consent": False,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_registration_rejects_invalid_phone(self):
        response = self.client.post(
            self.url,
            {
                "phone": "12345",
                "commune": "Cocody",
                "consent": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @patch(
      "apps.prelaunch.views.OTPRateLimiter.check",
      return_value=True,
    )
    def test_verified_number_does_not_reveal_registration(
        self,
        mock_limit,
    ):
        from django.utils import timezone

        WaitlistEntry.objects.create(
            phone="+2250700000092",
            commune="Cocody",
            consent_at=timezone.now(),
            status=WaitlistEntry.Status.VERIFIED,
            phone_verified_at=timezone.now(),
        )

        response = self.client.post(
            self.url,
            {
                "phone": "07 00 00 00 92",
                "commune": "Cocody",
                "consent": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("verification_id", response.data)
        self.assertNotIn("already", str(response.data).lower())

@override_settings(
    DEBUG=True,
    PRELAUNCH_OTP_PROVIDER="development",
)
class OTPAPITests(APITestCase):

    def setUp(self):
        self.verify_url = reverse("prelaunch-otp-verify")
        self.resend_url = reverse("prelaunch-otp-resend")

   
    
    def test_verify_success(self):
        entry = WaitlistEntry.objects.create(
            phone="+2250700000091",
            first_name="PatientTest",
            commune="Cocody",
            consent_at=timezone.now(),
        )

        verification = OTPVerification.objects.create(
            waitlist_entry=entry,
            code_hash=make_password("123456"),
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        response = self.client.post(
            self.verify_url,
            {
                "verification_id": str(verification.id),
                "code": "123456",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["status"],
            "VERIFIED",
        )

        self.assertTrue(
            response.data["referral_code"].startswith("TM-")
        )

        entry.refresh_from_db()

        self.assertEqual(
            entry.status,
            WaitlistEntry.Status.VERIFIED,
        )

        self.assertEqual(
            entry.referral_code,
            response.data["referral_code"],
        )

    @patch(
        "apps.prelaunch.views.verify_otp",
        return_value=False,
    )
    def test_verify_invalid_code(self, mock_verify):
        response = self.client.post(
            self.verify_url,
            {
                "verification_id": "8a0c5eed-c728-4abb-9115-b6e7ff78bf83",
                "code": "000000",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    
    @patch(
        "apps.prelaunch.views.OTPRateLimiter.check",
        return_value=True,
    )
    def test_resend_existing_pending_entry(self, mock_limit):
        entry = WaitlistEntry.objects.create(
            phone="+2250700000096",
            commune="Cocody",
            consent_at=timezone.now(),
        )

        old_verification = OTPVerification.objects.create(
            waitlist_entry=entry,
            code_hash=make_password("123456"),
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        response = self.client.post(
            self.resend_url,
            {
                "phone": "0700000096",
                "verification_id": str(old_verification.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("verification_id", response.data)

        new_verification_id = response.data["verification_id"]

        self.assertNotEqual(
            str(old_verification.id),
            new_verification_id,
        )

        old_verification.refresh_from_db()

        self.assertLessEqual(
            old_verification.expires_at,
            timezone.now(),
        )

        self.assertEqual(
            OTPVerification.objects.filter(waitlist_entry=entry).count(),
            2,
        )
    
    def test_resend_unknown_number(self):
        response = self.client.post(
            self.resend_url,
            {
                "phone": "0700000088",
                "verification_id": str(uuid.uuid4()),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            OTPVerification.objects.count(),
            0,
        )

    @patch(
        "apps.prelaunch.views.OTPRateLimiter.check",
        return_value=True,
    )
    @patch(
        "apps.prelaunch.providers.development."
        "DevelopmentOTPProvider.send_code"
    )
    def test_resend_timeout_preserves_previous_otp(
        self,
        mock_send,
        mock_limit,
    ):
        from apps.prelaunch.providers.exceptions import (
            OTPDeliveryUncertain,
        )
        from django.contrib.auth.hashers import check_password

        entry = WaitlistEntry.objects.create(
            phone="+2250700000098",
            commune="Cocody",
            consent_at=timezone.now(),
        )

        old_verification = OTPVerification.objects.create(
            waitlist_entry=entry,
            code_hash=make_password("123456"),
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        mock_send.side_effect = OTPDeliveryUncertain(
            "Orange SMS delivery status uncertain"
        )

        response = self.client.post(
            self.resend_url,
            {
                "phone": "0700000098",
                "verification_id": str(old_verification.id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )

        old_verification.refresh_from_db()

        self.assertGreater(
            old_verification.expires_at,
            timezone.now(),
        )

        self.assertTrue(
            check_password(
                "123456",
                old_verification.code_hash,
            )
        )

        self.assertIsNone(old_verification.verified_at)
        mock_send.assert_called_once()
