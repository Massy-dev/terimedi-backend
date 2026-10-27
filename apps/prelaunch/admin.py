from django.contrib import admin
from apps.prelaunch.models import PharmacyPreRegistration


@admin.register(PharmacyPreRegistration)
class PharmacyPreRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "pharmacy_name",
        "commune",
        "contact_name",
        "phone",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "commune",
        "created_at",
    )

    search_fields = (
        "pharmacy_name",
        "contact_name",
        "phone",
        "commune",
    )

    readonly_fields = (
        "id",
        "consent_at",
        "created_at",
        "updated_at",
    )

    list_per_page = 25

    ordering = ("-created_at",)

    fields = (
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