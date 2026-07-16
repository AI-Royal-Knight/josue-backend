from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import ParsePOPDFView, GenerateBrandedPOPDFView

router = DefaultRouter()
router.register(r'quotations', views.QuotationViewSet, basename='quotation')

urlpatterns = [
    path('suppliers/', views.SupplierListView.as_view(), name='supplier-list'),
    path('suppliers/invite/', views.SupplierInviteView.as_view(), name='supplier-invite'),
    path('projects/', views.ProcurementProjectListView.as_view(), name='procurement-projects'),
    path('po/parse-pdf/', ParsePOPDFView.as_view(), name='po-parse-pdf'),
    path('po/generate-pdf/', GenerateBrandedPOPDFView.as_view(), name='po-generate-pdf'),
    path('', include(router.urls)),
]
