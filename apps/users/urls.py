from django.urls import path
from .views import *
from rest_framework_simplejwt.views import TokenObtainPairView

urlpatterns = [

    path('me/', user_profile, name='user-profile'),
    path("auth/", FirebaseAuthView.as_view(), name="firebase_auth"),
    path('register/', RegisterView.as_view(), name='register'),
    #path('login/', LoginView.as_view(), name='login'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('phone-connexion/', PhoneLoginOrRegisterView.as_view(), name='phone-login-or-register'),
]
