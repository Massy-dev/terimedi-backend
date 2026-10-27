from drf_spectacular.utils import extend_schema

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pharmacies.permissions import IsPharmacyStaff

from .models import Order
from .serializers import (
    PatientOrderSerializer,
    PharmacyOrderSerializer,
    PickupCodeSerializer,
    OrderDetailSerializer,
    PharmacyOrderDetailSerializer,
)
from .services.orders import OrderService


class PatientOrderListView(generics.ListAPIView):
    serializer_class = PatientOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects
            .filter(patient=self.request.user)
            .select_related(
                "pharmacy",
                "medication_request",
            )
            .order_by("-created_at")
        )


class PatientOrderDetailView(generics.RetrieveAPIView):
    serializer_class = PatientOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects
            .filter(patient=self.request.user)
            .select_related(
                "pharmacy",
                "medication_request",
            )
        )


class ConfirmMedicationRequestView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PatientOrderSerializer

    @extend_schema(
        tags=["Orders"],
        summary="Confirm medication request",
        responses={
            201: PatientOrderSerializer,
        },
    )
    def post(self, request, request_id):
        try:
            order = OrderService.confirm_request(
                medication_request_id=request_id,
                patient=request.user,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PatientOrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class MarkOrderReadyView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]
    serializer_class = PharmacyOrderSerializer

    @extend_schema(
        tags=["Orders"],
        summary="Mark order as ready",
        responses={
            200: PharmacyOrderSerializer,
        },
    )
    def post(self, request, order_id):
        try:
            order = OrderService.mark_ready(
                order_id=order_id,
                pharmacy_user=request.user,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PharmacyOrderSerializer(order).data,
            status=status.HTTP_200_OK,
        )


class CompleteOrderView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]
    serializer_class = PickupCodeSerializer

    @extend_schema(
        tags=["Orders"],
        summary="Complete an order using pickup code",
        request=PickupCodeSerializer,
        responses={
            200: PharmacyOrderSerializer,
        },
    )
    def post(self, request, order_id):
        serializer = PickupCodeSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            order = OrderService.complete_order(
                order_id=order_id,
                pharmacy_user=request.user,
                pickup_code=serializer.validated_data[
                    "pickup_code"
                ],
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order is None:
            return Response(
                {
                    "detail": "Invalid pickup code.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PharmacyOrderSerializer(order).data,
            status=status.HTTP_200_OK,
        )


class PharmacyOrderListView(generics.ListAPIView):
    serializer_class = PharmacyOrderSerializer
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]

    def get_queryset(self):
        return (
            Order.objects
            .filter(
                pharmacy__memberships__user=self.request.user,
                pharmacy__memberships__is_active=True,
            )
            .select_related(
                "pharmacy",
                "medication_request",
            )
            .distinct()
            .order_by("-created_at")
        )

class PharmacyOrderListView(generics.ListAPIView):
    serializer_class = PharmacyOrderSerializer
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]

    def get_queryset(self):
        return (
            Order.objects
            .filter(
                pharmacy__memberships__user=self.request.user,
                pharmacy__memberships__is_active=True,
            )
            .select_related(
                "pharmacy",
                "medication_request",
            )
            .distinct()
            .order_by("-created_at")
        )

class MarkOrderPreparingView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]

    serializer_class = PharmacyOrderSerializer

    @extend_schema(
        tags=["Orders"],
        summary="Mark order as preparing",
        responses={
            200: PharmacyOrderSerializer,
        },
    )
    def post(self, request, order_id):
        try:
            order = OrderService.mark_preparing(
                order_id=order_id,
                pharmacy_user=request.user,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PharmacyOrderSerializer(order).data,
            status=status.HTTP_200_OK,
        )

class PatientOrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects
            .filter(patient=self.request.user)
            .select_related(
                "pharmacy",
                "medication_request",
                "assignment",
                "assignment__quote",
                "assignment__pharmacy",
            )
            .prefetch_related(
                "medication_request__items",
                "assignment__quote__items",
            )
        )

class PharmacyOrderDetailView(generics.RetrieveAPIView):
    serializer_class = PharmacyOrderDetailSerializer
    permission_classes = [
        IsAuthenticated,
        IsPharmacyStaff,
    ]

    def get_queryset(self):
        return (
            Order.objects
            .filter(
                pharmacy__memberships__user=self.request.user,
                pharmacy__memberships__is_active=True,
            )
            .select_related(
                "pharmacy",
                "medication_request",
                "assignment",
                "assignment__quote",
                "assignment__pharmacy",
            )
            .prefetch_related(
                "medication_request__items",
                "assignment__quote__items",
            )
            .distinct()
        )
