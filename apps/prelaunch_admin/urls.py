
from django.urls import path

from .views import (
    PrelaunchDashboardView,
    PharmacyAdminListView,
    PharmacyAdminDetailView,
    PharmacyAdminStatusUpdateView,
    PharmacyStatusHistoryView,
    AdminSessionView,
    PatientAdminListView,
    PatientAdminDetailView,
    PrelaunchAnalyticsView,
    AdminActivityListView
)


app_name = "prelaunch_admin"

urlpatterns = [
    path(
        "dashboard/",
        PrelaunchDashboardView.as_view(),
        name="dashboard",
    ),

    path(
        "pharmacies/",
        PharmacyAdminListView.as_view(),
        name="pharmacy-list",
    ),

    path(
        "pharmacies/<uuid:pk>/",
        PharmacyAdminDetailView.as_view(),
        name="pharmacy-detail",
    ),

    path(
        "pharmacies/<uuid:pk>/status/",
        PharmacyAdminStatusUpdateView.as_view(),
        name="pharmacy-status",
    ),

    path(
        "pharmacies/<uuid:pk>/history/",
        PharmacyStatusHistoryView.as_view(),
        name="pharmacy-history",
    ),

    path(
        "session/",
        AdminSessionView.as_view(),
        name="admin-session",
    ),
    
    path(
        "patients/",
        PatientAdminListView.as_view(),
        name="patient-list",
    ),

    path(
        "patients/<uuid:pk>/",
        PatientAdminDetailView.as_view(),
        name="patient-detail",
    ),

    path(
        "analytics/",
        PrelaunchAnalyticsView.as_view(),
        name="analytics",
    ),
    path(
        "activities/",
        AdminActivityListView.as_view(),
        name="activity-list",
    ),
]
