from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FinanceSupplierInvoiceViewSet

router = DefaultRouter()
router.register(r'supplier-invoices', FinanceSupplierInvoiceViewSet, basename='finance-supplier-invoices')

urlpatterns = [
    path('', include(router.urls)),
]
