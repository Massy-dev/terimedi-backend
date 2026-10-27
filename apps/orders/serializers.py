from rest_framework import serializers

from .models import Order
from apps.medication_requests.models import PharmacyQuote
from apps.medication_requests.serializers import MedicationRequestItemSerializer
from apps.medication_requests.quote_serializers import PharmacyQuoteReadSerializer

class PickupCodeSerializer(serializers.Serializer):
    pickup_code = serializers.RegexField(
        regex=r"^\d{6}$",
    )

class PatientOrderSerializer(serializers.ModelSerializer):
    pharmacy_name = serializers.CharField(
        source="pharmacy.name",
        read_only=True,
    )

    class Meta:
        model = Order
        fields = [
            "id",
            "medication_request",
            "pharmacy",
            "pharmacy_name",
            "status",
            "pickup_code",
            "reservation_expires_at",
            "ready_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields

class PharmacyOrderSerializer(serializers.ModelSerializer):
    pharmacy_name = serializers.CharField(
        source="pharmacy.name",
        read_only=True,
    )

    class Meta:
        model = Order
        fields = [
            "id",
            "medication_request",
            "pharmacy",
            "pharmacy_name",
            "status",
            "reservation_expires_at",
            "ready_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields

class OrderDetailSerializer(PatientOrderSerializer):
    requested_medications = MedicationRequestItemSerializer(
        source="medication_request.items",
        many=True,
        read_only=True,
    )

    quote = serializers.SerializerMethodField()

    request_input_type = serializers.CharField(
        source="medication_request.input_type",
        read_only=True,
    )

    request_text = serializers.CharField(
        source="medication_request.text",
        read_only=True,
    )

    fulfillment_type = serializers.CharField(
        source="medication_request.fulfillment_type",
        read_only=True,
    )

    delivery_address = serializers.CharField(
        source="medication_request.delivery_address",
        read_only=True,
    )

    has_prescription = serializers.SerializerMethodField()
    has_medication_photo = serializers.SerializerMethodField()

    class Meta(PatientOrderSerializer.Meta):
        fields = PatientOrderSerializer.Meta.fields + [
            "request_input_type",
            "request_text",
            "requested_medications",
            "quote",
            "fulfillment_type",
            "delivery_address",
            "has_prescription",
            "has_medication_photo",
        ]
        read_only_fields = fields

    def get_quote(self, obj):
        try:
            quote = obj.assignment.quote
        except PharmacyQuote.DoesNotExist:
            return None

        return PharmacyQuoteReadSerializer(
            quote,
            context=self.context,
        ).data

    def get_has_prescription(self, obj):
        return bool(obj.medication_request.prescription)

    def get_has_medication_photo(self, obj):
        return bool(obj.medication_request.medication_photo)

class PharmacyOrderDetailSerializer(OrderDetailSerializer):
    class Meta(OrderDetailSerializer.Meta):
        fields = [
            field
            for field in OrderDetailSerializer.Meta.fields
            if field != "pickup_code"
        ]
        read_only_fields = fields