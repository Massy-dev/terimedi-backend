
import json

from django.contrib.gis.geos import Point
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import (
    MedicationRequest,
    MedicationRequestItem,
    PharmacyAssignment,
)


MAX_ITEMS = 20
MAX_ITEM_PHOTO_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


class MedicationRequestItemSerializer(serializers.ModelSerializer):
    has_photo = serializers.SerializerMethodField()

    class Meta:
        model = MedicationRequestItem
        fields = [
            "id",
            "name",
            "dosage",
            "quantity",
            "unit",
            "position",
            "has_photo",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField)
    def get_has_photo(self, obj):
        return bool(obj.photo)


class MedicationRequestItemInputSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )
    dosage = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )
    quantity = serializers.IntegerField(
        min_value=1,
        default=1,
    )
    unit = serializers.ChoiceField(
        choices=MedicationRequestItem.Unit.choices,
        default=MedicationRequestItem.Unit.BOX,
    )


class PrivateAttachmentRepresentationMixin:
    """Masque les chemins de stockage dans les réponses JSON."""

    has_prescription = serializers.SerializerMethodField()
    has_medication_photo = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField)
    def get_has_prescription(self, obj):
        return bool(obj.prescription)

    @extend_schema_field(serializers.BooleanField)
    def get_has_medication_photo(self, obj):
        return bool(obj.medication_photo)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["prescription"] = None
        data["medication_photo"] = None
        return data


