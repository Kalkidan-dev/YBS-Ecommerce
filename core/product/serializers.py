from rest_framework import serializers
from .models import Product, Favorite, Category, City, Review, ProductImage
from decimal import Decimal, ROUND_DOWN
from django.db.models import Avg
from django.conf import settings
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'uploaded_at']

class ProductImageNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['image']

class FavoriteSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = Favorite
        fields = ['id', 'user', 'product', 'product_id', 'created_at']
        extra_kwargs = {'user': {'read_only': True}}

    def create(self, validated_data):
        user = self.context['request'].user
        product_id = validated_data.get('product_id')

        logger.debug(f"Product ID: {product_id}")

        if not product_id:
            raise serializers.ValidationError("Product ID is required.")

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            logger.error(f"Product {product_id} does not exist.")
            raise serializers.ValidationError("Product does not exist.")

        if Favorite.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError("You have already favorited this product.")

        return Favorite.objects.create(user=user, product=product)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['created_at'] = instance.created_at.isoformat()
        return representation

class CategorySerializer(serializers.ModelSerializer):
    icon_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id", "name", "parent", "icon", "icon_url",
            "image", "image_url", "created_at", "subcategories"
        ]

    def get_icon_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.icon.url) if obj.icon and request else None

    def get_image_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if obj.image and request else None

    def get_subcategories(self, obj):
        return CategorySerializer(obj.subcategories.all(), many=True, context=self.context).data

    def validate_icon(self, value):
        allowed_extensions = [".png", ".jpg", ".jpeg"]
        if value and not any(value.name.lower().endswith(ext) for ext in allowed_extensions):
            raise serializers.ValidationError("Only PNG, JPG, and JPEG files are allowed.")
        return value

    def validate_image(self, value):
        allowed_extensions = [".png", ".jpg", ".jpeg"]
        if value and not any(value.name.lower().endswith(ext) for ext in allowed_extensions):
            raise serializers.ValidationError("Only PNG, JPG, and JPEG files are allowed.")
        return value

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id','name', 'region']

class ProductReviewListSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = Review
        fields = ['id', 'rating', 'comment', 'user', 'created_at']

class ProductSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='seller.first_name', read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
    city = CitySerializer(read_only=True)
    city_id = serializers.PrimaryKeyRelatedField(queryset=City.objects.all(), source='city', write_only=True)
    images = ProductImageSerializer(source='variant_images', many=True, read_only=True)
    variant_images = ProductImageNestedSerializer(many=True, write_only=True, required=False)

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
            'id', 'title', 'description', 'price', 'formatted_price', 'review_count', 'average_rating', 'converted_price', 'currency',
            'category', 'category_id', 'city', 'city_id', 'seller_name',
            'main_image', 'image_url', 'images', 'variant_images', 'created_at', 'is_favorited', 'status', 'status_display', 'reviews'
        ]
        read_only_fields = ['seller_name', 'created_at', 'formatted_price', 'converted_price', 'is_favorited']

    def get_average_rating(self, obj):
        avg_rating = obj.reviews.aggregate(Avg('rating'))['rating__avg']
        return round(avg_rating, 2) if avg_rating else 0

    def get_image_url(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.main_image.url) if obj.main_image and request else None

    def get_converted_price(self, obj):
        request = self.context.get('request')
        target_currency = request.query_params.get('currency', obj.currency)

        original_price = Decimal(obj.price)
        converted_price = obj.convert_price(target_currency)
        exchange_rate = Decimal(converted_price / original_price) if original_price else Decimal("1.0")

        return {
            "amount": float(converted_price.quantize(Decimal("0.01"), rounding=ROUND_DOWN)),
            "currency": target_currency,
            "exchange_rate": float(exchange_rate.quantize(Decimal("0.00001"), rounding=ROUND_DOWN))
        }

    def get_formatted_price(self, obj):
        return {
            "amount": float(obj.price),
            "currency": obj.currency,
            "formatted": f"{float(obj.price):.2f} {obj.currency}"
        }

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        user = request.user
        if user and user.is_authenticated:
            return obj.favorited_by.filter(user=user).exists()
        return False

    def validate(self, data):
        request = self.context.get('request')
        user = request.user
        if request.method in ['PUT', 'PATCH'] and hasattr(self, 'instance'):
            if self.instance.seller != user and not user.is_superuser:
                raise PermissionDenied("You do not have permission to modify this product.")
        if 'status' in data and data['status'] == 'sold' and not user.is_superuser:
            raise serializers.ValidationError("Only admins can mark a product as sold.")
        return data

    def create(self, validated_data):
        variant_images_data = validated_data.pop('variant_images', [])
        request = self.context.get('request')
        validated_data['owner'] = validated_data['seller'] = validated_data['user'] = request.user
        validated_data['currency'] = validated_data.get('currency', 'ETB')

        product = super().create(validated_data)
        for image_data in variant_images_data:
            ProductImage.objects.create(product=product, **image_data)
        return product

    def update(self, instance, validated_data):
        variant_images_data = validated_data.pop('variant_images', [])
        product = super().update(instance, validated_data)

        if variant_images_data:
            product.variant_images.all().delete()
            for image_data in variant_images_data:
                ProductImage.objects.create(product=product, **image_data)
        return product

class ReviewRatingSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'product', 'rating', 'comment', 'created_at', 'user']
        read_only_fields = ['user', 'created_at']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        product = validated_data.get('product')

        if not product:
            raise serializers.ValidationError("Product is required.")

        if Review.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError("You have already reviewed this product.")

        validated_data['user'] = user
        return super().create(validated_data)

class BulkCategoryUpdateSerializer(serializers.Serializer):
    category_ids = serializers.ListField(child=serializers.IntegerField())
    new_parent_id = serializers.IntegerField(required=False)

    def validate(self, data):
        if not data.get('category_ids'):
            raise serializers.ValidationError("You must specify at least one category ID.")
        return data
    
    # def update_categories(self):

    #     category_ids = self.validated_data.get('category_ids')
    #     new_parent_id = self.validated_data.get('new_parent_id')

    #     if new_parent_id:
    #         new_parent = Category.objects.get(id=new_parent_id)
    #         Category.objects.filter(id__in=category_ids).update(parent=new_parent)
    #     else:
    #         Category.objects.filter(id__in=category_ids).update(parent=None)
    
    #     return category_ids
    # def to_representation(self, instance):
    #     return {
    #         "message": "Categories updated successfully.",
    #         "updated_category_ids": instance
    #     }
    