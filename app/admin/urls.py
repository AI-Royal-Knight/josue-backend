from django.urls import path
from .views import HomeView, AdminProfileView, ProjectAdminsView, AdminProjectListView, ManagingDirectorsView

urlpatterns = [
    path('home/', HomeView.as_view(), name='Admin Home'),
    path('profile/', AdminProfileView.as_view(), name='Admin Profile'),
    path('project-admins/', ProjectAdminsView.as_view(), name='Project Admins'),
    path('managing-directors/', ManagingDirectorsView.as_view(), name='Managing Directors'),
    path('projects/', AdminProjectListView.as_view(), name='Admin Projects'),
]
