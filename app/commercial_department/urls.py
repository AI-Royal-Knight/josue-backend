from django.urls import path
from .views import (
    VariationListCreateView,
    VariationApprovalView,
    VariationSubmitToClientView,
)

app_name = "commercial_department"

urlpatterns = [
    path("variations/", VariationListCreateView.as_view(), name="variation-list-create"),
    path("variations/<uuid:pk>/approve/", VariationApprovalView.as_view(), name="variation-approve"),
    path("variations/<uuid:pk>/submit-to-client/", VariationSubmitToClientView.as_view(), name="variation-submit-client"),
]
