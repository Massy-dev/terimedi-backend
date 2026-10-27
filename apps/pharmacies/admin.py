import mimetypes
from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.urls import path, reverse

from django.contrib import admin, messages
from django.utils.html import format_html

from .models import (
    Pharmacy,
    PharmacyDutyPeriod,
    PharmacyMembership,
    PharmacyOpeningHours,
)


class PharmacyOpeningHoursInline(admin.TabularInline):
    model = PharmacyOpeningHours
    extra = 0
    can_delete = False

    fields = (
        "day_of_week",
        "opens_at",
        "closes_at",
        "is_closed",
    )


class PharmacyMembershipInline(admin.TabularInline):
    model = PharmacyMembership
    extra = 0
    can_delete = False

    fields = (
        "user",
        "role",
        "is_active",
        "created_at",
    )

    readonly_fields = (
        "user",
        "role",
        "created_at",
    )


@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "commune",
        "owner_phone_number",
        "status_badge",
        "is_active",
        "created_at",
    )

    list_filter = (
        "status",
        "is_active",
        "commune",
        "created_at",
    )

    search_fields = (
        "name",
        "phone_number",
        "address",
        "commune",
        "owner__phone_number",
        "owner__first_name",
        "owner__last_name",
    )

    ordering = (
        "-created_at",
    )

    readonly_fields = (
        "id",
        "owner",
        "verification_document_link",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Pharmacie",
            {
                "fields": (
                    "id",
                    "name",
                    "phone_number",
                    "address",
                    "commune",
                    "location",
                ),
            },
        ),
        (
            "Responsable",
            {
                "fields": (
                    "owner",
                ),
            },
        ),
        (
            "Vérification",
            {
                "fields": (
                    "verification_document_link",
                    "status",
                    "rejection_reason",
                ),
            },
        ),
        (
            "État",
            {
                "fields": (
                    "is_active",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    actions = (
        "approve_pharmacies",
        "reject_pharmacies",
    )

    inlines = (
        PharmacyMembershipInline,
        PharmacyOpeningHoursInline,
    )

    @admin.display(
        description="Responsable",
    )
    def owner_phone_number(self, obj):
        if obj.owner is None:
            return "-"

        return obj.owner.phone_number

    @admin.display(
        description="Statut",
        ordering="status",
    )

    def get_urls(self):
        custom_urls = [
            path(
                "<path:object_id>/verification-document/",
                self.admin_site.admin_view(
                    self.verification_document_view,
                    cacheable=False,
                ),
                name="pharmacies_pharmacy_verification_document",
            ),
        ]

        return custom_urls + super().get_urls()


    def verification_document_view(self, request, object_id):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied

        pharmacy = self.get_object(request, object_id)

        if pharmacy is None:
            raise Http404

        if not self.has_view_or_change_permission(
            request,
            pharmacy,
        ):
            raise PermissionDenied

        document = pharmacy.verification_document

        if not document:
            raise Http404

        try:
            file_handle = document.open("rb")
        except (FileNotFoundError, OSError, ValueError):
            raise Http404 from None

        filename = Path(document.name).name

        content_type, _ = mimetypes.guess_type(filename)

        response = FileResponse(
            file_handle,
            content_type=(
                content_type or "application/octet-stream"
            ),
            as_attachment=False,
            filename=filename,
        )

        response["Cache-Control"] = (
            "private, no-store, max-age=0"
        )
        response["X-Content-Type-Options"] = "nosniff"

        return response

    def status_badge(self, obj):
        styles = {
            Pharmacy.Status.PENDING: (
                "background:#fff3cd;"
                "color:#856404;"
            ),
            Pharmacy.Status.APPROVED: (
                "background:#d4edda;"
                "color:#155724;"
            ),
            Pharmacy.Status.REJECTED: (
                "background:#f8d7da;"
                "color:#721c24;"
            ),
        }

        labels = {
            Pharmacy.Status.PENDING: "En attente",
            Pharmacy.Status.APPROVED: "Approuvée",
            Pharmacy.Status.REJECTED: "Refusée",
        }

        style = styles.get(
            obj.status,
            "background:#eeeeee;color:#333333;",
        )

        label = labels.get(
            obj.status,
            obj.status,
        )

        return format_html(
            '<span style="{} padding:4px 8px;'
            'border-radius:12px;font-weight:600;">'
            "{}</span>",
            style,
            label,
        )

    @admin.display(
        description="Justificatif",
    )

    @admin.display(description="Justificatif")
    def verification_document_link(self, obj):
        if not obj.pk or not obj.verification_document:
            return "Aucun justificatif"

        url = reverse(
            "admin:pharmacies_pharmacy_verification_document",
            args=[obj.pk],
        )

        return format_html(
            '<a href="{}" target="_blank" '
            'rel="noopener noreferrer">'
            "Ouvrir le justificatif"
            "</a>",
            url,
        )

    @admin.action(
        description="Approuver les pharmacies sélectionnées",
    )
    def approve_pharmacies(self, request, queryset):
        pending_pharmacies = queryset.filter(
            status=Pharmacy.Status.PENDING,
        )

        count = pending_pharmacies.update(
            status=Pharmacy.Status.APPROVED,
            rejection_reason="",
        )

        if count:
            self.message_user(
                request,
                (
                    f"{count} pharmacie(s) "
                    "approuvée(s) avec succès."
                ),
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                (
                    "Aucune pharmacie en attente "
                    "n'a été approuvée."
                ),
                level=messages.WARNING,
            )

    @admin.action(
        description="Refuser les pharmacies sélectionnées",
    )
    def reject_pharmacies(self, request, queryset):
        pending_pharmacies = queryset.filter(
            status=Pharmacy.Status.PENDING,
        )

        count = pending_pharmacies.update(
            status=Pharmacy.Status.REJECTED,
        )

        if count:
            self.message_user(
                request,
                (
                    f"{count} pharmacie(s) refusée(s). "
                    "Pensez à renseigner le motif du refus "
                    "dans chaque fiche."
                ),
                level=messages.WARNING,
            )
        else:
            self.message_user(
                request,
                (
                    "Aucune pharmacie en attente "
                    "n'a été refusée."
                ),
                level=messages.WARNING,
            )


@admin.register(PharmacyDutyPeriod)
class PharmacyDutyPeriodAdmin(admin.ModelAdmin):
    list_display = (
        "pharmacy",
        "starts_at",
        "ends_at",
    )

    list_filter = (
        "starts_at",
        "ends_at",
    )

    search_fields = (
        "pharmacy__name",
        "pharmacy__commune",
    )

    autocomplete_fields = (
        "pharmacy",
    )

    ordering = (
        "-starts_at",
    )


@admin.register(PharmacyMembership)
class PharmacyMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "pharmacy",
        "role",
        "is_active",
        "created_at",
    )

    list_filter = (
        "role",
        "is_active",
    )

    search_fields = (
        "user__phone_number",
        "user__first_name",
        "user__last_name",
        "pharmacy__name",
    )

    autocomplete_fields = (
        "pharmacy",
    )

    readonly_fields = (
        "created_at",
    )


@admin.register(PharmacyOpeningHours)
class PharmacyOpeningHoursAdmin(admin.ModelAdmin):
    list_display = (
        "pharmacy",
        "day_of_week",
        "opens_at",
        "closes_at",
        "is_closed",
    )

    list_filter = (
        "day_of_week",
        "is_closed",
    )

    search_fields = (
        "pharmacy__name",
    )

    autocomplete_fields = (
        "pharmacy",
    )