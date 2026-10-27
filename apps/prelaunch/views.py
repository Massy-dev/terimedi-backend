from django.db import IntegrityError, transaction
from django.utils import timezone
import uuid
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.prelaunch.models import OTPVerification
from apps.prelaunch.services.referral import assign_referral_code
from django.core.exceptions import ObjectDoesNotExist
from apps.prelaunch.serializers import OTPVerifySerializer
from apps.prelaunch.services.otp import verify_otp
from apps.prelaunch.serializers import OTPResendSerializer
from apps.prelaunch.models import WaitlistEntry
from apps.prelaunch.serializers import WaitlistRegistrationSerializer
from apps.prelaunch.services.otp import create_otp
from apps.prelaunch.services.rate_limit import (
    OTPRateLimiter,
    RateLimitExceeded,
)
from apps.prelaunch.models import PharmacyPreRegistration
from apps.prelaunch.serializers import PharmacyPreRegistrationSerializer
from rest_framework.throttling import ScopedRateThrottle

class WaitlistRegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = WaitlistRegistrationSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        phone = data["phone"]

        ip_address = request.META.get(
            "REMOTE_ADDR",
            "unknown",
        )

        try:
            OTPRateLimiter.check(phone, ip_address)
        except RateLimitExceeded as exc:
            return Response(
                {
                    "detail": "Veuillez patienter avant de demander un nouveau code.",
                    "retry_after": exc.retry_after,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        referral_code = data.get("referral_code", "").strip().upper()
        referrer = None

        if referral_code:
            referrer = WaitlistEntry.objects.filter(
                referral_code=referral_code,
                status=WaitlistEntry.Status.VERIFIED,
            ).first()
            
        with transaction.atomic():
            entry, created = WaitlistEntry.objects.get_or_create(
                phone=phone,
                defaults={
                    "first_name": data.get("first_name", ""),
                    "commune": data["commune"],
                    "consent_at": timezone.now(),
                    "referred_by": referrer,
                },
            )

            if entry.status == WaitlistEntry.Status.VERIFIED:
              return Response(
                  {
                    "verification_id": str(uuid.uuid4()),
                    "message": "Un code de confirmation a été envoyé sur votre whatsApp.",
                    "expires_in": 300,
                  },
                  status=status.HTTP_200_OK,
              )

            verification = create_otp(entry)

        
        delivery_uncertain = getattr(
            verification,
            "delivery_uncertain",
            False,
        )

        if delivery_uncertain:
            return Response(
                {
                    "verification_id": str(verification.id),
                    "message": (
                        "La confirmation de l'envoi du SMS "
                        "est indisponible. Si vous recevez "
                        "un code, vous pouvez le saisir."
                    ),
                    "expires_in": 300,
                    "delivery_status": "UNCERTAIN",
                },
                status=status.HTTP_202_ACCEPTED,
            )

        return Response(
            {
                "verification_id": str(verification.id),
                "message": (
                    "Votre demande d'envoi de code SMS "
                    "a été acceptée."
                ),
                "expires_in": 300,
                "delivery_status": "ACCEPTED",
            },
            status=status.HTTP_200_OK,
        )



class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        try:
            is_valid = verify_otp(
                verification_id=data["verification_id"],
                code=data["code"],
            )
        except ObjectDoesNotExist:
            is_valid = False

        if not is_valid:
            return Response(
                {
                    "detail": "Code invalide ou expiré.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        verification = OTPVerification.objects.select_related(
            "waitlist_entry"
        ).get(
            id=data["verification_id"]
        )

        entry = verification.waitlist_entry
        referral_code = assign_referral_code(entry)

        return Response(
            {
              "message": "Inscription confirmée avec succès.",
              "status": "VERIFIED",
              "referral_code": referral_code,
            },
            status=status.HTTP_200_OK,
        )


class OTPResendView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = OTPResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        ip_address = request.META.get("REMOTE_ADDR", "unknown")

        verification_id = serializer.validated_data["verification_id"]

        # Le renvoi nécessite une session OTP existante.
        if not verification_id:
            return Response(
                {"detail": "Session de vérification manquante."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            previous_verification = OTPVerification.objects.select_related(
                "waitlist_entry"
            ).get(id=verification_id)
        except (OTPVerification.DoesNotExist, ValueError, TypeError):
            return Response(
                {"detail": "Session de vérification invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entry = previous_verification.waitlist_entry

        if (
            entry.phone != phone
            or entry.status != WaitlistEntry.Status.PENDING
        ):
            return Response(
                {"detail": "Session de vérification invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            OTPRateLimiter.check(phone, ip_address)
        except RateLimitExceeded as exc:
            return Response(
                {
                    "detail": "Veuillez patienter avant de demander un nouveau code.",
                    "retry_after": exc.retry_after,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        with transaction.atomic():
            verification = create_otp(entry)

        
        delivery_uncertain = getattr(
            verification,
            "delivery_uncertain",
            False,
        )

        if delivery_uncertain:
            return Response(
                {
                    "verification_id": str(verification.id),
                    "message": (
                        "La confirmation de l'envoi du SMS "
                        "est indisponible. Si vous recevez "
                        "un code, vous pouvez le saisir. "
                        "Votre ancien code reste utilisable "
                        "jusqu'à son expiration."
                    ),
                    "expires_in": 300,
                    "delivery_status": "UNCERTAIN",
                },
                status=status.HTTP_202_ACCEPTED,
            )

        return Response(
            {
                "verification_id": str(verification.id),
                "message": (
                    "Votre demande de renvoi du code SMS "
                    "a été acceptée."
                ),
                "expires_in": 300,
                "delivery_status": "ACCEPTED",
            },
            status=status.HTTP_200_OK,
        )


#------------------------------ pharmacie -------------------------

class PharmacyPreRegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "pharmacy_prelaunch"

    SUCCESS_MESSAGE = (
        "Votre demande a bien été reçue. "
        "Si une candidature existe déjà avec ces coordonnées, "
        "notre équipe en tiendra compte."
    )

    def post(self, request):
        serializer = PharmacyPreRegistrationSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            # Ne pas révéler si le numéro existe déjà.
            pass

        return Response(
            {
                "message": self.SUCCESS_MESSAGE,
            },
            status=status.HTTP_200_OK,
        )