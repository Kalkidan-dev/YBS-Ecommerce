from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import django_filters
import logging

from .models import Product, Category, City, Favorite, Review
from .serializers import (
    ProductSerializer,
    CategorySerializer,
    CitySerializer,
    FavoriteSerializer,
    ReviewRatingSerializer,
)
from ..user.permissions import IsAdminOrOwner

logger = logging.getLogger(__name__)

# ---------------- Custom Permissions ----------------

class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or request.user.is_staff

# ---------------- Pagination Classes ----------------

class ProductPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ReviewPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

# ---------------- Filters ----------------

class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    category = django_filters.CharFilter(field_name="category__name", lookup_expr="iexact")

    class Meta:
        model = Product
        fields = ['category', 'min_price', 'max_price']

# ---------------- City ViewSet ----------------

class CityViewSet(viewsets.ModelViewSet):
    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'region']

# ---------------- Category ViewSet ----------------

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['name']
    search_fields = ['name']
    ordering_fields = ['name']
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(operation_summary="Create a new category")
    def perform_create(self, serializer):
        serializer.save()
        cache.delete("categories")

    @swagger_auto_schema(
        method='patch',
        operation_summary="Bulk update categories",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER)),
                'name': openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=['ids', 'name'],
        ),
        responses={200: openapi.Response('Categories updated successfully')}
    )
    @action(detail=False, methods=['patch'], permission_classes=[permissions.IsAdminUser])
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
        return Response({"detail": "Categories updated successfully."})

    @swagger_auto_schema(
        method='delete',
        operation_summary="Bulk delete categories",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER)),
            },
            required=['ids'],
        ),
        responses={200: openapi.Response('Categories deleted successfully')}
    )
    @action(detail=False, methods=['delete'], permission_classes=[permissions.IsAdminUser])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"detail": "Please provide IDs to delete."}, status=status.HTTP_400_BAD_REQUEST)
        deleted_count, _ = Category.objects.filter(id__in=ids).delete()
        cache.delete("categories")
        return Response({"detail": f"{deleted_count} categories deleted successfully."})

# ---------------- Favorite ViewSet ----------------

class FavoriteViewSet(viewsets.ModelViewSet):
    queryset = Favorite.objects.all()
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete']

    @swagger_auto_schema(
        method='post',
        operation_summary="Add a product to favorites",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'product_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the product to favorite'),
            },
            required=['product_id'],
        ),
        responses={201: FavoriteSerializer}
    )
    @action(detail=False, methods=['post'], url_path='add')
    def add_favorite(self, request):
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

    @swagger_auto_schema(
        method='delete',
        operation_summary="Remove a product from favorites"
    )
    @action(detail=True, methods=['delete'])
    def remove(self, request, pk=None):
        favorite = Favorite.objects.filter(user=request.user, product_id=pk).first()
        if not favorite:
            return Response({"error": "Product not in favorites"}, status=status.HTTP_400_BAD_REQUEST)
        favorite.delete()
        return Response({"message": "Removed from favorites"}, status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        method='get',
        operation_summary="List my favorite products"
    )
    @action(detail=False, methods=['get'], url_path='my')
    def my_favorites(self, request):
        favorites = Favorite.objects.filter(user=request.user)
        serializer = FavoriteSerializer(favorites, many=True)
        return Response(serializer.data)

# ---------------- Product ViewSet ----------------

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category').prefetch_related('variant_images', 'variants').all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = ProductPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_class = ProductFilter
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']
    search_fields = ['title', 'description']

    def get_queryset(self):
        cached_products = cache.get("products")
        if cached_products is None:
            products = list(Product.objects.select_related('category').all().values('id'))
            cache.set("products", products, timeout=300)
        else:
            products = cached_products
        return Product.objects.filter(id__in=[p['id'] for p in products])

    @swagger_auto_schema(operation_summary="Create a product")
    def perform_create(self, serializer):
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Authentication required to create a product.")
        serializer.save(owner=self.request.user, seller=self.request.user, user=self.request.user)
        cache.delete("products")

    @swagger_auto_schema(operation_summary="Update a product")
    def perform_update(self, serializer):
        if self.request.user != serializer.instance.owner:
            raise PermissionDenied("You are not the owner of this product.")
        serializer.save()
        cache.delete("products")

    @swagger_auto_schema(operation_summary="Delete a product")
    def perform_destroy(self, instance):
        instance.delete()
        cache.delete("products")

# ---------------- My Listings ViewSet ----------------

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

# ---------------- Review Notification Utility ----------------

def send_review_notification(product_owner, review):
    subject = 'New Review Received!'
    message = (
        f'{review.user} has left a new review on your product: {review.product.title}.\n'
        f'Rating: {review.rating}\n\nComment: {review.comment}'
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [product_owner.email], fail_silently=False)

# ---------------- Review Rating ViewSet ----------------

class ReviewRatingViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewRatingSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ReviewPagination

    def get_queryset(self):
        product_id = self.request.query_params.get('product_id')
        if product_id:
            return Review.objects.filter(product_id=product_id)
        return Review.objects.all()

    @swagger_auto_schema(
        operation_summary="Create a review with rating",
        request_body=ReviewRatingSerializer,
        responses={201: ReviewRatingSerializer}
    )
    def create(self, request, *args, **kwargs):
        product_id = request.data.get('product')
        rating = request.data.get('rating')

        if product_id is None or rating is None:
            return Response({"error": "Product and rating are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rating = int(rating)
        except (ValueError, TypeError):
            return Response({"error": "Rating must be a number."}, status=status.HTTP_400_BAD_REQUEST)

        if not (1 <= rating <= 5):
            return Response({"error": "Rating must be between 1 and 5."}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        review = serializer.save(user=self.request.user)
        send_review_notification(review.product.user, review)

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

    @swagger_auto_schema(
        methods=['post'],
        operation_summary="Flag a review"
    )
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def flag(self, request, pk=None):
        review = self.get_object()
        review.is_flagged = True
        review.save()
        return Response({"status": "Review flagged ✅"}, status=status.HTTP_200_OK)

# ---------------- Email Test Endpoint ----------------

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(operation_summary="Send a test email to the authenticated user")
def test_email_view(request):
    subject = '🎉 Test Email from YBS Ecommerce'
    message = f'Hey {request.user.email}, this is a test email sent from YBS Ecommerce!'
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [request.user.email], fail_silently=False)
    return Response({"message": "✅ Email sent successfully!"})
