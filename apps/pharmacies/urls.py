from django.urls import path

from .views import (
    MyPharmacyView,
    NearbyPharmacyView,
    PharmacyDutyPeriodsView,
    PharmacyOpeningHoursView,
    PharmacyRegistrationStatusView,
    PharmacyRegistrationView,
)


app_name = "pharmacies"


urlpatterns = [
    path(
        "register/",
        PharmacyRegistrationView.as_view(),
        name="register",
    ),

    path(
        "registration/",
        PharmacyRegistrationStatusView.as_view(),
        name="registration-status",
    ),

    path(
        "nearby/",
        NearbyPharmacyView.as_view(),
        name="nearby",
    ),

    path(
        "me/",
        MyPharmacyView.as_view(),
        name="my-pharmacy",
    ),

    path(
        "me/opening-hours/",
        PharmacyOpeningHoursView.as_view(),
        name="my-opening-hours",
    ),

    path(
        "me/duty-periods/",
        PharmacyDutyPeriodsView.as_view(),
        name="my-duty-periods",
    ),
]