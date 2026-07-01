from django.urls import path

from .views import (
    Overview,
    CompaniesView,
    CompanyDetailView,
    ValidateCompanyInvitationView,
    AcceptCompanyInvitationView,
    MonthlyInvoiceView,
)

urlpatterns = [
    path('overview/', Overview.as_view(), name='Overview'),
    path('invite-admin/', CompaniesView.as_view(), name='Invite Admin'),
    path('companies/', CompaniesView.as_view(), name='Companies'),
    path('companies/<uuid:pk>/', CompanyDetailView.as_view(), name='Company Detail'),
    path('invitations/validate/<uuid:token>/', ValidateCompanyInvitationView.as_view(), name='Validate Company Invitation'),
    path('invitations/accept/', AcceptCompanyInvitationView.as_view(), name='Accept Company Invitation'),
    path('invoices/', MonthlyInvoiceView.as_view(), name='Monthly Invoices'),
]
