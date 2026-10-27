from django.urls import path

from .views import (
    DeviceTokenView,
    NotificationListView,
    NotificationUnreadCountView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
)

app_name = "notifications"

urlpatterns = [
    path(
        "devices/",
        DeviceTokenView.as_view(),
        name="devices",
    ),
    path(
        "",
        NotificationListView.as_view(),
        name="list",
    ),
    path(
        "unread-count/",
        NotificationUnreadCountView.as_view(),
        name="unread-count",
    ),
    path(
        "read-all/",
        NotificationMarkAllReadView.as_view(),
        name="read-all",
    ),
    path(
        "<uuid:notification_id>/read/",
        NotificationMarkReadView.as_view(),
        name="mark-read",
    ),
]