
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.prelaunch.models import WaitlistEntry, OTPVerification
from apps.prelaunch.services.otp import create_otp
from django.contrib.auth.hashers import make_password
from datetime import timedelta
from apps.prelaunch.services.otp import verify_otp

@override_settings(PRELAUNCH_OTP_PROVIDER="development", DEBUG=True)
class OTPConcurrencyTests(TransactionTestCase):

    def setUp(self):
        self.entry = WaitlistEntry.objects.create(
            phone="+2250700000088",
            first_name="Concurrency",
            commune="Cocody",
            consent_at=timezone.now(),
        )

    def test_concurrent_requests_leave_one_active_otp(self):
        first_send_started = threading.Event()
        release_first_send = threading.Event()
        send_count = 0
        send_lock = threading.Lock()

        def fake_send(phone, code):
            nonlocal send_count

            with send_lock:
                send_count += 1
                current_send = send_count

            if current_send == 1:
                first_send_started.set()
                if not release_first_send.wait(timeout=10):
                    raise TimeoutError("First send was not released")

        def request_otp():
            close_old_connections()
            try:
                return create_otp(self.entry)
            finally:
                connections.close_all()

        with patch(
            "apps.prelaunch.providers.development."
            "DevelopmentOTPProvider.send_code",
            side_effect=fake_send,
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(request_otp)

                try:
                    self.assertTrue(
                        first_send_started.wait(timeout=5),
                        "First request did not reach the SMS provider",
                    )

                    second = executor.submit(request_otp)

                    # Give the second request time to reach the DB lock.
                    time.sleep(0.3)

                finally:
                    release_first_send.set()

                first.result(timeout=15)
                second.result(timeout=15)

        active_otps = OTPVerification.objects.filter(
            waitlist_entry=self.entry,
            verified_at__isnull=True,
            expires_at__gt=timezone.now(),
        )

        self.assertEqual(active_otps.count(), 1)
        self.assertEqual(send_count, 2)

    def test_concurrent_verifications_only_one_succeeds(self):
        first_otp = OTPVerification.objects.create(
            waitlist_entry=self.entry,
            code_hash=make_password("123456"),
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        second_otp = OTPVerification.objects.create(
            waitlist_entry=self.entry,
            code_hash=make_password("654321"),
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        start_event = threading.Event()

        def verify_in_thread(verification_id, code):
            close_old_connections()
            try:
                if not start_event.wait(timeout=10):
                    raise TimeoutError("Verification start timed out")

                return verify_otp(verification_id, code)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                verify_in_thread,
                first_otp.id,
                "123456",
            )

            second = executor.submit(
                verify_in_thread,
                second_otp.id,
                "654321",
            )

            # Déclencher les deux vérifications.
            start_event.set()

            results = [
                first.result(timeout=15),
                second.result(timeout=15),
            ]

        # Une seule vérification doit réussir.
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 1)

        self.entry.refresh_from_db()

        self.assertEqual(
            self.entry.status,
            WaitlistEntry.Status.VERIFIED,
        )

        # Vérifier qu'un seul OTP a été consommé.
        self.assertEqual(
            OTPVerification.objects.filter(
                waitlist_entry=self.entry,
                verified_at__isnull=False,
            ).count(),
            1,
        )
