from rest_framework import serializers
from .models import Order, OrderItem
from core.product.models import Product
from core.product.serializers import ProductSerializer
from django.utils.translation import gettext_lazy as _


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
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
    items = OrderItemSerializer(many=True)
    total_price = serializers.SerializerMethodField()
    shipping_address = serializers.CharField(max_length=255)

    class Meta:
        model = Order
        fields = ['id', 'user', 'status', 'created_at', 'updated_at', 'items', 'total_price', 'shipping_address']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'total_price']

    def get_total_price(self, obj):
        return sum(item.price * item.quantity for item in obj.items.all())

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        user = self.context['request'].user
        validated_data.pop('user', None)

        order = Order.objects.create(user=user, **validated_data)

        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            price = product.price
            OrderItem.objects.create(order=order, product=product, quantity=quantity, price=price)

        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        instance.status = validated_data.get('status', instance.status)
        instance.shipping_address = validated_data.get('shipping_address', instance.shipping_address)
        instance.save()

        if items_data:
            instance.items.all().delete()
            for item_data in items_data:
                product = item_data['product']
                quantity = item_data['quantity']
                price = product.price
                OrderItem.objects.create(order=instance, product=product, quantity=quantity, price=price)

        return instance
