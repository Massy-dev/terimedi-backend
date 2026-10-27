from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.utils import normalize_phone_number

from django.contrib.auth.password_validation import validate_password

class RegisterRequestOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=30)

    def validate_phone_number(self, value):
        try:
            return normalize_phone_number(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                "Invalid phone number."
            ) from exc


class RegisterVerifyOTPSerializer(serializers.Serializer):
    verification_id = serializers.UUIDField()
    code = serializers.CharField(
        min_length=6,
        max_length=6,
    )

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError(
                "Verification code must contain only digits."
            )

        return value


class RegisterRequestOTPResponseSerializer(serializers.Serializer):
    verification_id = serializers.UUIDField()
    expires_in = serializers.IntegerField()


class RegisterVerifyOTPResponseSerializer(serializers.Serializer):
    verification_id = serializers.UUIDField()
    verified = serializers.BooleanField()


class ErrorResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class RegisterCompleteSerializer(serializers.Serializer):
    verification_id = serializers.UUIDField()

    first_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )

    last_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )

    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    def validate_password(self, value):
        validate_password(value)
        return value


class RegisterCompleteResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    phone_number = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.CharField()
    is_phone_verified = serializers.BooleanField()


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=30)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate_phone_number(self, value):
        try:
            return normalize_phone_number(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                "Invalid phone number."
            ) from exc


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class MeResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    phone_number = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.CharField()
    is_phone_verified = serializers.BooleanField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        write_only=True
    )