class MedicationRequestCreateSerializer(
    PrivateAttachmentRepresentationMixin,
    serializers.ModelSerializer,
):
    latitude = serializers.FloatField(
        min_value=-90,
        max_value=90,
        write_only=True,
    )
    longitude = serializers.FloatField(
        min_value=-180,
        max_value=180,
        write_only=True,
    )
    items = MedicationRequestItemSerializer(
        many=True,
        read_only=True,
    )
    has_prescription = serializers.SerializerMethodField()
    has_medication_photo = serializers.SerializerMethodField()

    class Meta:
        model = MedicationRequest
        fields = [
            "id",
            "input_type",
            "text",
            "prescription",
            "medication_photo",
            "has_prescription",
            "has_medication_photo",
            "quantity",
            "items",
            "is_urgent",
            "quote_requested",
            "fulfillment_type",
            "latitude",
            "longitude",
            "delivery_address",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_at",
            "items",
            "has_prescription",
            "has_medication_photo",
        ]

    def _validate_photo(self, photo):
        from PIL import Image, UnidentifiedImageError

        if photo.size > MAX_ITEM_PHOTO_SIZE:
            raise serializers.ValidationError(
                "La photo ne doit pas dépasser 5 Mo."
            )

        try:
            photo.seek(0)

            with Image.open(photo) as image:
                image.verify()

            photo.seek(0)

            with Image.open(photo) as image:
                image_format = image.format

            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise serializers.ValidationError(
                    "Formats acceptés : JPEG, PNG et WEBP."
                )

        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            SyntaxError,
        ):
            raise serializers.ValidationError(
                "Le fichier fourni n'est pas une image valide."
            )
        finally:
            photo.seek(0)

    def validate(self, attrs):
        request = self.context.get("request")
        input_type = attrs.get("input_type")
        raw_items = None
        photos = {}

        if request is not None:
            raw_items = request.data.get("items")

        if raw_items is not None:
            if isinstance(raw_items, str):
                try:
                    raw_items = json.loads(raw_items)
                except (ValueError, TypeError):
                    raise serializers.ValidationError({
                        "items": (
                            "Le champ items doit contenir "
                            "un JSON valide."
                        )
                    })

            if not isinstance(raw_items, list):
                raise serializers.ValidationError({
                    "items": "Une liste de médicaments est attendue."
                })

            if not 1 <= len(raw_items) <= MAX_ITEMS:
                raise serializers.ValidationError({
                    "items": (
                        "La demande doit contenir entre "
                        f"1 et {MAX_ITEMS} médicaments."
                    )
                })

            item_serializer = MedicationRequestItemInputSerializer(
                data=raw_items,
                many=True,
            )
            item_serializer.is_valid(raise_exception=True)

            validated_items = list(
                item_serializer.validated_data
            )

            for index, item in enumerate(validated_items):
                photo_key = f"item_photo_{index}"

                photo = (
                    request.FILES.get(photo_key)
                    if request is not None
                    else None
                )

                if photo is not None:
                    self._validate_photo(photo)
                    photos[index] = photo

                if not item.get("name", "").strip() and not photo:
                    raise serializers.ValidationError({
                        "items": {
                            index: (
                                "Le nom ou une photo "
                                "est obligatoire."
                            )
                        }
                    })

            if request is not None:
                for key in request.FILES.keys():
                    if not key.startswith("item_photo_"):
                        continue

                    suffix = key.removeprefix("item_photo_")

                    if (
                        not suffix.isdecimal()
                        or str(int(suffix)) != suffix
                        or int(suffix) >= len(validated_items)
                    ):
                        raise serializers.ValidationError({
                            "items": f"Photo non associée : {key}"
                        })

            attrs["_items_data"] = validated_items
            attrs["_items_photos"] = photos

        elif request is not None:
            unexpected_photos = [
                key
                for key in request.FILES.keys()
                if key.startswith("item_photo_")
            ]

            if unexpected_photos:
                raise serializers.ValidationError({
                    "items": (
                        "Le champ items est obligatoire "
                        "lorsque des photos individuelles "
                        "sont envoyées."
                    )
                })

        has_items = bool(attrs.get("_items_data"))

        if (
            input_type == MedicationRequest.InputType.PRESCRIPTION
            and not attrs.get("prescription")
        ):
            raise serializers.ValidationError({
                "prescription": "Une ordonnance est obligatoire."
            })

        if (
            input_type == MedicationRequest.InputType.PHOTO
            and not attrs.get("medication_photo")
            and not has_items
        ):
            raise serializers.ValidationError({
                "medication_photo": (
                    "Une photo de médicament est obligatoire."
                )
            })

        if (
            input_type == MedicationRequest.InputType.TEXT
            and not attrs.get("text", "").strip()
            and not has_items
        ):
            raise serializers.ValidationError({
                "text": (
                    "Un texte ou une liste de médicaments "
                    "est obligatoire."
                )
            })

        fulfillment_type = attrs.get(
            "fulfillment_type",
            MedicationRequest.FulfillmentType.PICKUP,
        )

        if (
            fulfillment_type == MedicationRequest.FulfillmentType.DELIVERY
            and not attrs.get("delivery_address", "").strip()
        ):
            raise serializers.ValidationError({
                "delivery_address": (
                    "L'adresse de livraison est obligatoire."
                )
            })

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        latitude = validated_data.pop("latitude")
        longitude = validated_data.pop("longitude")
        items_data = validated_data.pop("_items_data", [])
        photos = validated_data.pop("_items_photos", {})

        validated_data["patient_location"] = Point(
            longitude,
            latitude,
            srid=4326,
        )

        medication_request = MedicationRequest.objects.create(
            **validated_data
        )

        for index, item_data in enumerate(items_data):
            MedicationRequestItem.objects.create(
                medication_request=medication_request,
                name=item_data.get("name", ""),
                dosage=item_data.get("dosage", ""),
                quantity=item_data.get("quantity", 1),
                unit=item_data.get(
                    "unit",
                    MedicationRequestItem.Unit.BOX,
                ),
                photo=photos.get(index),
                position=index,
            )

        return medication_request


class AvailableItemQuantityInputSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=0)


class PharmacyAssignmentResponseSerializer(serializers.Serializer):
    response = serializers.ChoiceField(
        choices=[
            PharmacyAssignment.Status.ACCEPTED,
            PharmacyAssignment.Status.PARTIAL,
            PharmacyAssignment.Status.REJECTED,
        ]
    )
    note = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    available_items = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    available_item_quantities = AvailableItemQuantityInputSerializer(
        many=True,
        required=False,
    )


