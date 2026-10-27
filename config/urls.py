
"""
URL configuration for the TeriMedi backend.

Private media files are not exposed through /media/.
They must be served through authenticated API endpoints.
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


urlpatterns = [
    path(
        "admin/",
        admin.site.urls,
    ),

    path(
        "api/schema/",
        SpectacularAPIView.as_view(),
        name="api-schema",
    ),

    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="api-schema",
        ),
        name="swagger-ui",
    ),

    path(
        "api/redoc/",
        SpectacularRedocView.as_view(
            url_name="api-schema",
        ),
        name="redoc",
    ),

    path(
        "api/v1/accounts/",
        include("apps.accounts.urls"),
    ),

    path(
        "api/v1/pharmacies/",
        include("apps.pharmacies.urls"),
    ),

    path(
        "api/v1/medication-requests/",
        include("apps.medication_requests.urls"),
    ),

    path(
        "api/v1/orders/",
        include("apps.orders.urls"),
    ),

    path(
        "api/v1/notifications/",
        include("apps.notifications.urls"),
    ),

    path(
        "api/v1/prelaunch/",
        include("apps.prelaunch.urls"),
    ),

    path(
        "api/v1/prelaunch-admin/",
        include("apps.prelaunch_admin.urls"),
    ),
]
