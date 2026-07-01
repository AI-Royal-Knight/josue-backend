from django.urls import path
from .views import (
    ProjectListCreateView, 
    ProjectDetailView, 
    ProjectRoleAssignmentsView, 
    CompanyUsersView, 
    ProjectFoldersView,
    ProjectFoldersBulkUpdateView,
    ProjectApprovalConfigurationsView,
    MyProjectsView,
)

urlpatterns = [
    path("users/", CompanyUsersView.as_view(), name="company-users"),
    path("my-projects/", MyProjectsView.as_view(), name="my-projects"),
    path("projects/", ProjectListCreateView.as_view(), name="project-list-create"),
    path("projects/<uuid:pk>/", ProjectDetailView.as_view(), name="project-detail"),
    path("projects/<uuid:pk>/roles/", ProjectRoleAssignmentsView.as_view(), name="project-roles"),
    path("projects/<uuid:pk>/folders/", ProjectFoldersView.as_view(), name="project-folders"),
    path("projects/<uuid:pk>/folders/bulk-update/", ProjectFoldersBulkUpdateView.as_view(), name="project-folders-bulk-update"),
    path("projects/<uuid:pk>/approval-configs/", ProjectApprovalConfigurationsView.as_view(), name="project-approval-configs"),
]
