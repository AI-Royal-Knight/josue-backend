from django.urls import path

from .views import (
    Overview,
    CompaniesView,
    CompanyDetailView,
)

urlpatterns = [
    path('overview/', Overview.as_view(), name='Overview'),
    path('invite-admin/', CompaniesView.as_view(), name='Invite Admin'),
    path('companies/', CompaniesView.as_view(), name='Companies'),
    path('companies/<int:pk>/', CompanyDetailView.as_view(), name='Company Detail'),
]
