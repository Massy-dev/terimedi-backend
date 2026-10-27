
from rest_framework import serializers

from apps.prelaunch.models import PharmacyPreRegistration,WaitlistEntry
from .models import PharmacyStatusAudit

class PharmacyAdminSerializer(serializers.ModelSerializer):
    """
    Lecture des candidatures pharmaceutiques.
    Réservé aux endpoints d'administration.
    """

    class Meta:
        model = PharmacyPreRegistration

        fields = (
            "id",
            "pharmacy_name",
            "commune",
            "address",
            "contact_name",
            "phone",
            "email",
            "is_on_duty",
            "status",
            "consent_at",
            "created_at",
            "updated_at",
        )

        read_only_fields = fields


class PharmacyStatusUpdateSerializer(serializers.Serializer):
    """
    Validation stricte du nouveau statut.
    """

    status = serializers.ChoiceField(
        choices=PharmacyPreRegistration.Status.choices,
        required=True,
    )


class PharmacyStatusAuditSerializer(serializers.ModelSerializer):
    actor_id = serializers.UUIDField(read_only=True)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = PharmacyStatusAudit

        fields = (
            "id",
            "pharmacy",
            "actor_id",
            "actor_name",
            "old_status",
            "new_status",
            "created_at",
        )

        read_only_fields = fields

    def get_actor_name(self, obj):
        actor = obj.actor

        if actor is None:
            return "Administrateur inconnu"

        full_name = " ".join(
            part.strip()
            for part in [
                actor.first_name or "",
                actor.last_name or "",
            ]
            if part and part.strip()
        )

        if full_name:
            return full_name

        return "Administrateur TeriMedi"


class PatientAdminSerializer(serializers.ModelSerializer):
    """
    Lecture des préinscriptions patients.
    Réservée aux administrateurs TeriMedi.

    Ne retourne aucune donnée technique OTP.
    """

    referred_by_phone = serializers.CharField(
        source="referred_by.phone",
        read_only=True,
        allow_null=True,
    )

    referrals_count = serializers.IntegerField(
        read_only=True,
    )

    class Meta:
        model = WaitlistEntry

        fields = (
            "id",
            "phone",
            "first_name",
            "commune",
            "status",
            "phone_verified_at",
            "referral_code",
            "referred_by",
            "referred_by_phone",
            "referrals_count",
            "consent_at",
            "created_at",
            "updated_at",
        )

        read_only_fields = fields



class AdminActivitySerializer(PharmacyStatusAuditSerializer):
    """
    Activité administrative globale.

    Étend le sérialiseur d'audit existant
    avec les informations de la pharmacie.
    """

    pharmacy_name = serializers.CharField(
        source="pharmacy.pharmacy_name",
        read_only=True,
    )

    pharmacy_commune = serializers.CharField(
        source="pharmacy.commune",
        read_only=True,
    )

    class Meta(PharmacyStatusAuditSerializer.Meta):
        fields = (
            "id",
            "pharmacy",
            "pharmacy_name",
            "pharmacy_commune",
            "actor_id",
            "actor_name",
            "old_status",
            "new_status",
            "created_at",
        )

        read_only_fields = fields
