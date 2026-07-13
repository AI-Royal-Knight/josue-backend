from django.urls import path
from .views import (
    VariationListCreateView,
    VariationApprovalView,
    VariationSubmitToClientView,
    VariationAssignUsersView,
    MonthlyApplicationListCreateView,
    WhiteCardView,
)

app_name = "commercial_department"

urlpatterns = [
    path("variations/", VariationListCreateView.as_view(), name="variation-list-create"),
    path("variations/<uuid:pk>/approve/", VariationApprovalView.as_view(), name="variation-approve"),
    path("variations/<uuid:pk>/submit-to-client/", VariationSubmitToClientView.as_view(), name="variation-submit-client"),
    path("variations/<uuid:pk>/assign/", VariationAssignUsersView.as_view(), name="variation-assign-users"),
    path("monthly-applications/", MonthlyApplicationListCreateView.as_view(), name="monthly-applications"),
    path("white-card/", WhiteCardView.as_view(), name="white-card"),
]
