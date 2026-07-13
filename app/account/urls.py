from django.urls import path
from .views import (
    ProfileView,
    LoginView,
    LogoutView,
    SendInvitationView,
    ValidateInvitationView,
    AcceptInvitationView,
    ForgotPasswordView,
    ResetPasswordView,
    ChangePasswordView,
    SubmitApplicationView,
    UsersListView,
    NotificationListView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    RequestAdminView,
)

from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('login/', LoginView.as_view(), name='Login View'),
    path('logout/', LogoutView.as_view(), name='Logout View'),
    path('refresh/', TokenRefreshView.as_view(), name='Token Refresh'),
    path('profile/', ProfileView.as_view(), name='Profile View'),
    path('submit-application/', SubmitApplicationView.as_view(), name='Submit Application'),
    path('request-admin/', RequestAdminView.as_view(), name='Request Admin'),
    path('users/', UsersListView.as_view(), name='Users List'),
    
    # Invitations
    path('invitations/send/', SendInvitationView.as_view(), name='Send Invitation'),
    path('invitations/validate/<uuid:token>/', ValidateInvitationView.as_view(), name='Validate Invitation'),
    path('invitations/accept/', AcceptInvitationView.as_view(), name='Accept Invitation'),

    # Password Reset
    path('forgot-password/', ForgotPasswordView.as_view(), name='Forgot Password'),
    path('reset-password/', ResetPasswordView.as_view(), name='Reset Password'),
    path('change-password/', ChangePasswordView.as_view(), name='Change Password'),

    # Notifications
    path('notifications/', NotificationListView.as_view(), name='Notifications List'),
    path('notifications/<uuid:pk>/read/', NotificationMarkReadView.as_view(), name='Notification Mark Read'),
    path('notifications/read-all/', NotificationMarkAllReadView.as_view(), name='Notification Mark All Read'),
]
