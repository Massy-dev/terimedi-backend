from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from django.conf.urls.static import static
from django.conf import settings

# Swagger
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# JWT views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,

)
from django.http import JsonResponse

from config.firebase import init_firebase

init_firebase()


schema_view = get_schema_view(
   openapi.Info(
      title="TeriMedi API",
      default_version='v1',
      description="Documentation interactive de l'API TeriMedi (version MVP)",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@terimedi.ci"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

def health(request):
    return JsonResponse({
        "status": "ok",
        "service": "terimedi-backend"
    })

urlpatterns = [

    path("", health), 
    path('admin/', admin.site.urls),

    # Auth JWT
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # App users
    path('api/users/', include('apps.users.urls')),

    # Swagger docs
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # App pharmacies
    path('api/pharmacies/', include('apps.pharmacies.urls')),
    

    # App orders
    path('api/orders/', include('apps.orders.urls')),

    #App notifications
    path('api/notifications/', include('apps.notifications.urls')),
    
    
    #API FIREBASE
    path('api/firebase/', include('apps.users.urls')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
