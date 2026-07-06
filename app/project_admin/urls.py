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
    ProjectFinancialBreakdownView,
    DashboardRFIListView,
    RFICloseView,
    RFIMessageCreateView,
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
    path("projects/<uuid:pk>/financial-breakdown/", ProjectFinancialBreakdownView.as_view(), name="project-financial-breakdown"),
    path("rfis/", DashboardRFIListView.as_view(), name="dashboard-rfi-list"),
    path("rfis/<uuid:pk>/close/", RFICloseView.as_view(), name="dashboard-rfi-close"),
    path("rfis/<uuid:pk>/messages/", RFIMessageCreateView.as_view(), name="dashboard-rfi-messages"),
]
