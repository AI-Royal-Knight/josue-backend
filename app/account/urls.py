from django.urls import path
from .views import (
    ProfileView,
    LoginView,
    SendInvitationView,
    ValidateInvitationView,
    AcceptInvitationView
)

urlpatterns = [
    path('login/', LoginView.as_view(), name='Login View'),
    path('profile/', ProfileView.as_view(), name='Profile View'),
    
    # Invitations
    path('invitations/send/', SendInvitationView.as_view(), name='Send Invitation'),
    path('invitations/validate/<uuid:token>/', ValidateInvitationView.as_view(), name='Validate Invitation'),
    path('invitations/accept/', AcceptInvitationView.as_view(), name='Accept Invitation'),
]
