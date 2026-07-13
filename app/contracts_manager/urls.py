from django.urls import path
from .views import CMProjectListView, CMSubfolderUpdateView

urlpatterns = [
    path("projects/", CMProjectListView.as_view(), name="cm-projects"),
    path("subfolders/<uuid:pk>/", CMSubfolderUpdateView.as_view(), name="cm-subfolders-update"),
]
