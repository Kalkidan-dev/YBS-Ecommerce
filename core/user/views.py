from datetime import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from rest_framework import generics, status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from .serializers import (
    CustomTokenObtainPairSerializer,
    UserSerializer,
    RegisterSerializer,
)

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Obtain JWT tokens by providing email and password.
    """
    serializer_class = CustomTokenObtainPairSerializer

    @swagger_auto_schema(
        operation_description="Login to get JWT access and refresh tokens.",
        responses={
            200: openapi.Response(
                description="JWT tokens",
                examples={
                    "application/json": {
                        "access": "access_token_here",
                        "refresh": "refresh_token_here"
                    }
                },
            ),
            400: "Bad Request",
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint.
    Sends an activation email upon successful registration.
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Register a new user account.",
        request_body=RegisterSerializer,
        responses={
            201: openapi.Response(description="User created successfully."),
            400: "Bad Request",
        },
    )
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        email = request.data.get("email")
        if email:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # unlikely right after creation but just in case
                return response

            # Prepare activation email
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            domain = f"{request.scheme}://{request.get_host()}"
            activation_link = f"{domain}/activate/{uidb64}/{token}/"

            message = render_to_string("account_activation_email.html", {
                "first_name": user.first_name or "there",
                "activation_link": activation_link,
                "current_year": datetime.now().year,
            })
            send_mail(
                subject="Activate Your YBS Account",
                message="",
                from_email="from@example.com",
                recipient_list=[user.email],
                html_message=message,
            )
        return response


class ResendActivationEmailView(APIView):
    """
    Resend activation email to a user.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Resend account activation email.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email"],
            properties={
                "email": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL),
            },
        ),
        responses={
            200: openapi.Response(description="Activation email resent."),
            400: "Bad Request",
        },
    )
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "No user found with this email"}, status=status.HTTP_400_BAD_REQUEST)

        if user.is_active:
            return Response({"message": "Account is already activated."}, status=status.HTTP_400_BAD_REQUEST)

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        domain = f"{request.scheme}://{request.get_host()}"
        activation_link = f"{domain}/activate/{uidb64}/{token}/"

        message = render_to_string("account_activation_email.html", {
            "first_name": user.first_name or "there",
            "activation_link": activation_link,
            "current_year": datetime.now().year,
        })
        send_mail(
            subject="Activate Your YBS Account - Resend",
            message="",
            from_email="from@example.com",
            recipient_list=[user.email],
            html_message=message,
        )

        return Response({"message": "Activation email resent."}, status=status.HTTP_200_OK)


class ActivateAccountView(APIView):
    """
    Activate user account via uid and token from activation email.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Activate user account via uid and token.",
        responses={
            200: openapi.Response(description="Account activated successfully."),
            400: openapi.Response(description="Invalid or expired activation link."),
        },
    )
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"error": "Invalid activation link"}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)

        if user.is_active:
            return Response({"message": "Account already activated."}, status=status.HTTP_200_OK)

        user.is_active = True
        user.save()

        return Response({"message": "Account activated successfully!"}, status=status.HTTP_200_OK)
    
class UserDetailView(generics.RetrieveUpdateAPIView):
    """
    Retrieve or update authenticated user's profile.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Retrieve the authenticated user's profile.",
        responses={
            200: openapi.Response(
                description="Authenticated user's profile",
                examples={
                    "application/json": {
                        "id": 1,
                        "username": "johndoe",
                        "email": "johndoe@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                    }
                },
            ),
            403: "Forbidden",
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Update the authenticated user's profile.",
        request_body=UserSerializer,
        responses={
            200: openapi.Response(description="Updated user profile."),
            400: "Bad Request",
        },
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing authenticated user's profile.
    Only admin can view all users; others can only see their own.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = User.objects.none()  # Helps schema generation

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return User.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            return User.objects.none()

        if hasattr(user, 'role') and user.role == "admin":
            return User.objects.all()

        return User.objects.filter(id=user.id)

    def get_object(self):
        # Only allow users to retrieve their own profile (unless overridden by detail route)
        return self.request.user

    @swagger_auto_schema(
        operation_description="Prevent listing all users (security).",
        responses={403: "Forbidden"},
    )
    def list(self, request, *args, **kwargs):
        return Response({"detail": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

    @swagger_auto_schema(
        operation_description="Retrieve the authenticated user's profile.",
        responses={
            200: openapi.Response(description="Authenticated user's profile."),
            403: "Forbidden",
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Update the authenticated user's profile.",
        request_body=UserSerializer,
        responses={
            200: openapi.Response(description="Updated user profile."),
            400: "Bad Request",
        },
    )
    @action(detail=False, methods=["patch"], permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(APIView):
    """
    Request password reset email.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Request a password reset email.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email"],
            properties={
                "email": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL),
            },
        ),
        responses={
            200: openapi.Response(description="Password reset email sent."),
            400: "Bad Request",
        },
    )
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "No user with this email found"}, status=status.HTTP_400_BAD_REQUEST)

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        domain = f"{request.scheme}://{request.get_host()}"
        reset_link = f"{domain}/api/reset-password/{uidb64}/{token}/"

        message = render_to_string("password_reset_email.html", {
            "reset_link": reset_link,
            "first_name": user.first_name or "User",
        })
        send_mail(
            subject="Password Reset",
            message="",
            from_email="from@example.com",
            recipient_list=[email],
            html_message=message,
        )

        return Response({"message": "Password reset email sent."}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """
    Confirm password reset with uid and token, set new password.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Confirm password reset using uid and token, set new password.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["password"],
            properties={
                "password": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD),
            },
        ),
        responses={
            200: openapi.Response(description="Password reset successful."),
            400: "Bad Request",
        },
    )
    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"error": "Invalid link"}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)

        password = request.data.get("password")
        if not password:
            return Response({"error": "Password is required"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save()

        return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)
