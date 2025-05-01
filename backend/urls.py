from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Initialize the API documentation view
schema_view = get_schema_view(
   openapi.Info(
      title="YBS Ecommerce API",
      default_version='v1',
      description="Test API documentation for YBS Ecommerce",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="cakek433@gmail.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.user.urls')), 
    path('api/product/', include('core.product.urls')),
    path('api/order/', include('core.order.urls')),
    path('', include('core.urls')),
    
    # API Documentation path
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='swagger-docs'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
