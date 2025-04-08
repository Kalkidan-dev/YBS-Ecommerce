from rest_framework import generics, status, viewsets, permissions
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from .serializers import CustomTokenObtainPairSerializer, UserSerializer, RegisterSerializer

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom view to use our serializer for JWT authentication."""
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    """User Registration API View"""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class UserDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update the authenticated user's profile."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserViewSet(viewsets.ModelViewSet):
    """Manage user profile actions"""
    
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Return the authenticated user's profile"""
        return self.request.user

    def list(self, request, *args, **kwargs):
        """Prevent listing all users (security)"""
        return Response({'detail': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve authenticated user's profile"""
        user = self.request.user
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    
    @action(detail=False, methods=['patch'], permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        user = self.request.user
        serializer = self.get_serializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)  
        return Response(serializer.errors, status=400)
