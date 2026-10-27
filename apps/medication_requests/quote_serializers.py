from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import PharmacyAssignment, PharmacyQuote, PharmacyQuoteItem


class PharmacyQuoteCreateSerializer(serializers.Serializer):
    response = serializers.ChoiceField(
        choices=[
            PharmacyAssignment.Status.ACCEPTED,
            PharmacyAssignment.Status.PARTIAL,
        ],
    )
    items = serializers.JSONField()
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )
    available_items = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    def validate_items(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Une liste de médicaments est attendue."
            )

        if not 1 <= len(value) <= 20:
            raise serializers.ValidationError(
                "Le devis doit contenir entre 1 et 20 éléments."
            )

        return value


class PharmacyQuoteItemSerializer(serializers.ModelSerializer):
    item_id = serializers.UUIDField(
        source="medication_item_id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = PharmacyQuoteItem
        fields = [
            "id",
            "item_id",
            "name",
            "dosage",
            "unit",
            "quantity",
            "unit_price",
            "subtotal",
            "position",
        ]
        read_only_fields = fields


class PharmacyQuoteReadSerializer(serializers.ModelSerializer):
    assignment_id = serializers.UUIDField(
        read_only=True,
    )
    request_id = serializers.UUIDField(
        source="assignment.medication_request_id",
        read_only=True,
    )
    pharmacy_id = serializers.UUIDField(
        source="assignment.pharmacy_id",
        read_only=True,
    )
    pharmacy_name = serializers.CharField(
        source="assignment.pharmacy.name",
        read_only=True,
    )
    availability_status = serializers.CharField(
        source="assignment.status",
        read_only=True,
    )
    available_item_quantities = serializers.JSONField(
        source="assignment.available_item_quantities",
        read_only=True,
    )
    items = PharmacyQuoteItemSerializer(
        many=True,
        read_only=True,
    )
    currency = serializers.SerializerMethodField()

    class Meta:
        model = PharmacyQuote
        fields = [
            "id",
            "assignment_id",
            "request_id",
            "pharmacy_id",
            "pharmacy_name",
            "availability_status",
            "available_item_quantities",
            "status",
            "items",
            "total_amount",
            "currency",
            "note",
            "proposed_at",
            "decided_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField)
    def get_currency(self, obj):
        return "XOF"


class PharmacyQuoteDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=["ACCEPT", "REJECT"],
    )
