from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Order, Product
from .serializers import OrderSerializer

@swagger_auto_schema(tags=["Orders"])
class OrderViewSet(viewsets.ModelViewSet):
    """
    This viewset provides actions to manage orders.
    Only authenticated users can perform these actions.
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    # def get_parsers(self):
    #     # Skip all parsers during swagger schema generation
    #     if getattr(self, 'swagger_fake_view', False):
    #         return []
    #     return super().get_parsers()

    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Order.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            return Order.objects.none()

        return Order.objects.filter(user=user)
    # @swagger_serializer_method(serializer_or_field=OrderItemSerializer(many=True))
    
    @swagger_auto_schema(request_body=OrderSerializer)
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


    @swagger_auto_schema(request_body=OrderSerializer)
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @swagger_auto_schema(
        responses={200: OrderSerializer(many=True)},
        operation_description="Get a list of orders for the authenticated user.",
        security=[{'Bearer': []}]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    
    @swagger_auto_schema(
        responses={200: OrderSerializer},
        operation_description="Retrieve the details of a specific order.",
        security=[{'Bearer': []}]
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        responses={204: "Order successfully deleted."},
        operation_description="Delete an order.",
        security=[{'Bearer': []}]
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    # @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    # @swagger_auto_schema(
    #     request_body=OrderSerializer,
    #     responses={200: OrderSerializer},
    #     operation_description="Update an existing order.",
    #     security=[{'Bearer': []}]
    # )
    # def update_order(self, request, pk=None):
    #     order = self.get_object()
    #     serializer = self.get_serializer(order, data=request.data, partial=True)
    #     if serializer.is_valid():
    #         if 'product' in request.data:
    #             product_id = request.data['product']
    #             try:
    #                 product = Product.objects.get(pk=product_id)
    #                 order.price = product.price
    #             except Product.DoesNotExist:
    #                 raise PermissionDenied("Invalid product selected.")
    #         serializer.save()
    #         return Response(serializer.data, status=200)
    # #     return Response(serializer.errors, status=400)

    # @swagger_auto_schema(
    #     request_body=OrderSerializer,
    #     responses={201: OrderSerializer},
    #     operation_description="Create a new order.",
    #     security=[{'Bearer': []}]
    # )
    # def perform_create(self, serializer):
    #     product = serializer.validated_data.get('product')
    #     if product:
    #         price = product.price
    #         serializer.save(user=self.request.user, price=price)
    #     else:
    #         raise PermissionDenied("You must select a valid product.")
        # serializer.save(user=self.request.user)