from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from drf_spectacular.utils import extend_schema_field

from apps.accounts.utils import normalize_phone_number

from .models import (
    Pharmacy,
    PharmacyDutyPeriod,
    PharmacyOpeningHours,
)


class PharmacySerializer(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    is_open = serializers.SerializerMethodField()
    is_on_duty = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Pharmacy
        fields = [
            "id",
            "name",
            "phone_number",
            "address",
            "commune",
            "latitude",
            "longitude",
            "status",
            "is_active",
            "is_open",
            "is_on_duty",
            "is_available",
        ]

    @extend_schema_field(serializers.FloatField)
    def get_latitude(self, obj):
        if obj.location:
            return obj.location.y
        return None

    @extend_schema_field(serializers.FloatField)
    def get_longitude(self, obj):
        if obj.location:
            return obj.location.x
        return None

    @extend_schema_field(serializers.BooleanField)
    def get_is_open(self, obj):
        return obj.is_open_at()

    @extend_schema_field(serializers.BooleanField)
    def get_is_on_duty(self, obj):
        return obj.is_on_duty_at()

    @extend_schema_field(serializers.BooleanField)
    def get_is_available(self, obj):
        return obj.is_available_at()


class MyPharmacySerializer(PharmacySerializer):
    membership_role = serializers.SerializerMethodField()
    can_manage_opening_hours = serializers.SerializerMethodField()

    class Meta(PharmacySerializer.Meta):
        fields = [
            *PharmacySerializer.Meta.fields,
            "membership_role",
            "can_manage_opening_hours",
        ]

    def get_membership_role(self, obj):
        membership = self.context.get("membership")

        if membership is None:
            return None

        return membership.role

    def get_can_manage_opening_hours(self, obj):
        membership = self.context.get("membership")

        if membership is None:
            return False

        return membership.role in {
            "OWNER",
            "MANAGER",
        }


class PharmacyRegistrationCreateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=255,
    )

    phone_number = serializers.CharField(
        max_length=30,
    )

    address = serializers.CharField(
        max_length=255,
    )

    commune = serializers.CharField(
        max_length=100,
    )

    latitude = serializers.FloatField(
        min_value=-90,
        max_value=90,
    )

    longitude = serializers.FloatField(
        min_value=-180,
        max_value=180,
    )

    verification_document = serializers.FileField(
        required=True,
        allow_empty_file=False,
    )

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le nom de la pharmacie est obligatoire."
            )

        return value

    def validate_phone_number(self, value):
        try:
            return normalize_phone_number(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                "Numéro de téléphone invalide."
            ) from exc

    def validate_address(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "L'adresse de la pharmacie est obligatoire."
            )

        return value

    def validate_commune(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "La commune est obligatoire."
            )

        return value

    def validate_verification_document(self, value):
        max_size = 10 * 1024 * 1024

        if value.size > max_size:
            raise serializers.ValidationError(
                "Le justificatif ne doit pas dépasser 10 Mo."
            )

        return value


class PharmacyRegistrationSerializer(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    submitted_at = serializers.DateTimeField(
        source="created_at",
        read_only=True,
    )

    class Meta:
        model = Pharmacy
        fields = [
            "id",
            "name",
            "phone_number",
            "address",
            "commune",
            "latitude",
            "longitude",
            "status",
            "rejection_reason",
            "submitted_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.FloatField)
    def get_latitude(self, obj):
        if obj.location:
            return obj.location.y

        return None

    @extend_schema_field(serializers.FloatField)
    def get_longitude(self, obj):
        if obj.location:
            return obj.location.x

        return None


class NearbyPharmacyQuerySerializer(serializers.Serializer):
    latitude = serializers.FloatField(
        min_value=-90,
        max_value=90,
    )

    longitude = serializers.FloatField(
        min_value=-180,
        max_value=180,
    )

    radius_km = serializers.FloatField(
        min_value=0.1,
        max_value=50,
        default=10,
        required=False,
    )


class PharmacyOpeningHoursSerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(
        source="get_day_of_week_display",
        read_only=True,
    )

    class Meta:
        model = PharmacyOpeningHours
        fields = [
            "day_of_week",
            "day_name",
            "opens_at",
            "closes_at",
            "is_closed",
        ]

    def validate(self, attrs):
        is_closed = attrs.get("is_closed", False)
        opens_at = attrs.get("opens_at")
        closes_at = attrs.get("closes_at")

        if is_closed:
            attrs["opens_at"] = None
            attrs["closes_at"] = None
            return attrs

        if opens_at is None or closes_at is None:
            raise serializers.ValidationError(
                "Les heures d'ouverture et de fermeture "
                "sont obligatoires pour un jour ouvert."
            )

        if opens_at >= closes_at:
            raise serializers.ValidationError(
                "L'heure de fermeture doit être postérieure "
                "à l'heure d'ouverture."
            )

        return attrs


class PharmacyOpeningHoursUpdateSerializer(serializers.Serializer):
    opening_hours = PharmacyOpeningHoursSerializer(
        many=True,
    )

    def validate_opening_hours(self, value):
        days = [
            item["day_of_week"]
            for item in value
        ]

        if len(days) != len(set(days)):
            raise serializers.ValidationError(
                "Un même jour ne peut apparaître qu'une seule fois."
            )

        if set(days) != set(range(7)):
            raise serializers.ValidationError(
                "Les horaires des 7 jours de la semaine "
                "doivent être fournis."
            )

        return value


class PharmacyDutyPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PharmacyDutyPeriod
        fields = [
            "id",
            "starts_at",
            "ends_at",
        ]
        read_only_fields = fields