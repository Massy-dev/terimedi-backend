from django.urls import path

from . import views

from apps.prelaunch.views import PharmacyPreRegistrationView

urlpatterns = [

  path(
        "waitlist/",
        views.WaitlistRegistrationView.as_view(),
        name="prelaunch-waitlist",
    ),

  path(
      "otp/verify/",
      views.OTPVerifyView.as_view(),
      name="prelaunch-otp-verify",
  ),

  path(
    "otp/resend/",
    views.OTPResendView.as_view(),
    name="prelaunch-otp-resend",
  ),

  path(
    "pharmacies/",
    PharmacyPreRegistrationView.as_view(),
    name="prelaunch-pharmacy-register",
  ),

]