from django.db import models
from django.conf import settings
from decimal import Decimal
import logging
from core.utils.currency import fetch_live_exchange_rate
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class City(models.Model):
    name = models.CharField(max_length=100, unique=True)
    region = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name}, {self.region}"


class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="subcategories"
    )
    icon = models.ImageField(upload_to="category_icons/", null=True, blank=True)
    image = models.ImageField(upload_to="category_images/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    CURRENCY_CHOICES = [
        ('ETB', 'Ethiopian Birr'),
        ('USD', 'US Dollar'),
        ('AED', 'UAE Dirham')
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('sold', 'Sold'),
        ('expired', 'Expired')
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='ETB')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")

    main_image = models.ImageField(upload_to="product_images/main/", null=True, blank=True)

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='products_owned')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="products_sold")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="products")

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.price} {self.currency} (Owner: {self.owner})"

    def convert_price(self, target_currency):
        if self.currency == target_currency or not self.price:
            return self.price

        exchange_rate = fetch_live_exchange_rate(target_currency)
        if exchange_rate == Decimal("1.0"):
            logger.warning(f"Exchange rate conversion skipped for product {self.id} as rate is 1.0")
            return self.price

        return round(self.price * exchange_rate, 2)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variant_images')
    image = models.ImageField(upload_to='product_images/variants/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Variant Image for {self.product.title}"


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    size = models.CharField(max_length=20, blank=True, null=True)
    color = models.CharField(max_length=30, blank=True, null=True)
    material = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Variant for {self.product.title} - {self.color}, {self.size}, {self.material}"


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.email} favorited {self.product.title}"


class Review(models.Model):
    product = models.ForeignKey(Product, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='reviews', on_delete=models.CASCADE)
    rating = models.IntegerField()
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_flagged = models.BooleanField(default=False)

    def __str__(self):
        return f"Review by {self.user.first_name} for {self.product.title}"
