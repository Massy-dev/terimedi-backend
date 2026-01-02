from rest_framework import serializers
from .models import Pharmacy
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point

User = get_user_model()


class PharmacySerializer(serializers.ModelSerializer):

    class Meta:
        model = Pharmacy
        fields = [
            'id', 'name', 'address', 'phone_number', 'description',
            'latitude', 'longitude', 'is_approved', 'is_deleted', 'created_at' 
        ]
        read_only_fields = ['is_approved', 'created_at', 'is_deleted']


    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None

    def update(self, instance, validated_data):
        if 'latitude' in validated_data and 'longitude' in validated_data:
            latitude = validated_data.pop("latitude")
            longitude = validated_data.pop("longitude")
            instance.location = Point(float(longitude), float(latitude))
            instance.latitude = latitude
            instance.longitude = longitude
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance

class PharmacyDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé avec plus d'informations"""
    logo_url = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Pharmacy
        fields = [
            'id', 'name', 'description', 'address', 'city',
            'phone', 'email', 'logo', 'logo_url', 'latitude', 
            'longitude', 'is_approved', 'is_active', 'created_at',
            'updated_at', 'owner_name'
        ]
    
    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None
    
    def get_owner_name(self, obj):
        if obj.owner:
            return f"{obj.owner.name} {obj.owner.phone_number}"
        return None
        
class DeviceTokenSerializer(serializers.Serializer):
    token = serializers.CharField()