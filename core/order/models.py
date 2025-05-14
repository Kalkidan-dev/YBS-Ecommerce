from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from core.product.models import Product

User = get_user_model()


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('paid', 'Paid'),
    ]

    VALID_STATUS_TRANSITIONS = {
        'pending': ['confirmed', 'cancelled'],
        'confirmed': ['shipped', 'cancelled'],
        'shipped': ['delivered'],
        'delivered': [],
        'cancelled': [],
        'paid': [],  # Adjust as needed
    }

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_address = models.TextField()

    def __str__(self):
        return f"Order #{self.id} - {self.user.email}"

    def calculate_total(self):
        total = sum(item.get_total_price() for item in self.items.all())
        self.total_price = total
        self.save(update_fields=["total_price"])
        return total

    def clean(self):
        if self.pk:
            old_status = Order.objects.get(pk=self.pk).status
            allowed = self.VALID_STATUS_TRANSITIONS.get(old_status, [])
            if self.status != old_status and self.status not in allowed:
                raise ValidationError(f"Invalid status transition: {old_status} → {self.status}")

    def save(self, *args, **kwargs):
        self.full_clean()  # enforce clean() rules
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} × {self.product.title}"

    def get_total_price(self):
        return self.quantity * self.price

    get_total_price.short_description = "Item Total"
