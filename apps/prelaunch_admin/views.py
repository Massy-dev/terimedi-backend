from .models import PharmacyStatusAudit
from django.db.models import Count, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import PharmacyStatusAudit
from .serializers import PharmacyStatusAuditSerializer
from apps.prelaunch.models import (
    PharmacyPreRegistration,
    WaitlistEntry,
)
from .serializers import AdminActivitySerializer
from .permissions import IsPrelaunchAdmin
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import generics, status

from .pagination import PharmacyAdminPagination
from .serializers import (
    PharmacyAdminSerializer,
    PharmacyStatusUpdateSerializer,
    PatientAdminSerializer,
)

from datetime import datetime, time,timedelta
from zoneinfo import ZoneInfo


from django.db.models.functions import TruncDate
from django.utils import timezone

class PharmacyAdminListView(generics.ListAPIView):
    """
    Liste paginée et filtrable des candidatures.
    """

    serializer_class = PharmacyAdminSerializer
    pagination_class = PharmacyAdminPagination
    permission_classes = [
        IsAuthenticated,
        IsPrelaunchAdmin,
    ]

    def get_queryset(self):
        queryset = PharmacyPreRegistration.objects.all()

        search = self.request.query_params.get("search", "").strip()
        commune = self.request.query_params.get("commune", "").strip()
        pharmacy_status = self.request.query_params.get(
            "status", ""
        ).strip()

        if search:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(pharmacy_name__icontains=search)
                | Q(contact_name__icontains=search)
                | Q(phone__icontains=search)
            )

        if commune:
            queryset = queryset.filter(
                commune__iexact=commune
            )

        if pharmacy_status:
            queryset = queryset.filter(
                status=pharmacy_status
            )

        ordering = self.request.query_params.get(
            "ordering", "-created_at"
        )

        if ordering not in ("created_at", "-created_at"):
            ordering = "-created_at"

        return queryset.order_by(ordering, "-id")

class PharmacyAdminDetailView(generics.RetrieveAPIView):
    """
    Consultation d'une candidature par UUID.
    """

    queryset = PharmacyPreRegistration.objects.all()
    serializer_class = PharmacyAdminSerializer

    permission_classes = [
        IsAuthenticated,
        IsPrelaunchAdmin,
    ]

class PrelaunchDashboardView(APIView):
    """
    Statistiques générales du pré-lancement TeriMedi.

    Aucune donnée personnelle n'est retournée.
    """

    permission_classes = [
        IsAuthenticated,
        IsPrelaunchAdmin,
    ]

    def get(self, request):
        patient_counts = {
            row["status"]: row["total"]
            for row in (
                WaitlistEntry.objects
                .values("status")
                .annotate(total=Count("id"))
            )
        }

        pharmacy_counts = {
            row["status"]: row["total"]
            for row in (
                PharmacyPreRegistration.objects
                .values("status")
                .annotate(total=Count("id"))
            )
        }

        patients_total = sum(patient_counts.values())
        patients_verified = patient_counts.get(
            WaitlistEntry.Status.VERIFIED,
            0,
        )

        pharmacies_total = sum(pharmacy_counts.values())
        pharmacies_approved = pharmacy_counts.get(
            PharmacyPreRegistration.Status.APPROVED,
            0,
        )

        verification_rate = (
            round(patients_verified / patients_total * 100, 2)
            if patients_total
            else 0
        )

        return Response(
            {
                "patients": {
                    "total": patients_total,
                    "verified": patients_verified,
                    "pending": patient_counts.get(
                        WaitlistEntry.Status.PENDING,
                        0,
                    ),
                    "verification_rate": verification_rate,
                },
                "pharmacies": {
                    "total": pharmacies_total,
                    "new": pharmacy_counts.get(
                        PharmacyPreRegistration.Status.NEW,
                        0,
                    ),
                    "contacted": pharmacy_counts.get(
                        PharmacyPreRegistration.Status.CONTACTED,
                        0,
                    ),
                    "interested": pharmacy_counts.get(
                        PharmacyPreRegistration.Status.INTERESTED,
                        0,
                    ),
                    "approved": pharmacies_approved,
                    "rejected": pharmacy_counts.get(
                        PharmacyPreRegistration.Status.REJECTED,
                        0,
                    ),
                },
            }
        )

class PharmacyAdminStatusUpdateView(APIView):
    """
    Modification du statut avec journal d'audit atomique.
    """

    permission_classes = [
        IsAuthenticated,
        IsPrelaunchAdmin,
    ]

    @transaction.atomic
    def patch(self, request, pk):
        serializer = PharmacyStatusUpdateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        pharmacy = get_object_or_404(
            PharmacyPreRegistration.objects.select_for_update(),
            pk=pk,
        )

        old_status = pharmacy.status
        new_status = serializer.validated_data["status"]

        if old_status != new_status:
            pharmacy.status = new_status

            pharmacy.save(
                update_fields=["status", "updated_at"]
            )

            PharmacyStatusAudit.objects.create(
                pharmacy=pharmacy,
                actor=request.user,
                old_status=old_status,
                new_status=new_status,
            )

        return Response(
            PharmacyAdminSerializer(pharmacy).data,
            status=status.HTTP_200_OK,
        )

class PharmacyStatusHistoryView(generics.ListAPIView):
    """
    Historique des changements de statut
    d'une candidature pharmaceutique.
    """

    serializer_class = PharmacyStatusAuditSerializer
    permission_classes = [
        IsAuthenticated,
        IsPrelaunchAdmin,
    ]
    pagination_class = PharmacyAdminPagination

    def get_queryset(self):
        pharmacy = get_object_or_404(
            PharmacyPreRegistration,
            pk=self.kwargs["pk"],
        )

        return (
            PharmacyStatusAudit.objects
            .filter(pharmacy=pharmacy)
            .select_related("actor")
            .order_by("-created_at", "-id")
        )

