from rest_framework import serializers
from django.db.models import Avg
from django.core.exceptions import PermissionDenied
from decimal import Decimal, ROUND_DOWN
from django.utils.translation import gettext_lazy as _
from .models import Product, ProductImage, ProductVariant, Category, City, Review, Favorite
from .utils import validate_file_extension
import logging

logger = logging.getLogger(__name__)

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'uploaded_at']

class ProductImageNestedSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)  # Include id for update matching

    class Meta:
        model = ProductImage
        fields = ['id', 'image']

class ProductVariantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)  # Include id for update matching

    class Meta:
        model = ProductVariant
        fields = ['id', 'option_name', 'option_value', 'stock']

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
            raise serializers.ValidationError(_("رقم المنتج مطلوب."))  # Arabic: "Product ID is required."

        product = Product.objects.filter(id=product_id).first()
        if not product:
            logger.error(f"Product {product_id} does not exist.")
            raise serializers.ValidationError(_("المنتج غير موجود."))  # "Product does not exist."

        if Favorite.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError(_("لقد قمت بإضافة هذا المنتج إلى المفضلة من قبل."))  # "You have already favorited this product."

        return Favorite.objects.create(user=user, product=product)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['created_at'] = instance.created_at.isoformat()
        return rep

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

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name', 'region']

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
        target_currency = request.query_params.get('currency', obj.currency) if request else obj.currency
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
        user = request.user if request else None
        return user.is_authenticated and obj.favorited_by.filter(user=user).exists() if user else False

    def validate(self, data):
        user = self.context['request'].user
        if self.instance and self.instance.seller != user and not user.is_superuser:
            raise PermissionDenied(_("ليس لديك الإذن لتعديل هذا المنتج."))  # Arabic: "You do not have permission to modify this product."

        if data.get('status') == 'sold' and not user.is_superuser:
            raise serializers.ValidationError(_("فقط المسؤولين يمكنهم وضع المنتج على أنه تم بيعه."))  # "Only admins can mark a product as sold."
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

    def _handle_nested_update(self, product, variants_data, images_data):
        """
        Handle partial update of nested variant_images and variants with these rules:
        - Update existing by ID
        - Create new without ID
        - Delete those not included (sync)
        """

        # --- VARIANT IMAGES ---
        existing_images = {img.id: img for img in product.variant_images.all()}
        received_image_ids = []

        for image_data in images_data:
            image_id = image_data.get('id', None)
            if image_id and image_id in existing_images:
                # Update existing
                img_obj = existing_images[image_id]
                img_obj.image = image_data.get('image', img_obj.image)
                img_obj.save()
                received_image_ids.append(image_id)
            else:
                # Create new
                ProductImage.objects.create(product=product, **image_data)

        # Delete images not in received list
        images_to_delete = [img for id_, img in existing_images.items() if id_ not in received_image_ids]
        for img in images_to_delete:
            img.delete()

        # --- VARIANTS ---
        existing_variants = {var.id: var for var in product.variants.all()}
        received_variant_ids = []

        for variant_data in variants_data:
            variant_id = variant_data.get('id', None)
            if variant_id and variant_id in existing_variants:
                var_obj = existing_variants[variant_id]
                var_obj.option_name = variant_data.get('option_name', var_obj.option_name)
                var_obj.option_value = variant_data.get('option_value', var_obj.option_value)
                var_obj.stock = variant_data.get('stock', var_obj.stock)
                var_obj.save()
                received_variant_ids.append(variant_id)
            else:
                ProductVariant.objects.create(product=product, **variant_data)

        # Delete variants not in received list
        variants_to_delete = [var for id_, var in existing_variants.items() if id_ not in received_variant_ids]
        for var in variants_to_delete:
            var.delete()

    def create(self, validated_data):
        variant_images_data = validated_data.pop('variant_images', [])
        variant_data = validated_data.pop('variant_data', [])
        user = self.context['request'].user

        validated_data['seller'] = user
        validated_data['currency'] = validated_data.get('currency', 'ETB')

        product = super().create(validated_data)

        # Bulk create nested images and variants
        self._handle_nested_creation(product, variant_data, variant_images_data)
        return product

    def update(self, instance, validated_data):
        variant_images_data = validated_data.pop('variant_images', None)
        variant_data = validated_data.pop('variant_data', None)

        instance = super().update(instance, validated_data)

        # If nested data provided, handle update with partial syncing
        if variant_images_data is not None:
            self._handle_nested_update(instance, variant_data or [], variant_images_data)

        elif variant_data is not None:
            # If only variant_data provided (no images), update variants accordingly
            self._handle_nested_update(instance, variant_data, [])

        return instance

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

class BulkCategoryUpdateSerializer(serializers.Serializer):
    category_ids = serializers.ListField(child=serializers.IntegerField())
    new_parent_id = serializers.IntegerField(required=False)

    def validate(self, data):
        if not data.get('category_ids'):
            raise serializers.ValidationError("You must specify at least one category ID.")
        return data
