from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from .models import Product, Category, City, Favorite, Review
from .serializers import ProductSerializer, CategorySerializer, CitySerializer, FavoriteSerializer, ReviewRatingSerializer 
from django.core.mail import send_mail
from rest_framework.decorators import api_view, permission_classes
from django.conf import settings

import logging
import django_filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.exceptions import ValidationError, PermissionDenied
from ..user.permissions import IsAdminOrOwner
from rest_framework.pagination import PageNumberPagination


logger = logging.getLogger(__name__)

class IsAdminOrReadOnly(permissions.BasePermission):
    """Custom permission to allow only admin users to create/edit cities."""
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or request.user.is_staff

# City ViewSet
class CityViewSet(viewsets.ModelViewSet):  
    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'region']

# Category ViewSet
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]
    filter_backends = [OrderingFilter, DjangoFilterBackend, SearchFilter]
    filterset_fields = ['name']
    search_fields = ['name']
    ordering_fields = ['name']
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]  # Allow any user for GET requests
        elif self.request.method == 'POST':
            return [IsAdminUser()]  # Only allow admins to create
        return [IsAuthenticated()]  # For other methods, allow authenticated users


    def perform_create(self, serializer):
        serializer.save()
        cache.delete("categories")

    @action(detail=False, methods=['patch'], permission_classes=[IsAdminUser])
    def bulk_update(self, request):
        ids = request.data.get('ids', [])
        name = request.data.get('name')
        if not ids or not name:
            return Response({"detail": "Please provide valid IDs and a name."}, status=status.HTTP_400_BAD_REQUEST)
        categories = Category.objects.filter(id__in=ids)
        if not categories.exists():
            return Response({"detail": "No matching categories found."}, status=status.HTTP_404_NOT_FOUND)
        categories.update(name=name)
        cache.delete("categories")
        return Response({"detail": "Categories updated successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], permission_classes=[IsAdminUser])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"detail": "Please provide IDs to delete."}, status=status.HTTP_400_BAD_REQUEST)
        deleted_count, _ = Category.objects.filter(id__in=ids).delete()
        cache.delete("categories")
        return Response({"detail": f"{deleted_count} categories deleted successfully."}, status=status.HTTP_200_OK)

# Favorite ViewSet
class FavoriteViewSet(viewsets.ModelViewSet):
    queryset = Favorite.objects.all()
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete']

    @action(detail=False, methods=['post'], url_path='add')
    def add_favorite(self, request, *args, **kwargs):
        product_id = request.data.get('product_id')
        if not product_id:
            raise ValidationError({"error": "Product ID is required."})
        product = Product.objects.filter(id=product_id).first()
        if not product:
            raise ValidationError({"error": "Product does not exist."})
        if Favorite.objects.filter(user=request.user, product=product).exists():
            raise ValidationError({"error": "Product already favorited."})
        favorite = Favorite.objects.create(user=request.user, product=product)
        return Response(FavoriteSerializer(favorite).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['DELETE'])
    def remove(self, request, pk=None):
        favorite = Favorite.objects.filter(user=request.user, product_id=pk).first()
        if not favorite:
            return Response({"error": "Product not in favorites"}, status=status.HTTP_400_BAD_REQUEST)
        favorite.delete()
        return Response({"message": "Removed from favorites"}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='my')
    def my_favorites(self, request):
        favorites = Favorite.objects.filter(user=request.user)
        serializer = FavoriteSerializer(favorites, many=True)
        return Response(serializer.data)
    
# Product Filtering and Pagination
class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    category = django_filters.CharFilter(field_name="category__name", lookup_expr="iexact")

    class Meta:
        model = Product
        fields = ['category', 'min_price', 'max_price']

class ProductPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

# Product ViewSet
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category').prefetch_related('images').all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ProductPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = ProductFilter
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']
    search_fields = ['title', 'description']

    def get_queryset(self):
        cached_products = cache.get("products")
        if cached_products is None:
            products = list(Product.objects.select_related('category').all().values())
            cache.set("products", products, timeout=300)
        else:
            products = cached_products
        return Product.objects.filter(id__in=[p['id'] for p in products])

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(
                owner=self.request.user,
                seller=self.request.user,  
                user=self.request.user     
            )
            cache.delete("products")
        else:
            raise PermissionDenied("Authentication required to create a product.")

    def perform_update(self, serializer):
        if self.request.user == serializer.instance.owner:
            serializer.save()
            cache.delete("products")
        else:
            raise PermissionDenied("You are not the owner of this product.")

    def perform_destroy(self, instance):
        instance.delete()
        cache.delete("products")

# My Listings ViewSet
class MyListingsViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrOwner]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return Product.objects.all()
        if user.role == "vendor":
            return Product.objects.filter(seller=user)
        return Product.objects.none()


class ReviewPagination(PageNumberPagination):
    page_size = 10  
    page_size_query_param = 'page_size'
    max_page_size = 100

def send_review_notification(product_owner, review):
    
    subject = 'New Review Received!'
    message = f'{review.user} has left a new review on your product: {review.product.title}. Rating: {review.rating}\n\nComment: {review.comment}'
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [product_owner.email],  # Send to the product owner's email
        fail_silently=False,
    )

class ReviewRatingViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewRatingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ReviewPagination

    def get_queryset(self):
        product_id = self.request.query_params.get('product_id')
        if product_id:
            return Review.objects.filter(product_id=product_id)
        return Review.objects.all()

    def perform_create(self, serializer):
        # Automatically associate the user with the review
        review = serializer.save(user=self.request.user)
        # After saving the review, notify the product owner
        product_owner = review.product.user  # Get the product owner
        send_review_notification(product_owner, review)

    def create(self, request, *args, **kwargs):
        # Ensure that both product and rating are provided
        product_id = request.data.get('product')
        rating = request.data.get('rating')
        comment = request.data.get('comment')

        if not product_id or not rating:
            return Response({"error": "Product and rating are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure the rating is within the valid range
        if int(rating) < 1 or int(rating) > 5:
            return Response({"error": "Rating must be between 1 and 5."}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        review = self.get_object()
        if review.user != request.user and not request.user.is_staff:
            return Response({"error": "You can only update your own reviews."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        review = self.get_object()
        if review.user != request.user and not request.user.is_staff:
            return Response({"error": "You can only delete your own reviews."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def flag(self, request, pk=None):
        review = self.get_object()
        review.is_flagged = True
        review.save()
        return Response({"status": "Review flagged ✅"}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_email_view(request):
    subject = '🎉 Test Email from YBS Ecommerce'
    message = f'Hey {request.user.email}, this is a test email sent from YBS Ecommerce!'
    recipient = [request.user.email]  # Send the test email to the logged-in user
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipient,
        fail_silently=False,
    )

    return Response({"message": "✅ Email sent successfully!"})