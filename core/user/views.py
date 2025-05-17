from rest_framework import generics, status, viewsets, permissions
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from .serializers import CustomTokenObtainPairSerializer, UserSerializer, RegisterSerializer
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.template.loader import render_to_string
from datetime import datetime

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    @swagger_auto_schema(
        operation_description="Login to get JWT Token",
        responses={
            200: openapi.Response(
                description="JWT tokens",
                examples={
                    'application/json': {
                        "access": "access_token_here",
                        "refresh": "refresh_token_here"
                    }
                }
            ),
            400: "Bad Request"
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="User registration",
        request_body=RegisterSerializer,
        responses={
            201: openapi.Response(
                description="User created successfully",
                examples={
                    'application/json': {
                        "email": "johndoe@example.com",
                        "password": "password123",
                        "first_name": "John",
                        "last_name": "Doe",
                        "phone_number": "1234567890",
                        "address": "123 Main St, City, Country",
                        "role": "customer"
                    }
                }
            ),
            400: "Bad Request"
        }
    )
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        user = User.objects.get(email=request.data["email"])

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        domain = request.scheme + "://" + request.get_host()
        activation_link = f"{domain}/activate/{uidb64}/{token}/"

        message = render_to_string("account_activation_email.html", {
            "first_name": user.first_name or "there",
            "activation_link": activation_link,
            "current_year": datetime.now().year,
        })
        send_mail(
            "Activate Your YBS Account",
            "",
            "from@example.com",
            [user.email],
            html_message=message
        )

        return response


class ResendActivationEmailView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Resend account activation email",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL)
            }
        ),
        responses={
            200: openapi.Response(description="Activation email resent"),
            400: "Bad Request"
        }
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
        domain = request.scheme + "://" + request.get_host()
        activation_link = f"{domain}/activate/{uidb64}/{token}/"

        message = render_to_string("account_activation_email.html", {
            "first_name": user.first_name or "there",
            "activation_link": activation_link,
            "current_year": datetime.now().year,
        })
        send_mail(
            "Activate Your YBS Account - Resend",
            "",
            "from@example.com",
            [user.email],
            html_message=message
        )

        return Response({"message": "Activation email resent."}, status=status.HTTP_200_OK)


class ActivateAccountView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Activate user account",
        responses={
            200: openapi.Response(description="Account activated successfully"),
            400: openapi.Response(description="Invalid or expired activation link")
        }
    )
    def get(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Invalid activation link'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = True
        user.save()

        return Response({'message': 'Account activated successfully!'}, status=status.HTTP_200_OK)


class UserDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Retrieve the authenticated user's profile",
        responses={
            200: openapi.Response(
                description="Authenticated user's profile",
                examples={
                    'application/json': {
                        "id": 1,
                        "username": "johndoe",
                        "email": "johndoe@example.com",
                        "first_name": "John",
                        "last_name": "Doe"
                    }
                }
            ),
            403: "Forbidden"
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Update the authenticated user's profile",
        request_body=UserSerializer,
        responses={
            200: openapi.Response(
                description="Updated user profile",
                examples={
                    'application/json': {
                        "id": 1,
                        "username": "johndoe",
                        "email": "newemail@example.com",
                        "first_name": "John",
                        "last_name": "Doe"
                    }
                }
            ),
            400: "Bad Request"
        }
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    @swagger_auto_schema(
        operation_description="Prevent listing all users (security)",
        responses={403: "Forbidden"}
    )
    def list(self, request, *args, **kwargs):
        return Response({'detail': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

    @swagger_auto_schema(
        operation_description="Retrieve the authenticated user's profile",
        responses={
            200: openapi.Response(
                description="Authenticated user's profile",
                examples={
                    'application/json': {
                        "id": 1,
                        "username": "johndoe",
                        "email": "johndoe@example.com",
                        "first_name": "John",
                        "last_name": "Doe"
                    }
                }
            ),
            403: "Forbidden"
        }
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Update the authenticated user's profile",
        request_body=UserSerializer,
        responses={
            200: openapi.Response(
                description="Updated user profile",
                examples={
                    'application/json': {
                        "id": 1,
                        "username": "johndoe",
                        "email": "newemail@example.com",
                        "first_name": "John",
                        "last_name": "Doe"
                    }
                }
            ),
            400: "Bad Request"
        }
    )
    @action(detail=False, methods=['patch'], permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        user = self.request.user
        serializer = self.get_serializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Request a password reset email",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL)
            }
        ),
        responses={
            200: openapi.Response(
                description="Password reset email sent",
                examples={
                    'application/json': {
                        "message": "Password reset email sent."
                    }
                }
            ),
            400: "Bad Request"
        }
    )
    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "No user with this email found"}, status=status.HTTP_400_BAD_REQUEST)

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        domain = request.scheme + "://" + request.get_host()
        reset_link = f"{domain}/api/reset-password/{uidb64}/{token}/"

        subject = 'Password Reset'
        message = render_to_string('password_reset_email.html', {
            'reset_link': reset_link,
            'first_name': user.first_name or "User",
        })
        send_mail(subject, '', 'from@example.com', [email], html_message=message)

        return Response({"message": "Password reset email sent."}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Confirm password reset with token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'password': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD)
            }
        ),
        responses={
            200: openapi.Response(
                description="Password reset successful",
                examples={
                    'application/json': {
                        "message": "Password has been reset successfully."
                    }
                }
            ),
            400: "Bad Request"
        }
    )
    def post(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
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
