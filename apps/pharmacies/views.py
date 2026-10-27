from django.db import transaction

from drf_spectacular.utils import extend_schema

from rest_framework import status
from rest_framework.parsers import (
    FormParser,
    MultiPartParser,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    PharmacyDutyPeriod,
    PharmacyMembership,
    PharmacyOpeningHours,
)
from .permissions import IsPharmacyStaff
from .serializers import (
    MyPharmacySerializer,
    NearbyPharmacyQuerySerializer,
    PharmacyDutyPeriodSerializer,
    PharmacyOpeningHoursSerializer,
    PharmacyOpeningHoursUpdateSerializer,
    PharmacyRegistrationCreateSerializer,
    PharmacyRegistrationSerializer,
    PharmacySerializer,
)
from .services import (
    PharmacyRegistrationAlreadyExists,
    PharmacyRegistrationService,
    PharmacySearchService,
)


def get_active_pharmacy_membership(user):
    return (
        PharmacyMembership.objects
        .select_related("pharmacy")
        .filter(
            user=user,
            is_active=True,
            pharmacy__is_active=True,
            pharmacy__status="APPROVED",
        )
        .first()
    )


class PharmacyRegistrationView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    @extend_schema(
        tags=["Pharmacy Registration"],
        summary="Register a pharmacy",
        description=(
            "Submit a new pharmacy registration request. "
            "The authenticated user becomes the owner of "
            "the pharmacy and the registration starts with "
            "the PENDING status."
        ),
        request=PharmacyRegistrationCreateSerializer,
        responses={
            201: PharmacyRegistrationSerializer,
            400: PharmacyRegistrationSerializer,
        },
    )
    def post(self, request):
        serializer = PharmacyRegistrationCreateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            pharmacy = PharmacyRegistrationService.register(
                user=request.user,
                validated_data=serializer.validated_data,
            )
        except PharmacyRegistrationAlreadyExists as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = PharmacyRegistrationSerializer(
            pharmacy,
            context={
                "request": request,
            },
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class PharmacyRegistrationStatusView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        tags=["Pharmacy Registration"],
        summary="Get pharmacy registration status",
        description=(
            "Return the pharmacy registration associated "
            "with the authenticated user, including pending "
            "and rejected registrations."
        ),
        responses={
            200: PharmacyRegistrationSerializer,
        },
    )
    def get(self, request):
        pharmacy = (
            PharmacyRegistrationService
            .get_registration_for_user(request.user)
        )

        if pharmacy is None:
            return Response(
                {
                    "detail": (
                        "Aucune demande d'inscription pharmacie "
                        "n'est associée à ce compte."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PharmacyRegistrationSerializer(
            pharmacy,
            context={
                "request": request,
            },
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class NearbyPharmacyView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Pharmacies"],
        summary="Find nearby pharmacies",
        parameters=[NearbyPharmacyQuerySerializer],
        responses={
            200: PharmacySerializer(many=True),
        },
    )
    def get(self, request):
        query = NearbyPharmacyQuerySerializer(
            data=request.query_params
        )
        query.is_valid(raise_exception=True)

        pharmacies = PharmacySearchService.nearby(
            **query.validated_data
        )

        serializer = PharmacySerializer(
            pharmacies,
            many=True,
        )

        return Response(serializer.data)


class MyPharmacyView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]

    @extend_schema(
        responses={
            200: MyPharmacySerializer,
        },
        tags=["Pharmacy Settings"],
    )
    def get(self, request):
        membership = get_active_pharmacy_membership(
            request.user,
        )

        if membership is None:
            return Response(
                {
                    "detail": (
                        "Aucune pharmacie active et approuvée "
                        "n'est associée à ce compte."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = MyPharmacySerializer(
            membership.pharmacy,
            context={
                "request": request,
                "membership": membership,
            },
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class PharmacyOpeningHoursView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]

    @extend_schema(
        tags=["Pharmacy Settings"],
        summary="Get pharmacy opening hours",
        responses={
            200: PharmacyOpeningHoursSerializer(many=True),
        },
    )
    def get(self, request):
        membership = get_active_pharmacy_membership(
            request.user
        )

        if membership is None:
            return Response(
                {
                    "detail": (
                        "Aucune pharmacie active et approuvée "
                        "n'est associée à ce compte."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        opening_hours = (
            PharmacyOpeningHours.objects
            .filter(pharmacy=membership.pharmacy)
            .order_by("day_of_week")
        )

        serializer = PharmacyOpeningHoursSerializer(
            opening_hours,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Pharmacy Settings"],
        summary="Update pharmacy opening hours",
        request=PharmacyOpeningHoursUpdateSerializer,
        responses={
            200: PharmacyOpeningHoursSerializer(many=True),
        },
    )
    @transaction.atomic
    def put(self, request):
        membership = get_active_pharmacy_membership(
            request.user
        )

        if membership is None:
            return Response(
                {
                    "detail": (
                        "Aucune pharmacie active et approuvée "
                        "n'est associée à ce compte."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if membership.role not in {
            PharmacyMembership.Role.OWNER,
            PharmacyMembership.Role.MANAGER,
        }:
            return Response(
                {
                    "detail": (
                        "Seul un propriétaire ou un responsable "
                        "peut modifier les horaires."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PharmacyOpeningHoursUpdateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        for item in serializer.validated_data[
            "opening_hours"
        ]:
            PharmacyOpeningHours.objects.update_or_create(
                pharmacy=membership.pharmacy,
                day_of_week=item["day_of_week"],
                defaults={
                    "opens_at": item.get("opens_at"),
                    "closes_at": item.get("closes_at"),
                    "is_closed": item["is_closed"],
                },
            )

        opening_hours = (
            PharmacyOpeningHours.objects
            .filter(pharmacy=membership.pharmacy)
            .order_by("day_of_week")
        )

        return Response(
            PharmacyOpeningHoursSerializer(
                opening_hours,
                many=True,
            ).data,
            status=status.HTTP_200_OK,
        )


class PharmacyDutyPeriodsView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]

    @extend_schema(
        tags=["Pharmacy Settings"],
        summary="Get pharmacy duty periods",
        responses={
            200: PharmacyDutyPeriodSerializer(many=True),
        },
    )
    def get(self, request):
        membership = get_active_pharmacy_membership(
            request.user
        )

        if membership is None:
            return Response(
                {
                    "detail": (
                        "Aucune pharmacie active et approuvée "
                        "n'est associée à ce compte."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        duty_periods = (
            PharmacyDutyPeriod.objects
            .filter(
                pharmacy=membership.pharmacy,
            )
            .order_by("starts_at")
        )

        serializer = PharmacyDutyPeriodSerializer(
            duty_periods,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )