from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.cache import cache
from apps.accounts.models import PhoneVerification, User
from apps.accounts.services.otp import OTPService
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.tokens import RefreshToken

class RegistrationOTPAPITests(APITestCase):
    def setUp(self):
        self.request_otp_url = reverse(
            "accounts:register-request-otp"
        )
        self.verify_otp_url = reverse(
            "accounts:register-verify-otp"
        )

    def test_request_otp_creates_verification(self):
        response = self.client.post(
            self.request_otp_url,
            {
                "phone_number": "07 01 02 03 04",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertIn("verification_id", response.data)
        self.assertIn("expires_in", response.data)

        verification = PhoneVerification.objects.get(
            id=response.data["verification_id"])

        self.assertEqual(
            verification.phone_number,
            "+2250701020304",
        )

        self.assertEqual(
            verification.purpose,
            PhoneVerification.Purpose.REGISTRATION,
        )

    def test_request_otp_rejects_invalid_phone_number(self):
        response = self.client.post(
            self.request_otp_url,
            {
                "phone_number": "123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_request_otp_enforces_cooldown(self):
        payload = {
            "phone_number": "07 01 02 03 04",
        }

        first_response = self.client.post(
            self.request_otp_url,
            payload,
            format="json",
        )

        second_response = self.client.post(
            self.request_otp_url,
            payload,
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_verify_otp_accepts_valid_code(self):
        verification, code = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        response = self.client.post(
            self.verify_otp_url,
            {
                "verification_id": str(verification.id),
                "code": code,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertTrue(response.data["verified"])

        verification.refresh_from_db()

        self.assertIsNotNone(verification.verified_at)

    def test_verify_otp_rejects_invalid_code(self):
        verification, _ = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        response = self.client.post(
            self.verify_otp_url,
            {
                "verification_id": str(verification.id),
                "code": "000000",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_verify_otp_returns_404_for_unknown_verification(self):
        response = self.client.post(
            self.verify_otp_url,
            {
                "verification_id":
                    "550e8400-e29b-41d4-a716-446655440000",
                "code": "123456",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_verified_otp_cannot_be_verified_again(self):
        verification, code = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        payload = {
            "verification_id": str(verification.id),
            "code": code,
        }

        first_response = self.client.post(
            self.verify_otp_url,
            payload,
            format="json",
        )

        second_response = self.client.post(
            self.verify_otp_url,
            payload,
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

class RegistrationOTPThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()

        self.url = reverse(
            "accounts:register-request-otp"
        )

    def tearDown(self):
        cache.clear()

    def test_request_otp_is_throttled(self):
        payload = {
            "phone_number": "invalid",
        }

        responses = [
            self.client.post(
                self.url,
                payload,
                format="json",
            )
            for _ in range(6)
        ]

        for response in responses[:5]:
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
            )

        self.assertEqual(
            responses[5].status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

class RegistrationCompleteAPITests(APITestCase):
    def setUp(self):
        self.url = reverse(
            "accounts:register-complete"
        )

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

        response = self.client.post(
            self.url,
            {
                "verification_id": str(verification.id),
                "first_name": "Awa",
                "last_name": "Kone",
                "password": "TerimediTest2026!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        user = User.objects.get(
            phone_number="+2250701020304"
        )

        self.assertEqual(
            user.role,
            User.Role.PATIENT,
        )
        self.assertTrue(user.is_phone_verified)
        self.assertTrue(
            user.check_password("TerimediTest2026!")
        )

        verification.refresh_from_db()

        self.assertIsNotNone(
            verification.consumed_at
        )

    def test_complete_registration_rejects_unverified_otp(self):
        verification, _ = OTPService.create_verification(
            phone_number="07 01 02 03 04",
            purpose=PhoneVerification.Purpose.REGISTRATION,
        )

        response = self.client.post(
            self.url,
            {
                "verification_id": str(verification.id),
                "password": "TerimediTest2026!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertFalse(
            User.objects.filter(
                phone_number="+2250701020304"
            ).exists()
        )

    def test_complete_registration_rejects_unknown_verification(self):
        import uuid

        response = self.client.post(
            self.url,
            {
                "verification_id": str(uuid.uuid4()),
                "password": "TerimediTest2026!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_complete_registration_cannot_reuse_verification(self):
        verification = self.create_verified_registration()

        payload = {
            "verification_id": str(verification.id),
            "password": "TerimediTest2026!",
        }

        first_response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        second_response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            User.objects.filter(
                phone_number="+2250701020304"
            ).count(),
            1,
        )

    def test_complete_registration_rejects_weak_password(self):
        verification = self.create_verified_registration()

        response = self.client.post(
            self.url,
            {
                "verification_id": str(verification.id),
                "password": "12345678",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertFalse(
            User.objects.filter(
                phone_number="+2250701020304"
            ).exists()
        )

class LoginAPITests(APITestCase):
    def setUp(self):
        self.url = reverse("accounts:login")

        self.user = User.objects.create_user(
            phone_number="07 01 02 03 04",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

    def test_login_returns_access_and_refresh_tokens(self):
        response = self.client.post(
            self.url,
            {
                "phone_number": "07 01 02 03 04",
                "password": "TerimediTest2026!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_accepts_normalized_phone_number(self):
        response = self.client.post(
            self.url,
            {
                "phone_number": "+2250701020304",
                "password": "TerimediTest2026!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_login_rejects_wrong_password(self):
        response = self.client.post(
            self.url,
            {
                "phone_number": "07 01 02 03 04",
                "password": "WrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            response.data["detail"],
            "Invalid credentials.",
        )

    def test_login_rejects_unknown_phone_number(self):
        response = self.client.post(
            self.url,
            {
                "phone_number": "05 01 02 03 04",
                "password": "TerimediTest2026!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            response.data["detail"],
            "Invalid credentials.",
        )

    def test_login_rejects_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(
            self.url,
            {
                "phone_number": "07 01 02 03 04",
                "password": "TerimediTest2026!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_access_token_contains_correct_user_id(self):
        response = self.client.post(
            self.url,
            {
                "phone_number": "07 01 02 03 04",
                "password": "TerimediTest2026!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        access_token = AccessToken(
            response.data["access"]
        )

        self.assertEqual(
            access_token["user_id"],
            str(self.user.id),
        )

class MeAPITests(APITestCase):
    def setUp(self):
        self.url = reverse("accounts:me")

        self.user = User.objects.create_user(
            phone_number="07 01 02 03 04",
            password="TerimediTest2026!",
            first_name="Awa",
            last_name="Kone",
            role=User.Role.PATIENT,
            is_phone_verified=True, 
        )

    def test_me_returns_authenticated_user(self):
        refresh = RefreshToken.for_user(
            self.user
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=(
                f"Bearer {refresh.access_token}"
            )
        )

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            self.user.id,
        )
        self.assertEqual(
            response.data["phone_number"],
            "+2250701020304",
        )
        self.assertEqual(
            response.data["role"],
            User.Role.PATIENT,
        )

    def test_me_rejects_unauthenticated_request(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

class LogoutAPITests(APITestCase):
    def setUp(self):
        self.url = reverse("accounts:logout")

        self.user = User.objects.create_user(
            phone_number="07 01 02 03 04",
            password="TerimediTest2026!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )

    def test_logout_blacklists_refresh_token(self):
        refresh = RefreshToken.for_user(
            self.user
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=(
                f"Bearer {refresh.access_token}"
            )
        )

        response = self.client.post(
            self.url,
            {
                "refresh": str(refresh),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        response = self.client.post(
            reverse("accounts:token-refresh"),
            {
                "refresh": str(refresh),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )