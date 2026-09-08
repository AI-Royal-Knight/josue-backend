from django.urls import path
from .views import (
    SupplierInvitationDetailsView,
    SupplierInvitationAcceptView,
    SupplierInvitationDeclineView,
    SupplierAuthLoginView,
    SupplierCompanyListView,
    SupplierInvoiceListView,
    SupplierInvoiceDetailView,
    SupplierQuotationListView,
    SupplierQuotationDetailView,
)

urlpatterns = [
    # Public invitation endpoints
    path('invitations/<str:token>/', SupplierInvitationDetailsView.as_view(), name='supplier-invitation-details'),
    path('invitations/<str:token>/accept/', SupplierInvitationAcceptView.as_view(), name='supplier-invitation-accept'),
    path('invitations/<str:token>/decline/', SupplierInvitationDeclineView.as_view(), name='supplier-invitation-decline'),

    # Dedicated supplier auth
    path('auth/login/', SupplierAuthLoginView.as_view(), name='supplier-auth-login'),

    # Authenticated supplier company and invoice endpoints
    path('companies/', SupplierCompanyListView.as_view(), name='supplier-company-list'),
    path('invoices/', SupplierInvoiceListView.as_view(), name='supplier-invoice-list'),
    path('invoices/<uuid:pk>/', SupplierInvoiceDetailView.as_view(), name='supplier-invoice-detail'),

    # Authenticated supplier quotations / RFQs
    path('quotations/', SupplierQuotationListView.as_view(), name='supplier-quotation-list'),
    path('quotations/<str:pk>/', SupplierQuotationDetailView.as_view(), name='supplier-quotation-detail'),
]
