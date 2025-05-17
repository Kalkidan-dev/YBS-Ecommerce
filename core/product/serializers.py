from rest_framework import serializers
from django.db.models import Avg
from django.core.exceptions import PermissionDenied
from decimal import Decimal, ROUND_DOWN
from .models import Product, ProductImage, ProductVariant, Category, City, Review, Favorite
from .utils import validate_file_extension
import logging

logger = logging.getLogger(__name__)


# -------------------- Image & Variant Serializers --------------------

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'uploaded_at']

class ProductImageNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['image']

class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ['id', 'option_name', 'option_value']


# -------------------- Favorite Serializer --------------------

class FavoriteSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = Favorite
        fields = ['id', 'user', 'product', 'product_id', 'created_at']
        extra_kwargs = {'user': {'read_only': True}}

    def create(self, validated_data):
        user = self.context['request'].user
        product_id = validated_data.get('product_id')

        if not product_id:
            raise serializers.ValidationError("Product ID is required.")

        product = Product.objects.filter(id=product_id).first()
        if not product:
            logger.error(f"Product {product_id} does not exist.")
            raise serializers.ValidationError("Product does not exist.")

        if Favorite.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError("You have already favorited this product.")

        return Favorite.objects.create(user=user, product=product)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['created_at'] = instance.created_at.isoformat()
        return rep


# -------------------- Category Serializer --------------------

class CategorySerializer(serializers.ModelSerializer):
    icon_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "parent", "icon", "icon_url", "image", "image_url", "created_at", "subcategories"]

    def get_icon_url(self, obj):
        return self._get_image_url(obj.icon)

    def get_image_url(self, obj):
        return self._get_image_url(obj.image)

    def _get_image_url(self, file_field):
        request = self.context.get("request")
        return request.build_absolute_uri(file_field.url) if file_field and request else None

    def get_subcategories(self, obj):
        return CategorySerializer(obj.subcategories.all(), many=True, context=self.context).data

    def validate_icon(self, value):
        return validate_file_extension(value)

    def validate_image(self, value):
        return validate_file_extension(value)


# -------------------- City & Review Serializers --------------------

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name', 'region']

class ProductReviewListSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = Review
        fields = ['id', 'rating', 'comment', 'user', 'created_at']


# -------------------- Product Serializer --------------------

class ProductSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='seller.first_name', read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
    city = CitySerializer(read_only=True)
    city_id = serializers.PrimaryKeyRelatedField(queryset=City.objects.all(), source='city', write_only=True)

    images = ProductImageSerializer(source='variant_images', many=True, read_only=True)
    variant_images = ProductImageNestedSerializer(many=True, write_only=True, required=False)
    variants = ProductVariantSerializer(many=True, read_only=True)
    variant_data = ProductVariantSerializer(many=True, write_only=True, required=False)

    image_url = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    formatted_price = serializers.SerializerMethodField()
    converted_price = serializers.SerializerMethodField()
    currency = serializers.CharField(write_only=True)

    is_favorited = serializers.SerializerMethodField()
    review_count = serializers.IntegerField(source='reviews.count', read_only=True)
    average_rating = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviews = ProductReviewListSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'title', 'description', 'price', 'formatted_price', 'review_count', 'average_rating',
            'converted_price', 'currency', 'category', 'category_id', 'city', 'city_id', 'seller_name',
            'main_image', 'image_url', 'images', 'variant_images', 'variants', 'variant_data',
            'created_at', 'is_favorited', 'status', 'status_display', 'reviews'
        ]
        read_only_fields = ['seller_name', 'created_at', 'formatted_price', 'converted_price', 'is_favorited']

    def get_average_rating(self, obj):
        avg = obj.reviews.aggregate(Avg('rating'))['rating__avg']
        return round(avg, 2) if avg else 0

    def get_image_url(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.main_image.url) if obj.main_image and request else None

    def get_formatted_price(self, obj):
        return {
            "amount": float(obj.price),
            "currency": obj.currency,
            "formatted": f"{obj.price:.2f} {obj.currency}"
        }

    def get_converted_price(self, obj):
        request = self.context.get('request')
        target_currency = request.query_params.get('currency', obj.currency)
        original_price = Decimal(obj.price)

        converted_price = obj.convert_price(target_currency)
        exchange_rate = converted_price / original_price if original_price else Decimal("1.0")

        return {
            "amount": float(converted_price.quantize(Decimal("0.01"), rounding=ROUND_DOWN)),
            "currency": target_currency,
            "exchange_rate": float(exchange_rate.quantize(Decimal("0.00001"), rounding=ROUND_DOWN))
        }

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        user = request.user
        return user.is_authenticated and obj.favorited_by.filter(user=user).exists()

    def validate(self, data):
        user = self.context['request'].user
        if self.instance and self.instance.seller != user and not user.is_superuser:
            raise PermissionDenied("You do not have permission to modify this product.")

        if data.get('status') == 'sold' and not user.is_superuser:
            raise serializers.ValidationError("Only admins can mark a product as sold.")
        return data

    def _handle_nested_creation(self, product, variants, images):
        if images:
            ProductImage.objects.bulk_create([
                ProductImage(product=product, **img) for img in images
            ])
        if variants:
            ProductVariant.objects.bulk_create([
                ProductVariant(product=product, **var) for var in variants
            ])

    def create(self, validated_data):
        variant_images_data = validated_data.pop('variant_images', [])
        variant_data = validated_data.pop('variant_data', [])
        user = self.context['request'].user

        validated_data['seller'] = validated_data['user'] = validated_data['owner'] = user
        validated_data['currency'] = validated_data.get('currency', 'ETB')

        product = super().create(validated_data)
        self._handle_nested_creation(product, variant_data, variant_images_data)
        return product

    def update(self, instance, validated_data):
        variant_images_data = validated_data.pop('variant_images', [])
        variant_data = validated_data.pop('variant_data', [])

        product = super().update(instance, validated_data)
        if variant_images_data:
            product.variant_images.all().delete()
        if variant_data:
            product.variants.all().delete()

        self._handle_nested_creation(product, variant_data, variant_images_data)
        return product


# -------------------- Review Serializer --------------------

class ReviewRatingSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'product', 'rating', 'comment', 'created_at', 'user']
        read_only_fields = ['user', 'created_at']

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        product = validated_data['product']

        if Review.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError("You have already reviewed this product.")

        validated_data['user'] = user
        return super().create(validated_data)


# -------------------- Bulk Category Update --------------------

class BulkCategoryUpdateSerializer(serializers.Serializer):
    category_ids = serializers.ListField(child=serializers.IntegerField())
    new_parent_id = serializers.IntegerField(required=False)

    def validate(self, data):
        if not data.get('category_ids'):
            raise serializers.ValidationError("You must specify at least one category ID.")
        return data
