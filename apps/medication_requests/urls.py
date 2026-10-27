
from django.urls import path

from .views import (
    MedicationRequestItemPhotoView,
    MedicationRequestListCreateView,
    PartialDecisionView,
    PatientMedicationRequestAttachmentView,
    PatientMedicationRequestDetailView,
    PharmacyAssignmentAttachmentView,
    PharmacyAssignmentRespondView,
    PharmacyPendingAssignmentsView,
)

from .quote_views import (
    PatientQuoteDecisionView,
    PatientQuoteDetailView,
    PharmacyQuoteCreateView,
)


app_name = "medication_requests"


urlpatterns = [
    path(
        "",
        MedicationRequestListCreateView.as_view(),
        name="list-create",
    ),
    path(
        "pharmacy/pending/",
        PharmacyPendingAssignmentsView.as_view(),
        name="pharmacy-pending",
    ),
    path(
        (
            "pharmacy/assignments/"
            "<uuid:assignment_id>/attachment/"
        ),
        PharmacyAssignmentAttachmentView.as_view(),
        name="pharmacy-assignment-attachment",
    ),
    path(
        (
            "pharmacy/assignments/"
            "<uuid:assignment_id>/respond/"
        ),
        PharmacyAssignmentRespondView.as_view(),
        name="pharmacy-assignment-respond",
    ),
    path(
        "<uuid:request_id>/partial-decision/",
        PartialDecisionView.as_view(),
        name="partial-decision",
    ),
    path(
        "<uuid:request_id>/attachment/",
        PatientMedicationRequestAttachmentView.as_view(),
        name="patient-attachment",
    ),
    path(
        "<uuid:request_id>/items/<uuid:item_id>/photo/",
        MedicationRequestItemPhotoView.as_view(),
        name="item-photo",
    ),
    path(
        "<uuid:pk>/",
        PatientMedicationRequestDetailView.as_view(),
        name="detail",
    ),

    path(
        "pharmacy/assignments/<uuid:assignment_id>/quote/",
        PharmacyQuoteCreateView.as_view(),
        name="pharmacy-assignment-quote",
    ),
    path(
        "<uuid:request_id>/quote/",
        PatientQuoteDetailView.as_view(),
        name="patient-quote",
    ),
    path(
        "<uuid:request_id>/quote/decision/",
        PatientQuoteDecisionView.as_view(),
        name="patient-quote-decision",
    ),
]
