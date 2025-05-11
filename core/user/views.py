from rest_framework import generics, status, viewsets, permissions
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from .serializers import CustomTokenObtainPairSerializer, UserSerializer, RegisterSerializer
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom view to use our serializer for JWT authentication."""
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
    """User Registration API View"""
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
        return super().post(request, *args, **kwargs)



class UserDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update the authenticated user's profile."""
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
    """Manage user profile actions"""
    
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Return the authenticated user's profile"""
        return self.request.user

    @swagger_auto_schema(
        operation_description="Prevent listing all users (security)",
        responses={403: "Forbidden"}
    )
    def list(self, request, *args, **kwargs):
        """Prevent listing all users"""
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
        """Retrieve the authenticated user's profile"""
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