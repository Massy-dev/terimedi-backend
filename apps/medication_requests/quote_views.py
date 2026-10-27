
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pharmacies.permissions import IsPharmacyStaff

from .models import MedicationRequest, PharmacyQuote
from .quote_serializers import (
    PharmacyQuoteCreateSerializer,
    PharmacyQuoteDecisionSerializer,
    PharmacyQuoteReadSerializer,
)
from .services.quotes import QuoteService
from .views import authorized_pharmacy_assignments


class PharmacyQuoteCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]

    @extend_schema(
        tags=["Pharmacy Quotes"],
        summary="Submit a pharmacy quote",
        request=PharmacyQuoteCreateSerializer,
        responses={
            201: PharmacyQuoteReadSerializer,
        },
    )
    def post(self, request, assignment_id):
        assignment = get_object_or_404(
            authorized_pharmacy_assignments(
                request.user
            ),
            id=assignment_id,
        )

        serializer = PharmacyQuoteCreateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            quote = QuoteService.create_quote(
                assignment_id=assignment.id,
                pharmacy_user=request.user,
                response=serializer.validated_data[
                    "response"
                ],
                items=serializer.validated_data[
                    "items"
                ],
                note=serializer.validated_data.get(
                    "note", ""
                ),
                available_items=serializer.validated_data.get(
                    "available_items", ""
                ),
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quote = (
            PharmacyQuote.objects
            .select_related(
                "assignment__pharmacy",
                "assignment__medication_request",
            )
            .prefetch_related("items")
            .get(pk=quote.pk)
        )

        return Response(
            PharmacyQuoteReadSerializer(quote).data,
            status=status.HTTP_201_CREATED,
        )


class PatientQuoteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Medication Quotes"],
        summary="Get patient's current quote",
        responses={
            200: PharmacyQuoteReadSerializer,
        },
    )
    def get(self, request, request_id):
        medication_request = get_object_or_404(
            MedicationRequest,
            id=request_id,
            patient=request.user,
            quote_requested=True,
        )

        quote = get_object_or_404(
            PharmacyQuote.objects
            .filter(
                assignment__medication_request=medication_request,
                status__in=[
                    PharmacyQuote.Status.PROPOSED,
                    PharmacyQuote.Status.ACCEPTED,
                ],
            )
            .select_related(
                "assignment__pharmacy",
                "assignment__medication_request",
            )
            .prefetch_related("items")
            .order_by("-proposed_at", "-id"),
        )

        return Response(
            PharmacyQuoteReadSerializer(quote).data,
            status=status.HTTP_200_OK,
        )


class PatientQuoteDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Medication Quotes"],
        summary="Accept or reject a pharmacy quote",
        request=PharmacyQuoteDecisionSerializer,
        responses={
            200: PharmacyQuoteReadSerializer,
        },
    )
    def post(self, request, request_id):
        get_object_or_404(
            MedicationRequest,
            id=request_id,
            patient=request.user,
            quote_requested=True,
        )

        serializer = PharmacyQuoteDecisionSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            quote = QuoteService.decide(
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

        quote = (
            PharmacyQuote.objects
            .select_related(
                "assignment__pharmacy",
                "assignment__medication_request",
            )
            .prefetch_related("items")
            .get(pk=quote.pk)
        )

        return Response(
            PharmacyQuoteReadSerializer(quote).data,
            status=status.HTTP_200_OK,
        )
