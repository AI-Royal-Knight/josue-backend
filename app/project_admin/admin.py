from django.contrib import admin
from .models import Project

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "project_name", "job_code", "vat_rate", "company",
        "project_value", "start_date", "completion_date",
        "is_completed", "created_at",
    ]
    list_filter = ["vat_rate", "is_completed", "company"]
    search_fields = ["project_name", "job_code", "address"]
    ordering = ["-created_at"]
