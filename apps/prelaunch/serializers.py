import phonenumbers

from rest_framework import serializers
from django.db import IntegrityError, transaction
from django.utils import timezone


from apps.prelaunch.models import PharmacyPreRegistration

class WaitlistRegistrationSerializer(serializers.Serializer):
    first_name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    phone = serializers.CharField(
        max_length=30,
    )

    commune = serializers.CharField(
        max_length=100,
    )

    consent = serializers.BooleanField()

    referral_code = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
    )

    def validate_phone(self, value):
        try:
            parsed = phonenumbers.parse(value, "CI")
        except phonenumbers.NumberParseException:
            raise serializers.ValidationError(
                "Numéro de téléphone invalide."
            )

        if not phonenumbers.is_valid_number(parsed):
            raise serializers.ValidationError(
                "Numéro de téléphone invalide."
            )

        if parsed.country_code != 225:
            raise serializers.ValidationError(
                "Seuls les numéros ivoiriens sont acceptés."
            )

        return phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.E164,
        )

    def validate_consent(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "Le consentement est obligatoire."
            )
        return value


class OTPVerifySerializer(serializers.Serializer):
    verification_id = serializers.UUIDField()

    code = serializers.RegexField(
        regex=r"^[0-9]{6}$",
        max_length=6,
        min_length=6,
    )


class OTPResendSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=30)
    verification_id = serializers.UUIDField(required=True)

    def validate_phone(self, value):
        return WaitlistRegistrationSerializer().validate_phone(value)


class WaitlistRegistrationResponseSerializer(serializers.Serializer):
    verification_id = serializers.UUIDField()
    message = serializers.CharField()
    expires_in = serializers.IntegerField()


#------------------------- PHARMACIE -------------------------------


class PharmacyPreRegistrationSerializer(serializers.ModelSerializer):
    consent = serializers.BooleanField(
        write_only=True,
        required=True,
    )

    class Meta:
        model = PharmacyPreRegistration
        fields = [
            "id",
            "pharmacy_name",
            "commune",
            "address",
            "contact_name",
            "phone",
            "email",
            "is_on_duty",
            "consent",
        ]

        read_only_fields = ["id"]

        extra_kwargs = {
            "phone": {
                "validators": [],
            },
            "pharmacy_name": {
                "trim_whitespace": True,
            },
            "commune": {
                "trim_whitespace": True,
            },
            "address": {
                "trim_whitespace": True,
            },
            "contact_name": {
                "trim_whitespace": True,
            },
        }

    def validate_phone(self, value):
        try:
            parsed = phonenumbers.parse(value, "CI")
        except phonenumbers.NumberParseException:
            raise serializers.ValidationError(
                "Numéro de téléphone invalide."
            )

        if not phonenumbers.is_valid_number(parsed):
            raise serializers.ValidationError(
                "Numéro de téléphone invalide."
            )

        if parsed.country_code != 225:
            raise serializers.ValidationError(
                "Le numéro doit être ivoirien."
            )

        return phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.E164,
        )

    def validate_consent(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "Le consentement est obligatoire."
            )
        return value

    def validate(self, attrs):
        for field in [
            "pharmacy_name",
            "commune",
            "address",
            "contact_name",
        ]:
            if not attrs.get(field, "").strip():
                raise serializers.ValidationError({
                    field: "Ce champ est obligatoire."
                })

        return attrs

    def create(self, validated_data):
        validated_data.pop("consent", None)

        validated_data["consent_at"] = timezone.now()

        return PharmacyPreRegistration.objects.create(
            **validated_data
        )