class AdminSessionView(APIView):
    """
    Vérifie que le JWT appartient à un
    superutilisateur Django actif.
    """

    permission_classes = [
        IsAuthenticated,
        IsPrelaunchAdmin,
    ]

    def get(self, request):
        user = request.user

        return Response(
            {
                "id": str(user.pk),
                "phone_number": user.phone_number,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_admin": True,
            },
            status=status.HTTP_200_OK,
        )

class PatientAdminListView(generics.ListAPIView):
    """
    Liste paginée des préinscriptions patients.

    Filtres disponibles :
    - search : prénom ou téléphone
    - commune : correspondance exacte insensible à la casse
    - status : PENDING ou VERIFIED
    - ordering : created_at ou -created_at
    """

    serializer_class = PatientAdminSerializer
    pagination_class = PharmacyAdminPagination

    permission_classes = [
        IsAuthenticated,
        IsPrelaunchAdmin,
    ]

    def get_queryset(self):
        queryset = (
            WaitlistEntry.objects
            .select_related("referred_by")
            .annotate(
                referrals_count=Count("referrals")
            )
        )

        search = self.request.query_params.get(
            "search", ""
        ).strip()

        commune = self.request.query_params.get(
            "commune", ""
        ).strip()

        patient_status = self.request.query_params.get(
            "status", ""
        ).strip()

        ordering = self.request.query_params.get(
            "ordering", "-created_at"
        )

        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(phone__icontains=search)
            )

        if commune:
            queryset = queryset.filter(
                commune__iexact=commune
            )

        valid_statuses = {
            WaitlistEntry.Status.PENDING,
            WaitlistEntry.Status.VERIFIED,
        }

        if patient_status:
            if patient_status not in valid_statuses:
                return queryset.none()

            queryset = queryset.filter(
                status=patient_status
            )

        if ordering not in (
            "created_at",
            "-created_at",
        ):
            ordering = "-created_at"

        return queryset.order_by(
            ordering,
            "-id",
        )

class PatientAdminDetailView(generics.RetrieveAPIView):
    """
    Consultation d'un dossier de préinscription patient.

    Lecture seule.
    """

    serializer_class = PatientAdminSerializer

    permission_classes = [
        IsAuthenticated,
        IsPrelaunchAdmin,
    ]

    def get_queryset(self):
        return (
            WaitlistEntry.objects
            .select_related("referred_by")
            .annotate(
                referrals_count=Count("referrals")
            )
        )

class PrelaunchAnalyticsView(APIView):
    """
    Séries chronologiques des inscriptions du pré-lancement.

    - 30 jours calendaires, aujourd'hui inclus
    - Fuseau horaire Africa/Abidjan
    - Comptage par date de création
    - Aucune donnée personnelle exposée
    """

    permission_classes = [
        IsAuthenticated,
        IsPrelaunchAdmin,
    ]

    def get(self, request):
        local_tz = ZoneInfo("Africa/Abidjan")
        today = timezone.localdate(timezone=local_tz)

        period_days = 30
        start_date = today - timedelta(days=period_days - 1)

        # Début de la période en heure locale.
        """start_datetime = timezone.make_aware(
            __import__("datetime").datetime.combine(
                start_date,
                __import__("datetime").time.min,
            ),
            local_tz,
        )"""

        start_datetime = datetime.combine(
            start_date,
            time.min,
            tzinfo=local_tz,
        )

        patient_counts = {
            row["day"]: row["total"]
            for row in (
                WaitlistEntry.objects
                .filter(created_at__gte=start_datetime)
                .annotate(
                    day=TruncDate(
                        "created_at",
                        tzinfo=local_tz,
                    )
                )
                .values("day")
                .annotate(total=Count("id"))
                .order_by("day")
            )
        }

        pharmacy_counts = {
            row["day"]: row["total"]
            for row in (
                PharmacyPreRegistration.objects
                .filter(created_at__gte=start_datetime)
                .annotate(
                    day=TruncDate(
                        "created_at",
                        tzinfo=local_tz,
                    )
                )
                .values("day")
                .annotate(total=Count("id"))
                .order_by("day")
            )
        }

        patients = []
        pharmacies = []

        for offset in range(period_days):
            day = start_date + timedelta(days=offset)

            patients.append(
                {
                    "date": day.isoformat(),
                    "total": patient_counts.get(day, 0),
                }
            )

            pharmacies.append(
                {
                    "date": day.isoformat(),
                    "total": pharmacy_counts.get(day, 0),
                }
            )

        return Response(
            {
                "period_days": period_days,
                "timezone": "Africa/Abidjan",
                "patients": patients,
                "pharmacies": pharmacies,
            }
        )

class AdminActivityListView(generics.ListAPIView):
    """
    Journal global des modifications de statut
    des candidatures pharmacies.

    Lecture seule et accès superutilisateur.
    """

    serializer_class = AdminActivitySerializer

    permission_classes = [
        IsAuthenticated,
        IsPrelaunchAdmin,
    ]

    pagination_class = PharmacyAdminPagination

    def get_queryset(self):
        return (
            PharmacyStatusAudit.objects
            .select_related(
                "pharmacy",
                "actor",
            )
            .order_by(
                "-created_at",
                "-id",
            )
        )
