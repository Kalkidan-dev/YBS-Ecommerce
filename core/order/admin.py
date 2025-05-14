from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Order, OrderItem
import csv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price', 'get_total_price']
    can_delete = False

    def get_total_price(self, obj):
        return obj.get_total_price()
    get_total_price.short_description = _("Item Total")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'colored_status', 'total_price', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__email', 'status']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    readonly_fields = ['total_price', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    actions = ['export_as_csv', 'export_as_pdf', 'mark_as_shipped', 'mark_as_paid']
    fieldsets = (
        (None, {
            'fields': ('user', 'status', 'shipping_address')
        }),
        ('Financial', {
            'fields': ('total_price',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        obj.calculate_total()  # Ensure total_price is recalculated
        super().save_model(request, obj, form, change)

    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=orders.csv'
        writer = csv.writer(response)
        writer.writerow(['Order ID', 'User', 'Status', 'Total Price', 'Created At'])

        for order in queryset:
            writer.writerow([order.id, order.user.email, order.status, order.total_price, order.created_at])

        return response
    export_as_csv.short_description = _("Export Selected Orders to CSV")

    def export_as_pdf(self, request, queryset):
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        y = height - 50
        p.setFont("Helvetica", 12)
        p.drawString(200, y, _("Order Report"))

        y -= 40
        for order in queryset:
            if y < 100:
                p.showPage()
                y = height - 50
            p.drawString(50, y, f"Order #{order.id} | User: {order.user.email} | Status: {order.status} | Total: ${order.total_price}")
            y -= 20

        p.save()
        buffer.seek(0)
        return HttpResponse(buffer, content_type='application/pdf')
    export_as_pdf.short_description = _("Export Selected Orders to PDF")

    def colored_status(self, obj):
        color_map = {
            'pending': 'orange',
            'confirmed': 'blue',
            'shipped': 'purple',
            'delivered': 'green',
            'cancelled': 'red',
            'paid': 'darkgreen',
        }
        color = color_map.get(obj.status, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.status.capitalize())
    colored_status.short_description = _('Status')

    def mark_as_shipped(self, request, queryset):
        queryset.update(status='shipped')
        self.message_user(request, _("Selected orders have been marked as Shipped"))
    mark_as_shipped.short_description = _("Mark as Shipped")

    def mark_as_paid(self, request, queryset):
        queryset.update(status='paid')
        self.message_user(request, _("Selected orders have been marked as Paid"))
    mark_as_paid.short_description = _("Mark as Paid")


    def get_queryset(self, request):
        """
        Limit visibility based on user role.
        Only show orders for vendors (if they are logged in) and admins can see all.
        """
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            # Vendors can only see their own orders
            queryset = queryset.filter(user=request.user)
        return queryset


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'price', 'get_total_price']
    search_fields = ['order__user__email', 'product__title']
    list_filter = ['product__category', 'order__status']

    def get_total_price(self, obj):
        return obj.get_total_price()
    get_total_price.short_description = _("Item Total")
