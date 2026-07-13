from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'quotations', views.QuotationViewSet, basename='quotation')

urlpatterns = [
    path('suppliers/', views.SupplierListView.as_view(), name='supplier-list'),
    path('suppliers/invite/', views.SupplierInviteView.as_view(), name='supplier-invite'),
    path('projects/', views.ProcurementProjectListView.as_view(), name='procurement-projects'),
    path('', include(router.urls)),
]
