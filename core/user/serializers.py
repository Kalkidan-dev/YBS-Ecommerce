from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.utils.http import urlsafe_base64_decode
from django.template.loader import render_to_string



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
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 'role', 'password', 'confirm_password']

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_user(**validated_data)
        user.is_active = False
        user.save()
        return user

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update({"message": "Account created. Check your email to activate."})
        return data


    def to_representation(self, instance):
        """Return limited data; no token until account is activated."""
        data = super().to_representation(instance)
        data.update({"message": "Account created. Check your email to activate."})
        return data
    
class PasswordResetSerializer(serializers.Serializer):
    """Serializer for password reset request"""

    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user with this email found.")
        return value

    def save(self):
        email = self.validated_data['email']
        user = User.objects.get(email=email)

        # Generate password reset token
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

        message = render_to_string("password_reset_email.html", {
        "first_name": user.first_name,
        "reset_link": reset_link,
    })
        # Send email
        send_mail(
            subject='Reset Your Password',
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=message,
            fail_silently=False,
        )
        return user
    
class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""

    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True, min_length=6)

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs

    def save(self, uid, token):
        user = User.objects.get(pk=urlsafe_base64_decode(uid).decode())
        if default_token_generator.check_token(user, token):
            user.set_password(self.validated_data['password'])
            user.save()
            return user
        else:
            raise serializers.ValidationError("Invalid token or user ID.")
        
