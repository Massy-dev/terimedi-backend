
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.prelaunch.models import PharmacyPreRegistration


class PharmacyStatusAudit(models.Model):
    """
    Historique des changements de statut
    des candidatures pharmaceutiques.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    pharmacy = models.ForeignKey(
        PharmacyPreRegistration,
        on_delete=models.PROTECT,
        related_name="status_audits",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pharmacy_status_audits",
    )

    old_status = models.CharField(
        max_length=20,
        choices=PharmacyPreRegistration.Status.choices,
    )

    new_status = models.CharField(
        max_length=20,
        choices=PharmacyPreRegistration.Status.choices,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at", "-id"]

        indexes = [
            models.Index(
                fields=["pharmacy", "-created_at"],
                name="pharm_audit_date_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=~Q(
                    old_status=models.F("new_status")
                ),
                name="pharm_audit_status_diff",
            ),
        ]

    def __str__(self):
        return (
            f"{self.pharmacy_id}: "
            f"{self.old_status} -> {self.new_status}"
        )
