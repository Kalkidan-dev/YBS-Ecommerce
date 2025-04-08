from django.contrib import admin
from .models import Category, City, Product

class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'image']

class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'region']
    search_fields = ['name', 'region']

class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'city', 'price', 'seller', 'created_at']
    search_fields = ['title', 'category__name', 'city__name', 'seller__username']
    list_filter = ['category', 'city', 'created_at']
    ordering = ['-created_at']

admin.site.register(Category, CategoryAdmin)
admin.site.register(City, CityAdmin)
admin.site.register(Product, ProductAdmin)
