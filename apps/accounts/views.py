from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.accounts.throttles import OTPRequestThrottle
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts.models import PhoneVerification, User
from apps.accounts.serializers import *
from apps.accounts.services.registration import RegistrationService
from apps.accounts.services.otp import OTPService
from apps.accounts.services.sms import ConsoleSMSBackend


class RegisterCompleteView(APIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = RegisterCompleteSerializer

    @extend_schema(
        tags=["Authentication"],
        summary="Complete patient registration",
        description=(
            "Create a patient account after successful "
            "phone number verification."
        ),
        request=RegisterCompleteSerializer,
        responses={
            201: RegisterCompleteResponseSerializer,
            400: ErrorResponseSerializer,
        },
    )
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            user = RegistrationService.complete_registration(
                verification_id=serializer.validated_data[
                    "verification_id"
                ],
                password=serializer.validated_data[
                    "password"
                ],
                first_name=serializer.validated_data.get(
                    "first_name",
                    "",
                ),
                last_name=serializer.validated_data.get(
                    "last_name",
                    "",
                ),
            )
        except DjangoValidationError as exc:
            return Response(
                {
                    "detail": exc.messages[0],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "id": user.id,
                "phone_number": user.phone_number,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "is_phone_verified":
                    user.is_phone_verified,
            },
            status=status.HTTP_201_CREATED,
        )

class RegisterRequestOTPView(APIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = RegisterRequestOTPSerializer
    throttle_classes = [OTPRequestThrottle]

    @extend_schema(
        tags=["Authentication"],
        summary="Request registration OTP",
        description=(
            "Generate a verification code for a patient "
            "registration phone number."
        ),
        request=RegisterRequestOTPSerializer,
        responses={
            201: RegisterRequestOTPResponseSerializer,
            400: ErrorResponseSerializer,
            429: ErrorResponseSerializer,
        },
    )
    def post(self, request):
        serializer = RegisterRequestOTPSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]

        try:
            verification, code = OTPService.create_verification(
                phone_number=phone_number,
                purpose=PhoneVerification.Purpose.REGISTRATION,
            )
        except DjangoValidationError as exc:
            return Response(
                {
                    "detail": exc.messages[0],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ConsoleSMSBackend().send_otp(
            phone_number=verification.phone_number,
            code=code,
        )

        return Response(
            {
                "verification_id": verification.id,
                "expires_in": settings.OTP_EXPIRY_MINUTES * 60,
            },
            status=status.HTTP_201_CREATED,
        )


class RegisterVerifyOTPView(APIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = RegisterVerifyOTPSerializer

    @extend_schema(
        tags=["Authentication"],
        summary="Verify registration OTP",
        description=(
            "Verify the OTP associated with a registration "
            "verification challenge."
        ),
        request=RegisterVerifyOTPSerializer,
        responses={
            200: RegisterVerifyOTPResponseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def post(self, request):
        serializer = RegisterVerifyOTPSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        verification_id = serializer.validated_data[
            "verification_id"
        ]
        code = serializer.validated_data["code"]

        try:
            verification = PhoneVerification.objects.get(
                id=verification_id,
                purpose=PhoneVerification.Purpose.REGISTRATION,
            )
        except PhoneVerification.DoesNotExist:
            return Response(
                {
                    "detail": "Verification not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            OTPService.verify(
                verification=verification,
                code=code,
            )
        except DjangoValidationError as exc:
            return Response(
                {
                    "detail": exc.messages[0],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "verification_id": verification.id,
                "verified": True,
            },
            status=status.HTTP_200_OK,
        )

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Authentication"],
        summary="Get current user",
        description="Return the authenticated user's profile.",
        responses={
            200: MeResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def get(self, request):
        user = request.user

        return Response(
            {
                "id": user.id,
                "phone_number": user.phone_number,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "is_phone_verified": user.is_phone_verified,
            },
            status=status.HTTP_200_OK,
        )

class LoginView(APIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = LoginSerializer

    @extend_schema(
        tags=["Authentication"],
        summary="Login",
        description=(
            "Authenticate a user with a phone number and password "
            "and return JWT access and refresh tokens."
        ),
        request=LoginSerializer,
        responses={
            200: LoginResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data[
            "phone_number"
        ]
        password = serializer.validated_data[
            "password"
        ]

        try:
            user = User.objects.get(
                phone_number=phone_number
            )
        except User.DoesNotExist:
            return Response(
                {
                    "detail": "Invalid credentials.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {
                    "detail": "Invalid credentials.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return Response(
                {
                    "detail": "Invalid credentials.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )

    class MeView(APIView):
        permission_classes = [IsAuthenticated]

        @extend_schema(
            tags=["Authentication"],
            summary="Get current user",
            description=(
                "Return the authenticated user's profile."
            ),
            responses={
                200: MeResponseSerializer,
                401: ErrorResponseSerializer,
            },
        )
        def get(self, request):
            user = request.user

            return Response(
                {
                    "id": user.id,
                    "phone_number": user.phone_number,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "is_phone_verified":
                        user.is_phone_verified,
                },
                status=status.HTTP_200_OK,
            )

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    @extend_schema(
        tags=["Authentication"],
        summary="Logout",
        description=(
            "Blacklist the provided refresh token."
        ),
        request=LogoutSerializer,
        responses={
            204: None,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            refresh = RefreshToken(
                serializer.validated_data["refresh"]
            )
            refresh.blacklist()
        except TokenError:
            return Response(
                {
                    "detail": "Invalid refresh token.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )