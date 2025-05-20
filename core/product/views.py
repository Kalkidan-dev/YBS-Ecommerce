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
import json
from django.db import transaction
from .models import Product, Category, City, Favorite, Review, ProductVariant, ProductImage
from .serializers import (
    ProductSerializer,
    CategorySerializer,
    CitySerializer,
    FavoriteSerializer,
    ReviewRatingSerializer,
    ProductVariantSerializer, SubCategorySerializer
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
# class SubCategoryListView(viewsets.ModelViewSet):
#     queryset = Category.objects.exclude(parent=None)  # only subcategories
#     serializer_class = SubCategorySerializer

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().prefetch_related('subcategories')
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['name']
    search_fields = ['name']
    ordering_fields = ['name']
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_context(self):
        # Pass request to serializer for full URLs
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    @swagger_auto_schema(operation_summary="Create a new category")
    def perform_create(self, serializer):
        serializer.save()
        cache.delete("categories")

    @swagger_auto_schema(
    operation_summary="Bulk update categories' name",
    tags=["Categories"],
    consumes=['multipart/form-data'],      # ← now form-data
    request_body=None,                     # ← disable Schema
    manual_parameters=[
            openapi.Parameter(
                'ids',
                openapi.IN_FORM,
                description="List of category IDs",
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_INTEGER),
                required=True
            ),
            openapi.Parameter(
                'name',
                openapi.IN_FORM,
                description="New name for selected categories",
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
        responses={200: openapi.Response('Categories updated successfully')}
    )
    @action(detail=False, methods=['patch'], permission_classes=[permissions.IsAdminUser])
    def bulk_update(self, request):
        ids = request.data.get('ids', [])
        if isinstance(ids, str):
            ids = [int(i) for i in ids.split(',') if i.strip().isdigit()]
        name = request.data.get('name')

        if not ids or not name:
            return Response({"detail": "Please provide valid IDs and a name."}, status=status.HTTP_400_BAD_REQUEST)

        categories = Category.objects.filter(id__in=ids)
        if not categories.exists():
            return Response({"detail": "No matching categories found."}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            categories.update(name=name)
            cache.delete("categories")

        return Response({"detail": "Categories updated successfully."})

    @swagger_auto_schema(
        method='delete',
        operation_summary="Bulk delete categories",
        tags=["Categories"],
        manual_parameters=[
            openapi.Parameter(
                'ids', openapi.IN_FORM,
                description="List of category IDs to delete",
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_INTEGER),
                required=True
            )
        ],
        responses={200: openapi.Response('Categories deleted successfully')}
    )
    @action(detail=False, methods=['delete'], permission_classes=[permissions.IsAdminUser])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if isinstance(ids, str):
            ids = [int(i) for i in ids.split(',') if i.strip().isdigit()]

        if not ids:
            return Response({"detail": "Please provide IDs to delete."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
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
        tags=["Favorites"],
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

    @swagger_auto_schema(method='delete', operation_summary="Remove a product from favorites", tags=["Favorites"])
    @action(detail=True, methods=['delete'])
    def remove(self, request, pk=None):
        favorite = Favorite.objects.filter(user=request.user, product_id=pk).first()
        if not favorite:
            return Response({"error": "Product not in favorites"}, status=status.HTTP_400_BAD_REQUEST)
        favorite.delete()
        return Response({"message": "Removed from favorites"}, status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(method='get', operation_summary="List my favorite products", tags=["Favorites"])
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

   
    @swagger_auto_schema(
    tags=["Products"],
    operation_summary="Update product variants with images",
    consumes=['multipart/form-data'],
    request_body=None,               # ← important: stop auto-generating a schema
    manual_parameters=[
            openapi.Parameter(
                name='variant_data',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=True,
                description=(
                  'JSON string of variants; ex: '
                  '[{"option_name":"Color","option_value":"Red","stock":10}, …]'
                )
            ),
            openapi.Parameter(
                name='variant_images_meta',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False,
                description=(
                  'JSON mapping of image indexes to option_value; ex: '
                  '[{"index":0,"option_value":"Red"}, …]'
                )
            ),
            *[
                openapi.Parameter(
                    name=f'variant_images_{i}',
                    in_=openapi.IN_FORM,
                    type=openapi.TYPE_FILE,
                    required=False,
                    description=f'Image file #{i+1} for a variant'
                ) for i in range(5)
            ]
        ],
        responses={
            200: openapi.Response(
                description="Variants updated",
                examples={
                    "application/json": {
                        "message": "Variants updated",
                        "variants": [
                            {"id":1,"option_name":"Color","option_value":"Red","stock":10}
                        ]
                    }
                }
            )
        }
    )
    @action(
        detail=True,
        methods=['patch'],
        parser_classes=[MultiPartParser, FormParser],
        url_path='update-variants'
    )
    
    def update_variants(self, request, pk=None):
        """
        PATCH /products/{id}/update-variants/

        Accepts:
        - variant_data: JSON stringified list of variants (option_name, option_value, stock)
        - variant_images_meta: JSON list mapping image indexes to option_value
        - variant_images_0, variant_images_1, ... : image files
        """
        product = self.get_object()

        try:
            variant_data = json.loads(request.data.get('variant_data', '[]'))
            variant_images_meta = json.loads(request.data.get('variant_images_meta', '[]'))
        except json.JSONDecodeError:
            return Response({'error': 'Invalid JSON in variant_data or variant_images_meta'}, status=400)

        saved_variants = []
        for variant in variant_data:
            obj, _ = ProductVariant.objects.update_or_create(
                product=product,
                option_name=variant.get('option_name'),
                option_value=variant.get('option_value'),
                defaults={'stock': variant.get('stock', 0)},
            )
            saved_variants.append(obj)

        for meta in variant_images_meta:
            index = meta.get('index')
            option_value = meta.get('option_value')
            image_file = request.FILES.get(f'variant_images_{index}')
            if image_file:
                variant_match = ProductVariant.objects.filter(product=product, option_value=option_value).first()
                if variant_match:
                    ProductImage.objects.create(product=product, image=image_file)

        serialized = ProductVariantSerializer(saved_variants, many=True)
        return Response({
            "message": "Variants updated",
            "variants": serialized.data
        }, status=status.HTTP_200_OK)


    @swagger_auto_schema(operation_summary="Create a product", request_body=ProductSerializer)
    def perform_create(self, serializer):
            if not self.request.user.is_authenticated:
                raise PermissionDenied("Authentication required to create a product.")
            serializer.save(owner=self.request.user, seller=self.request.user, user=self.request.user)
            cache.delete("products")
            logger.info(f"Product {serializer.instance.title} created by {self.request.user.email}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(operation_summary="Update a product")
    def perform_update(self, serializer):
        if self.request.user != serializer.instance.seller:
            raise PermissionDenied("You are not the owner of this product.")
        serializer.save()
        cache.delete("products")
        logger.info(f"Product {serializer.instance.title} updated by {self.request.user.email}")
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.user != instance.vendor and not request.user.is_staff:
            return Response({"detail": "You do not have permission to edit this product."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)
    
    @swagger_auto_schema(operation_summary="Delete a product")
    def perform_destroy(self, instance):
        instance.delete()
        cache.delete("products")
        logger.info(f"Product {instance.title} deleted by {self.request.user.email}")
        return Response({"detail": "Product deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

# ---------------- My Listings ViewSet ----------------

class MyListingsViewSet(viewsets.ModelViewSet):
        serializer_class = ProductSerializer
        permission_classes = [IsAdminOrOwner]

        def get_queryset(self):
            # Fix schema generation errors in Swagger
            if getattr(self, 'swagger_fake_view', False):
                return Product.objects.none()

            user = self.request.user
            if not user.is_authenticated:
                return Product.objects.none()

            if hasattr(user, 'role'):
                if user.role == "admin":
                    return Product.objects.all()
                if user.role == "vendor":
                    return Product.objects.filter(seller=user)

            return Product.objects.none()

# ---------------- Review Notification Utility ----------------

def send_review_notification(product_owner, review):
    try:
        user = review.user.get_full_name() or str(review.user)
        product = review.product.title

        subject = 'New Review Received!'
        message = (
            f'{user} has left a new review on your product: {product}.\n'
            f'Rating: {review.rating}\n\nComment: {review.comment}'
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [product_owner.email], fail_silently=False)

    except Exception as e:
        print("Notification failed:", e)

# ---------------- Review Rating ViewSet ----------------

class ReviewRatingViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewRatingSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ReviewPagination

    def get_queryset(self):
        # Avoid errors during schema generation by short-circuiting if swagger_fake_view is set or request is None
        if getattr(self, 'swagger_fake_view', False) or self.request is None:
            return Review.objects.none()

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
        send_review_notification(review.review)


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
