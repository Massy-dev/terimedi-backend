from django.urls import path

from .views import *

app_name = "orders"

urlpatterns = [
    path(
        "",
        PatientOrderListView.as_view(),
        name="patient-order-list",
    ),
    path(
        "requests/<uuid:request_id>/confirm/",
        ConfirmMedicationRequestView.as_view(),
        name="confirm-request",
    ),
    path(
        "<uuid:pk>/",
        PatientOrderDetailView.as_view(),
        name="patient-order-detail",
    ),
    path(
        "<uuid:order_id>/ready/",
        MarkOrderReadyView.as_view(),
        name="mark-ready",
    ),
    path(
        "<uuid:order_id>/complete/",
        CompleteOrderView.as_view(),
        name="complete",
    ),

    path(
        "pharmacy/",
        PharmacyOrderListView.as_view(),
        name="pharmacy-order-list",
    ),

    path(
        "<uuid:order_id>/preparing/",
        MarkOrderPreparingView.as_view(),
        name="mark-preparing",
    ),

    path(
        "pharmacy/<uuid:pk>/",
        PharmacyOrderDetailView.as_view(),
        name="pharmacy-order-detail",
    ),

]