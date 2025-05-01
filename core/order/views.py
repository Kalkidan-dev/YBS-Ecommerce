from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from .models import Order, Product
from .serializers import OrderSerializer

class OrderViewSet(viewsets.ModelViewSet):
    """
    This viewset provides actions to manage orders.
    It supports listing, retrieving, creating, updating, and deleting orders.
    Only authenticated users can perform these actions.
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        responses={200: OrderSerializer(many=True)},  # Example response with the serializer
        operation_description="Get a list of orders for the authenticated user."
    )
    def get_queryset(self):
        """
        This method filters orders for the authenticated user.
        If the user is not authenticated, a PermissionDenied exception is raised.
        """
        user = self.request.user
        if user.is_authenticated:
            # Return orders related to the authenticated user
            return Order.objects.filter(user=user)
        else:
            # If not authenticated, deny access to orders
            raise PermissionDenied("You must be authenticated to view orders.")

    @swagger_auto_schema(
        request_body=OrderSerializer,  # Example request body for creating an order
        responses={201: OrderSerializer},  # Example response when an order is created
        operation_description="Create a new order."
    )
    def perform_create(self, serializer):
        """
        This method automatically associates the authenticated user with the order 
        and sets the price from the selected product when the order is created.
        """
        product = serializer.validated_data.get('product')
        
        # Ensure the product exists and get its price
        if product:
            price = product.price  # Retrieve the price from the selected product
            serializer.save(user=self.request.user, price=price)
        else:
            raise PermissionDenied("You must select a valid product.")

    @swagger_auto_schema(
        responses={200: OrderSerializer},  # Example response for retrieving an order
        operation_description="Retrieve the details of a specific order."
    )
    def retrieve(self, request, *args, **kwargs):
        """
        This method is used to retrieve a specific order.
        """
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        responses={204: "Order successfully deleted."},  # Example response when an order is deleted
        operation_description="Delete an order."
    )
    def destroy(self, request, *args, **kwargs):
        """
        This method is used to delete a specific order.
        """
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    @swagger_auto_schema(
        request_body=OrderSerializer,
        responses={200: OrderSerializer},
        operation_description="Update an existing order."
    )
    def update_order(self, request, pk=None):
        """
        Custom action to update an order for the authenticated user.
        """
        order = self.get_object()
        serializer = self.get_serializer(order, data=request.data, partial=True)
        if serializer.is_valid():
            # Recalculate the price in case of product change
            if 'product' in request.data:
                product = request.data['product']
                price = product.price  # Get price from the product
                order.price = price  # Update the order price
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)
