from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Customize JWT token response to include user details."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data.update({
            'email': self.user.email,
            'role': self.user.role,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
        })
        return data

class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile data"""

    class Meta:
        model = User
        fields = ['id', 'public_id', 'email', 'first_name', 'last_name', 'phone_number', 'role', 'is_active']
        read_only_fields = ['id', 'public_id', 'email']


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""

    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 'role', 'password']

    def create(self, validated_data):
        """Create a new user and return with JWT tokens"""
        user = User.objects.create_user(**validated_data)
        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "email": user.email,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
