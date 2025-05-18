# utils/admin_exports.py
import csv
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def export_orders_to_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=orders.csv'
    writer = csv.writer(response)
    writer.writerow(['ID', 'User', 'Status', 'Total Price', 'Created At'])

    for order in queryset:
        writer.writerow([order.id, order.user.email, order.status, order.total_price, order.created_at])

    return response
export_orders_to_csv.short_description = "Export selected orders to CSV"

def export_orders_to_pdf(modeladmin, request, queryset):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=orders.pdf'

    p = canvas.Canvas(response, pagesize=letter)
    y = 750
    p.setFont("Helvetica-Bold", 12)
    p.drawString(30, y, "Order Report")
    y -= 30

    p.setFont("Helvetica", 10)
    for order in queryset:
        p.drawString(30, y, f"Order #{order.id} - {order.user.email} - {order.status} - ${order.total_price}")
        y -= 20
        if y <= 40:
            p.showPage()
            y = 750

    p.save()
    return response
export_orders_to_pdf.short_description = "Export selected orders to PDF"
def export_users_to_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=users.csv'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Email', 'First Name', 'Last Name', 'Role'])

    for user in queryset:
        writer.writerow([user.id, user.email, user.first_name, user.last_name, user.role])

    return response