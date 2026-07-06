from django.urls import path
from .views import (
    ProfileView,
    LoginView,
    SendInvitationView,
    ValidateInvitationView,
    AcceptInvitationView,
    ForgotPasswordView,
    ResetPasswordView,
    SubmitApplicationView,
    UsersListView,
)

from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('login/', LoginView.as_view(), name='Login View'),
    path('refresh/', TokenRefreshView.as_view(), name='Token Refresh'),
    path('profile/', ProfileView.as_view(), name='Profile View'),
    path('submit-application/', SubmitApplicationView.as_view(), name='Submit Application'),
    path('users/', UsersListView.as_view(), name='Users List'),
    
    # Invitations
    path('invitations/send/', SendInvitationView.as_view(), name='Send Invitation'),
    path('invitations/validate/<uuid:token>/', ValidateInvitationView.as_view(), name='Validate Invitation'),
    path('invitations/accept/', AcceptInvitationView.as_view(), name='Accept Invitation'),

    # Password Reset
    path('forgot-password/', ForgotPasswordView.as_view(), name='Forgot Password'),
    path('reset-password/', ResetPasswordView.as_view(), name='Reset Password'),
]
