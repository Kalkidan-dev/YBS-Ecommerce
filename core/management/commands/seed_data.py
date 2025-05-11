# core/management/commands/seed_data.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.product.models import City, Category, Product, Favorite, Review
from core.order.models import Order, OrderItem

User = get_user_model()

class Command(BaseCommand):
    help = "Seed the database with initial data"

    def handle(self, *args, **kwargs):
        # Users
        admin, _ = User.objects.get_or_create(
            email="admin@example.com",
            defaults={
                "first_name": "Admin",
                "last_name": "User",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
            }
        )
        admin.set_password("adminpass123")
        admin.save()

        vendor, _ = User.objects.get_or_create(
            email="vendor@example.com",
            defaults={"first_name": "Vendor", "last_name": "User", "role": "vendor"}
        )
        vendor.set_password("vendorpass123")
        vendor.save()

        customer, _ = User.objects.get_or_create(
            email="customer@example.com",
            defaults={"first_name": "Customer", "last_name": "User", "role": "customer"}
        )
        customer.set_password("customerpass123")
        customer.save()

        # Cities
        addis, _ = City.objects.get_or_create(name="Addis Ababa", region="Addis Ababa")
        dubai_city, _ = City.objects.get_or_create(name="Deira", defaults={"region": "Dubai"})


        # Categories
        electronics, _ = Category.objects.get_or_create(name="Electronics")
        phones, _ = Category.objects.get_or_create(name="Phones", parent=electronics)

        # Products
        product1, _ = Product.objects.get_or_create(
            title="iPhone 13",
            defaults={
                "description": "Latest iPhone model",
                "city": addis,
                "price": 1000,
                "currency": "USD",
                "category": phones,
                "owner": vendor,
                "seller": vendor,
                "user": vendor,
                "status": "active",
            }
        )

        product2, _ = Product.objects.get_or_create(
            title="Samsung Galaxy",
            defaults={
                "description": "Flagship Samsung phone",
                "city": dubai_city,
                "price": 900,
                "currency": "USD",
                "category": phones,
                "owner": vendor,
                "seller": vendor,
                "user": vendor,
                "status": "active",
            }
        )

        # Favorites
        Favorite.objects.get_or_create(user=customer, product=product1)

        # Reviews
        Review.objects.get_or_create(
            product=product1,
            user=customer,
            defaults={"rating": 5, "comment": "Excellent product!"}
        )

        # Orders and OrderItems
        order, _ = Order.objects.get_or_create(
            user=customer,
            shipping_address="Addis Ababa, Ethiopia",
            status="pending"
        )

        OrderItem.objects.get_or_create(order=order, product=product1, quantity=1, price=1000)
        OrderItem.objects.get_or_create(order=order, product=product2, quantity=2, price=900)

        # Recalculate order total
        order.calculate_total()

        self.stdout.write(self.style.SUCCESS("Successfully seeded database with sample data."))
