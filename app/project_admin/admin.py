from django.contrib import admin
from .models import Project, ProjectFolder, ProjectSubfolder, FolderAssignment

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

@admin.register(ProjectFolder)
class ProjectFolderAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "is_management", "created_at"]
    list_filter = ["is_management", "project"]
    search_fields = ["name", "project__project_name"]

@admin.register(ProjectSubfolder)
class ProjectSubfolderAdmin(admin.ModelAdmin):
    list_display = ["name", "folder", "created_at"]
    list_filter = ["folder__project", "folder"]
    search_fields = ["name", "folder__name"]

@admin.register(FolderAssignment)
class FolderAssignmentAdmin(admin.ModelAdmin):
    list_display = ["user", "subfolder", "is_management_assignment", "created_at"]
    list_filter = ["is_management_assignment", "subfolder__folder__project", "subfolder__folder"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
