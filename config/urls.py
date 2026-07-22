from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/account/', include('app.account.urls')),
    path('api/v1/super-admin/', include('app.super_admin.urls')),
    path('api/v1/admin/', include('app.admin.urls')),
    path('api/v1/project-admin/', include('app.project_admin.urls')),
    path('api/v1/document-controller/', include('app.document_controller.urls')),
    path('api/v1/employee/', include('app.employee.urls')),
    path('api/v1/commercial/', include('app.commercial_department.urls')),
    path('api/v1/procurement/', include('app.procurement_department.urls')),
    path('api/v1/contracts-manager/', include('app.contracts_manager.urls')),
    path('api/v1/finance/', include('app.finance_department.urls')),
    
    # Swagger / OpenAPI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
