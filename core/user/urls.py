from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView, RegisterView, UserDetailView, UserViewSet

# Set up the router and register the UserViewSet
router = DefaultRouter()
router.register('users', UserViewSet, basename='user')

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view(), name='register'),
    path('me/', UserDetailView.as_view(), name='user_detail'),
    path('', include(router.urls)),  # This includes the 'update_profile' action automatically
]
