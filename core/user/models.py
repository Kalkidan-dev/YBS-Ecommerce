import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.http import Http404


class UserManager(BaseUserManager):
    """Custom manager for User model without a username field."""

    def get_object_by_public_id(self, public_id):
        """Retrieve a user by their public UUID."""
        try:
            return self.get(public_id=public_id) 
        except (ObjectDoesNotExist, ValueError, TypeError):
            raise Http404

    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user."""
        if not email:
            raise ValueError("Users must have an email.")
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser (admin)."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if not password:
            raise ValueError("Superusers must have a password.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model for e-commerce with role-based access."""

    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('admin', 'Admin'),
    )

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Needed for Django admin
    is_superuser = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

    def is_customer(self):
        return self.role == 'customer'

    def is_vendor(self):
        return self.role == 'vendor'

    def is_admin(self):
        return self.role == 'admin'
