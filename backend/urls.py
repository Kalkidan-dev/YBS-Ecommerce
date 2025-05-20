from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from core.user.views import ActivateAccountView  # keep if used

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
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path('admin/', admin.site.urls) if settings.DEBUG else path('secure-admin/', admin.site.urls),

    path('api/', include('core.user.urls')),
    path('api/product/', include('core.product.urls')),
    path('api/order/', include('core.order.urls')),
    path('', include('core.urls')),

   
    path('api/user/activate/<uidb64>/<token>/', ActivateAccountView.as_view(), name='activate-account'),

    # Swagger Docs
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='swagger-json'),
    path('swagger.yaml', schema_view.without_ui(cache_timeout=0), name='swagger-yaml'),
    path('docs/', schema_view.with_ui('swagger', cache_timeout=10), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('openapi.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
