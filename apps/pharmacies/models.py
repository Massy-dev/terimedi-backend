import uuid

from django.conf import settings
from django.contrib.gis.db import models
from django.utils import timezone


class Pharmacy(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="owned_pharmacies",
        null=True,
        blank=True,
    )

    name = models.CharField(
        max_length=255,
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
    )

    address = models.CharField(
        max_length=255,
    )

    commune = models.CharField(
        max_length=100,
    )

    location = models.PointField(
        geography=True,
        srid=4326,
    )

    verification_document = models.FileField(
        upload_to="pharmacies/verification/%Y/%m/",
        null=True,
        blank=True,
    )

    rejection_reason = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def is_open_at(self, moment=None):
        """
        Return True if the pharmacy is open according to
        its normal opening hours at the given moment.
        """
        moment = moment or timezone.now()
        local_moment = timezone.localtime(moment)

        opening_hours = self.opening_hours.filter(
            day_of_week=local_moment.weekday(),
            is_closed=False,
        ).first()

        if not opening_hours:
            return False

        current_time = local_moment.time()

        return (
            opening_hours.opens_at is not None
            and opening_hours.closes_at is not None
            and opening_hours.opens_at
            <= current_time
            < opening_hours.closes_at
        )

    def is_on_duty_at(self, moment=None):
        """
        Return True if the pharmacy has an active duty period
        at the given moment.
        """
        moment = moment or timezone.now()

        return self.duty_periods.filter(
            starts_at__lte=moment,
            ends_at__gt=moment,
        ).exists()

    def is_available_at(self, moment=None):
        """
        A pharmacy is accessible if it is normally open
        OR currently on duty.
        """
        moment = moment or timezone.now()

        return (
            self.is_open_at(moment)
            or self.is_on_duty_at(moment)
        )

    def __str__(self):
        return self.name


class PharmacyOpeningHours(models.Model):
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name="opening_hours",
    )

    day_of_week = models.PositiveSmallIntegerField(
        choices=DayOfWeek.choices,
    )

    opens_at = models.TimeField(
        null=True,
        blank=True,
    )

    closes_at = models.TimeField(
        null=True,
        blank=True,
    )

    is_closed = models.BooleanField(
        default=False,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "pharmacy",
                    "day_of_week",
                ],
                name="unique_pharmacy_opening_day",
            ),
        ]

    def __str__(self):
        return (
            f"{self.pharmacy.name} - "
            f"{self.get_day_of_week_display()}"
        )


class PharmacyDutyPeriod(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name="duty_periods",
    )

    starts_at = models.DateTimeField()

    ends_at = models.DateTimeField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    ends_at__gt=models.F("starts_at")
                ),
                name="duty_period_ends_after_start",
            ),
        ]

    def __str__(self):
        return (
            f"{self.pharmacy.name}: "
            f"{self.starts_at} -> {self.ends_at}"
        )


class PharmacyMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        MANAGER = "MANAGER", "Manager"
        STAFF = "STAFF", "Staff"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pharmacy_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STAFF,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pharmacy", "user"],
                name="unique_pharmacy_user_membership",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.phone_number} "
            f"-> {self.pharmacy.name}"
        )