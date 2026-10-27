from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db import transaction

from apps.accounts.models import User

from .models import (
    Pharmacy,
    PharmacyMembership,
)


class PharmacySearchService:
    @staticmethod
    def nearby(
        *,
        latitude: float,
        longitude: float,
        radius_km: float = 10,
    ):
        patient_location = Point(
            longitude,
            latitude,
            srid=4326,
        )

        return (
            Pharmacy.objects
            .filter(
                status=Pharmacy.Status.APPROVED,
                is_active=True,
                location__distance_lte=(
                    patient_location,
                    D(km=radius_km),
                ),
            )
            .annotate(
                distance=Distance(
                    "location",
                    patient_location,
                )
            )
            .order_by("distance")
        )


class PharmacyRegistrationAlreadyExists(Exception):
    pass


class PharmacyRegistrationService:
    @staticmethod
    @transaction.atomic
    def register(*, user, validated_data):
        existing_pharmacy = (
            Pharmacy.objects
            .select_for_update()
            .filter(owner=user)
            .first()
        )

        existing_membership = (
            PharmacyMembership.objects
            .select_for_update()
            .filter(
                user=user,
                is_active=True,
            )
            .first()
        )

        if (
            existing_pharmacy is not None
            or existing_membership is not None
        ):
            raise PharmacyRegistrationAlreadyExists(
                "Une demande d'inscription pharmacie "
                "existe déjà pour ce compte."
            )

        pharmacy = Pharmacy.objects.create(
            owner=user,
            name=validated_data["name"],
            phone_number=validated_data["phone_number"],
            address=validated_data["address"],
            commune=validated_data["commune"],
            location=Point(
                validated_data["longitude"],
                validated_data["latitude"],
                srid=4326,
            ),
            verification_document=validated_data[
                "verification_document"
            ],
            status=Pharmacy.Status.PENDING,
            is_active=True,
        )

        PharmacyMembership.objects.create(
            pharmacy=pharmacy,
            user=user,
            role=PharmacyMembership.Role.OWNER,
            is_active=True,
        )

        if user.role != User.Role.PHARMACY_STAFF:
            user.role = User.Role.PHARMACY_STAFF
            user.save(
                update_fields=[
                    "role",
                    "updated_at",
                ]
            )

        return pharmacy

    @staticmethod
    def get_registration_for_user(user):
        return (
            Pharmacy.objects
            .filter(owner=user)
            .order_by("-created_at")
            .first()
        )