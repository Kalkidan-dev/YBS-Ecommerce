from rest_framework import serializers
from .models import Order, OrderItem
from core.product.models import Product
from core.product.serializers import ProductSerializer
from django.utils.translation import gettext_lazy as _


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    # quantity = serializers.IntegerField(min_value=1)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = OrderItem
        fields = ['product', 'product_id', 'quantity', 'price']
        read_only_fields = ['price']

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value


class OrderSerializer(serializers.ModelSerializer):
    # items = OrderItemSerializer(many=True, read_only=True)
    items = OrderItemSerializer(many=True)
    total_price = serializers.SerializerMethodField()
    shipping_address = serializers.CharField(max_length=255)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    # user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), write_only=True)


    class Meta:
        model = Order
        fields = ['id', 'user', 'status', 'created_at', 'updated_at', 'items', 'total_price', 'shipping_address']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'total_price']

    def get_total_price(self, obj):
        try:
            return sum(item.price * item.quantity for item in obj.items.all())
        except Exception:
            return 0
   
    
    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return serializers.OrderItemSerializer
        return self.serializer_class

    def _build_order_items(self, items_data, order):
        order_items = []
        for item_data in items_data:
            product = item_data.get('product')
            quantity = item_data.get('quantity')

            if not product or product.price is None:
                raise serializers.ValidationError(_("Invalid product or missing price."))

            order_items.append(OrderItem(
                order=order,
                product=product,
                quantity=quantity,
                price=product.price
            ))
        return order_items

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError(_("Order must include at least one item."))
        return value
    def validate(self, attrs):
        items_data = attrs.get('items', [])
        if not items_data:
            raise serializers.ValidationError(_("Order must include at least one item."))

        # Validate each item
        for item_data in items_data:
            product = item_data.get('product')
            quantity = item_data.get('quantity')

            if not product or product.price is None:
                raise serializers.ValidationError(_("Invalid product or missing price."))

            if quantity <= 0:
                raise serializers.ValidationError(_("Quantity must be greater than zero."))

        return attrs
    
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        if not user or not user.is_authenticated:
            raise serializers.ValidationError(_("User must be authenticated."))

        items_data = validated_data.pop('items', [])
        order = Order.objects.create(user=user, **validated_data)
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        return order

    def update(self, instance, validated_data):
        # Handle nested items on update: delete old and create new (simple approach)
        items_data = validated_data.pop('items', [])
        instance = super().update(instance, validated_data)
        if items_data:
            # Remove old items and re-create them
            instance.items.all().delete()
            for item_data in items_data:
                OrderItem.objects.create(order=instance, **item_data)
        return instance
    # def create(self, validated_data):
    #     request = self.context.get('request')
    #     user = request.user if request else None
    #     if not user or not user.is_authenticated:
    #         raise serializers.ValidationError(_("User must be authenticated."))

    #     items_data = validated_data.pop('items', None)
    #     if not items_data:
    #             raise serializers.ValidationError(_("Order must include at least one item."))

    #     validated_data.pop('user', None)

    #     order = Order.objects.create(user=user, **validated_data)
    #     order_items = self._build_order_items(items_data, order)
    #     OrderItem.objects.bulk_create(order_items)

    #     return order

    # def update(self, instance, validated_data):
    #     items_data = validated_data.pop('items', None)

    #     instance.status = validated_data.get('status', instance.status)
    #     instance.shipping_address = validated_data.get('shipping_address', instance.shipping_address)
    #     instance.save()

    #     if items_data:
    #         instance.items.all().delete()
    #         order_items = self._build_order_items(items_data, instance)
    #         OrderItem.objects.bulk_create(order_items)

    #     return instance
