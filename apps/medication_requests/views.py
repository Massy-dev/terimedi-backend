
import mimetypes
from pathlib import Path

from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pharmacies.models import PharmacyMembership
from apps.pharmacies.permissions import IsPharmacyStaff

from .models import (
    MedicationRequest,
    MedicationRequestItem,
    PharmacyAssignment,
)
from .serializers import (
    MedicationRequestCreateSerializer,
    MedicationRequestReadSerializer,
    PartialDecisionSerializer,
    PharmacyAssignmentResponseSerializer,
    PharmacyAssignmentSerializer,
)
from .services.matching import MatchingService
from .services.partial import PartialDecisionService


ACTIVE_ASSIGNMENT_STATUSES = [
    PharmacyAssignment.Status.PENDING,
    PharmacyAssignment.Status.ACCEPTED,
    PharmacyAssignment.Status.PARTIAL,
]

PHARMACY_DOCUMENT_REQUEST_STATUSES = [
    MedicationRequest.Status.PENDING,
    MedicationRequest.Status.MATCHING,
    MedicationRequest.Status.PHARMACY_FOUND,
    MedicationRequest.Status.PARTIAL,
    MedicationRequest.Status.QUOTE_PENDING,
    MedicationRequest.Status.CONFIRMED,
    MedicationRequest.Status.READY,
]


