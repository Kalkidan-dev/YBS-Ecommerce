from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, CategoryViewSet, FavoriteViewSet, MyListingsViewSet, CityViewSet, ReviewRatingViewSet
from .views import test_email_view


router = DefaultRouter()


router.register(r'', ProductViewSet, basename='product')  # This handles the products
router.register(r'categories', CategoryViewSet, basename='category')  # This handles categories

# Other registrations
router.register(r'cities', CityViewSet, basename='city')
router.register(r'favorites', FavoriteViewSet, basename='favorite')
router.register(r'my-listings', MyListingsViewSet, basename='my-listings')


router.register(r'reviews', ReviewRatingViewSet, basename='review')


urlpatterns = [
    path('', include(router.urls)),  # Include all router-generated URLs
    path('test-email/', test_email_view, name='test-email'),
]
