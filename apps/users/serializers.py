from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from apps.pharmacies.serializers import PharmacySerializer
from .models import CustomUser
User = get_user_model()


class PhoneLoginSerializer(serializers.Serializer):
    phone = serializers.CharField()

    def validate_phone(self, value):
        value = value.replace(" ", "")
        if not value.startswith("+"):
            value = "+225" + value  # ajouter indicatif
        return value

    def create_or_get_user(self):
        
        phone = self.validated_data['phone']
        user, created = CustomUser.objects.get_or_create(phone=phone)
        refresh = RefreshToken.for_user(user)
        return {
            "user": {
                "id": user.id,
                "phone": user.phone,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(style={'input_type': 'password'}, write_only=True)
   
    class Meta:
        model = User
        fields = ['phone', 'role', 'password', 'password2']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "le mots ne correspondent pas."})
        return data

   
    def create(self, validated_data):
        print("dataa ------------- ",validated_data)
        user = User.objects.create_user(
            
            phone=validated_data.get('phone'),
            password=validated_data['password'],
            role= validated_data['role'],

        )
        return user


class UserSerializer(serializers.ModelSerializer):
    pharmacy = PharmacySerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "phone", "role", "pharmacy"]


class CustomLoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        print("data------------------- ",data)
        phone = data.get('phone')
        password = data.get('password')

        user = authenticate(phone=phone, password=password)
        if not user:
            raise serializers.ValidationError("Identifiants invalides")

        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'phone': user.phone,
                'email': user.email,
                'role': user.role
            }
        }