def private_file_response(attachment):
    """
    Retourne un fichier privé sans exposer son URL de stockage.
    """
    if not attachment:
        return Response(
            {"detail": "Fichier introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        file_handle = attachment.open("rb")
    except (FileNotFoundError, OSError):
        return Response(
            {"detail": "Fichier introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )

    filename = Path(attachment.name).name
    content_type, _ = mimetypes.guess_type(filename)

    response = FileResponse(
        file_handle,
        content_type=(
            content_type or "application/octet-stream"
        ),
    )

    response["Content-Disposition"] = (
        f'inline; filename="{filename}"'
    )
    response["Cache-Control"] = (
        "private, no-store, max-age=0"
    )
    response["X-Content-Type-Options"] = "nosniff"

    return response


def latest_assignment_id(medication_request):
    """
    Identifie la dernière attribution enregistrée.
    """
    return (
        PharmacyAssignment.objects
        .filter(
            medication_request=medication_request
        )
        .order_by("-assigned_at", "-id")
        .values_list("id", flat=True)
        .first()
    )


def is_current_pharmacy_assignment(assignment):
    """
    Vérifie que l'attribution est courante et que la demande
    autorise encore l'accès aux documents.
    """
    medication_request = assignment.medication_request

    if (
        medication_request.status
        not in PHARMACY_DOCUMENT_REQUEST_STATUSES
    ):
        return False

    if assignment.status not in ACTIVE_ASSIGNMENT_STATUSES:
        return False

    return (
        assignment.id
        == latest_assignment_id(medication_request)
    )


def authorized_pharmacy_assignments(user):
    """
    Attributions accessibles aux membres actifs
    d'une pharmacie approuvée et active.
    """
    return (
        PharmacyAssignment.objects
        .filter(
            pharmacy__memberships__user=user,
            pharmacy__memberships__is_active=True,
            pharmacy__is_active=True,
            pharmacy__status="APPROVED",
        )
        .select_related(
            "medication_request",
            "pharmacy",
        )
        .distinct()
    )


def patient_legacy_attachment(medication_request):
    """
    Sélectionne le document historique selon le type.
    """
    if (
        medication_request.input_type
        == MedicationRequest.InputType.PRESCRIPTION
    ):
        return medication_request.prescription

    if (
        medication_request.input_type
        == MedicationRequest.InputType.PHOTO
    ):
        return medication_request.medication_photo

    return None


class MedicationRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [
        MultiPartParser,
        FormParser,
        JSONParser,
    ]

    @extend_schema(
        tags=["Medication Requests"],
        summary="List patient's medication requests",
        responses={
            200: MedicationRequestReadSerializer(many=True),
        },
    )
    def get(self, request):
        medication_requests = (
            MedicationRequest.objects
            .filter(
                patient=request.user
            )
            .prefetch_related(
                "assignments__pharmacy",
                "items",
            )
            .order_by("-created_at")
        )

        serializer = MedicationRequestReadSerializer(
            medication_requests,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Medication Requests"],
        summary="Create medication request",
        request=MedicationRequestCreateSerializer,
        responses={
            201: MedicationRequestCreateSerializer,
        },
    )
    def post(self, request):
        serializer = MedicationRequestCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            medication_request = serializer.save(
                patient=request.user,
            )

            MatchingService.assign_next_pharmacy(
                medication_request.id
            )

        medication_request.refresh_from_db()

        response_serializer = MedicationRequestCreateSerializer(
            medication_request
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class PharmacyPendingAssignmentsView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]

    @extend_schema(
        tags=["Pharmacy Requests"],
        summary="Get pending pharmacy assignments",
        responses={
            200: PharmacyAssignmentSerializer(many=True),
        },
    )
    def get(self, request):
        pharmacy_ids = (
            PharmacyMembership.objects
            .filter(
                user=request.user,
                is_active=True,
                pharmacy__is_active=True,
                pharmacy__status="APPROVED",
            )
            .values_list(
                "pharmacy_id",
                flat=True,
            )
        )

        assignments = (
            PharmacyAssignment.objects
            .filter(
                pharmacy_id__in=pharmacy_ids,
                status=PharmacyAssignment.Status.PENDING,
            )
            .select_related(
                "medication_request",
                "pharmacy",
            )
            .prefetch_related(
                "medication_request__items",
            )
            .order_by("assigned_at")
        )

        serializer = PharmacyAssignmentSerializer(
            assignments,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class PharmacyAssignmentAttachmentView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]

    @extend_schema(
        tags=["Pharmacy Requests"],
        summary="View medication request attachment",
        responses={
            200: {
                "type": "string",
                "format": "binary",
            },
        },
    )
    def get(self, request, assignment_id):
        assignment = get_object_or_404(
            authorized_pharmacy_assignments(
                request.user
            ),
            id=assignment_id,
        )

        if not is_current_pharmacy_assignment(
            assignment
        ):
            return Response(
                {"detail": "Fichier introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        attachment = patient_legacy_attachment(
            assignment.medication_request
        )

        return private_file_response(
            attachment
        )


class PatientMedicationRequestAttachmentView(APIView):
    """
    Consultation privée d'une ordonnance ou d'une photo
    historique par son patient propriétaire.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Medication Requests"],
        summary="View patient's medication request attachment",
        responses={
            200: {
                "type": "string",
                "format": "binary",
            },
        },
    )
    def get(self, request, request_id):
        medication_request = get_object_or_404(
            MedicationRequest,
            id=request_id,
            patient=request.user,
        )

        attachment = patient_legacy_attachment(
            medication_request
        )

        return private_file_response(
            attachment
        )


class MedicationRequestItemPhotoView(APIView):
    """
    Consultation d'une photo par son patient propriétaire
    ou par le personnel de la pharmacie actuellement attribuée.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Medication Requests"],
        summary="View a medication item photo",
        responses={
            200: {
                "type": "string",
                "format": "binary",
            },
        },
    )
    def get(self, request, request_id, item_id):
        medication_request = get_object_or_404(
            MedicationRequest,
            id=request_id,
        )

        is_owner = (
            medication_request.patient_id
            == request.user.id
        )

        if not is_owner:
            assignments = authorized_pharmacy_assignments(
                request.user
            ).filter(
                medication_request=medication_request,
                status__in=ACTIVE_ASSIGNMENT_STATUSES,
            )

            is_authorized = any(
                is_current_pharmacy_assignment(
                    assignment
                )
                for assignment in assignments
            )

            if not is_authorized:
                return Response(
                    {"detail": "Fichier introuvable."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        item = get_object_or_404(
            MedicationRequestItem,
            id=item_id,
            medication_request=medication_request,
        )

        return private_file_response(
            item.photo
        )


class PharmacyAssignmentRespondView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]

    @extend_schema(
        tags=["Pharmacy Requests"],
        summary="Respond to a medication request assignment",
        request=PharmacyAssignmentResponseSerializer,
        responses={
            200: PharmacyAssignmentSerializer,
        },
    )
    def post(self, request, assignment_id):
        serializer = PharmacyAssignmentResponseSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        assignment = get_object_or_404(
            PharmacyAssignment.objects.select_related(
                "pharmacy",
                "medication_request",
            ),
            id=assignment_id,
            pharmacy__memberships__user=request.user,
            pharmacy__memberships__is_active=True,
        )

        try:
            assignment = MatchingService.respond(
                assignment_id=assignment.id,
                response=serializer.validated_data[
                    "response"
                ],
                note=serializer.validated_data.get(
                    "note",
                    "",
                ),
                available_items=serializer.validated_data.get(
                    "available_items",
                    "",
                ),
                available_item_quantities=(
                    serializer.validated_data.get(
                        "available_item_quantities"
                    )
                ),
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PharmacyAssignmentSerializer(
                assignment
            ).data,
            status=status.HTTP_200_OK,
        )


class PartialDecisionView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        tags=["Medication Requests"],
        summary="Accept or reject partial pharmacy availability",
        request=PartialDecisionSerializer,
        responses={
            200: MedicationRequestCreateSerializer,
        },
    )
    def post(self, request, request_id):
        serializer = PartialDecisionSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            medication_request = PartialDecisionService.decide(
                medication_request_id=request_id,
                patient=request.user,
                decision=serializer.validated_data[
                    "decision"
                ],
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            MedicationRequestCreateSerializer(
                medication_request
            ).data,
            status=status.HTTP_200_OK,
        )


class PatientMedicationRequestDetailView(
    generics.RetrieveAPIView
):
    serializer_class = MedicationRequestReadSerializer
    permission_classes = [
        IsAuthenticated,
    ]

    def get_queryset(self):
        return (
            MedicationRequest.objects
            .filter(
                patient=self.request.user
            )
            .prefetch_related(
                "assignments__pharmacy",
                "items",
            )
            .order_by("-created_at")
        )
