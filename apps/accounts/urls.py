from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import *


app_name = "accounts"


urlpatterns = [
    path(
        "register/request-otp/",
        RegisterRequestOTPView.as_view(),
        name="register-request-otp",
    ),
    path(
        "register/verify-otp/",
        RegisterVerifyOTPView.as_view(),
        name="register-verify-otp",
    ),
    path(
        "register/complete/",
        RegisterCompleteView.as_view(),
        name="register-complete",
    ),

    path(
    "login/",
        LoginView.as_view(),
        name="login",
    ),
    path(
        "me/",
        MeView.as_view(),
        name="me",
    ),

    path(
        "token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),

    path(
    "logout/",
        LogoutView.as_view(),
        name="logout",
    ),
]