class PharmacyAssignmentSerializer(serializers.ModelSerializer):
    request_id = serializers.UUIDField(
        source="medication_request.id",
        read_only=True,
    )
    input_type = serializers.CharField(
        source="medication_request.input_type",
        read_only=True,
    )
    text = serializers.CharField(
        source="medication_request.text",
        read_only=True,
    )
    quantity = serializers.IntegerField(
        source="medication_request.quantity",
        read_only=True,
        allow_null=True,
    )
    items = MedicationRequestItemSerializer(
        source="medication_request.items",
        many=True,
        read_only=True,
    )
    is_urgent = serializers.BooleanField(
        source="medication_request.is_urgent",
        read_only=True,
    )
    fulfillment_type = serializers.CharField(
        source="medication_request.fulfillment_type",
        read_only=True,
    )
    has_attachment = serializers.SerializerMethodField()
    attachment_type = serializers.SerializerMethodField()

    available_item_quantities = serializers.JSONField(
        read_only=True,
    )

    quote_requested = serializers.BooleanField(
        source="medication_request.quote_requested",
        read_only=True,
    )

    class Meta:
        model = PharmacyAssignment
        fields = [
            "id",
            "request_id",
            "input_type",
            "text",
            "quantity",
            "items",
            "is_urgent",
            "fulfillment_type",
            "has_attachment",
            "attachment_type",
            "status",
            "assigned_at",
            "expires_at",
            "available_item_quantities",
            "quote_requested",
        ]

    @extend_schema_field(serializers.BooleanField)
    def get_has_attachment(self, obj):
        medication_request = obj.medication_request

        if (
            medication_request.input_type
            == MedicationRequest.InputType.PRESCRIPTION
        ):
            return bool(medication_request.prescription)

        if (
            medication_request.input_type
            == MedicationRequest.InputType.PHOTO
        ):
            return bool(medication_request.medication_photo)

        return False

    @extend_schema_field(
        serializers.CharField(allow_null=True)
    )
    def get_attachment_type(self, obj):
        medication_request = obj.medication_request

        if (
            medication_request.input_type
            == MedicationRequest.InputType.PRESCRIPTION
            and medication_request.prescription
        ):
            return MedicationRequest.InputType.PRESCRIPTION

        if (
            medication_request.input_type
            == MedicationRequest.InputType.PHOTO
            and medication_request.medication_photo
        ):
            return MedicationRequest.InputType.PHOTO

        return None


class PartialDecisionSerializer(serializers.Serializer):
    class Decision:
        ACCEPT = "ACCEPT"
        REJECT = "REJECT"

    decision = serializers.ChoiceField(
        choices=[
            Decision.ACCEPT,
            Decision.REJECT,
        ]
    )


class PatientCurrentAssignmentSerializer(serializers.ModelSerializer):
    pharmacy = serializers.SerializerMethodField()

    available_item_quantities = serializers.JSONField(
        read_only=True,
    )

    class Meta:
        model = PharmacyAssignment
        fields = [
            "id",
            "status",
            "available_items",
            "available_item_quantities",
            "expires_at",
            "pharmacy",
        ]

    @extend_schema_field({
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "format": "uuid",
            },
            "name": {
                "type": "string",
            },
            "address": {
                "type": "string",
            },
            "commune": {
                "type": "string",
            },
        },
    })
    def get_pharmacy(self, obj):
        return {
            "id": obj.pharmacy.id,
            "name": obj.pharmacy.name,
            "address": obj.pharmacy.address,
            "commune": obj.pharmacy.commune,
        }


class MedicationRequestReadSerializer(
    PrivateAttachmentRepresentationMixin,
    serializers.ModelSerializer,
):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    current_assignment = serializers.SerializerMethodField()

    items = MedicationRequestItemSerializer(
        many=True,
        read_only=True,
    )

    has_prescription = serializers.SerializerMethodField()
    has_medication_photo = serializers.SerializerMethodField()

    class Meta:
        model = MedicationRequest
        fields = [
            "id",
            "input_type",
            "text",
            "prescription",
            "medication_photo",
            "has_prescription",
            "has_medication_photo",
            "quantity",
            "items",
            "is_urgent",
            "quote_requested",
            "fulfillment_type",
            "delivery_address",
            "latitude",
            "longitude",
            "status",
            "created_at",
            "current_assignment",
            "updated_at",
        ]
        read_only_fields = [
            "has_prescription",
            "has_medication_photo",
        ]

    @extend_schema_field(
        serializers.FloatField(allow_null=True)
    )
    def get_latitude(self, obj):
        if obj.patient_location:
            return obj.patient_location.y
        return None

    @extend_schema_field(
        serializers.FloatField(allow_null=True)
    )
    def get_longitude(self, obj):
        if obj.patient_location:
            return obj.patient_location.x
        return None

    @extend_schema_field(
        PatientCurrentAssignmentSerializer
    )
    def get_current_assignment(self, obj):
        assignment = (
            obj.assignments
            .filter(
                status__in=[
                    PharmacyAssignment.Status.PENDING,
                    PharmacyAssignment.Status.ACCEPTED,
                    PharmacyAssignment.Status.PARTIAL,
                ]
            )
            .select_related("pharmacy")
            .order_by("-assigned_at")
            .first()
        )

        if assignment is None:
            return None

        return PatientCurrentAssignmentSerializer(
            assignment
        ).data
