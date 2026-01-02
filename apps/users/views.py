from rest_framework_simplejwt.tokens import RefreshToken
import firebase_admin
from firebase_admin import auth as firebase_auth

from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework import generics
from .serializers import *
from apps.pharmacies.models import Pharmacy
from django.contrib.auth import get_user_model

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

User = get_user_model()

@api_view(["POST"])
def register_device_token(request):
    user = request.user
    token = request.data.get("device_token")

    if not token:
        return Response({"error": "Token required"}, status=400)

    user.device_token = token
    user.save()

    return Response({"success": True})

# Create your views here.

class PhoneLoginOrRegisterView(APIView):
    permission_classes = [AllowAny]
   
    def post(self, request):
       
        serializer = PhoneLoginSerializer(data=request.data)
        
       
        if serializer.is_valid():
            data = serializer.create_or_get_user()
           
            return Response(data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    user = request.user
    # Adapte selon ton modèle utilisateur
    return Response({
        "id": user.id,
        "username": user.username,
        "phone": user.phone,
        "role": user.role,
         #getattr(user, "pharmacy", None),
    }, status=status.HTTP_200_OK)

        
class FirebaseAuthView(APIView):
    def post(self, request):
        id_token = request.data.get("idToken")
       
        if not id_token:
            return Response({"error": "idToken manquant"}, status=400)

        try:
            # Vérifier le token Firebase
            decoded_token = firebase_auth.verify_id_token(id_token)
            uid = decoded_token["uid"]
            email = decoded_token.get("email", f"{uid}@firebase.local")

            # Créer ou récupérer un User Django lié
            user, created = User.objects.get_or_create(username=uid, defaults={"email": email})

            # Générer un JWT avec SimpleJWT
            refresh = RefreshToken.for_user(user)
            print(str(refresh.access_token))
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user_id": user.id,
                "email": user.email
            })
        except Exception as e:
            return Response({"error": str(e)}, status=401)

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    
    def perform_create(self, serializer):
        
        serializer.save(role='pharmacien', is_active=False)

class LoginView(APIView):
   
    serializer_class = CustomLoginSerializer
    def post(self, request):
        print("login----------------------- 2")
        serializer = CustomLoginSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)