from django.urls import path
from .views import (
    ProfileView,
    LoginView,
)

urlpatterns = [
    path('login/', LoginView.as_view(), name='Login View'),
    path('profile/', ProfileView.as_view(), name='Profile View'),
]
