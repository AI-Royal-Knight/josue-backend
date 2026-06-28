from rest_framework import serializers
from .models import Project
from app.account.models import RoleAssignment, UserAccount


class ProjectListSerializer(serializers.ModelSerializer):
    estimate_profit = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "project_name",
            "job_code",
            "vat_rate",
            "address",
            "created_at",
            "project_value",
            "material_estimate",
            "labour_estimate",
            "prelims_estimate",
            "estimate_profit",
            "start_date",
            "completion_date",
            "is_overdue",
            "is_completed",
        ]


class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "project_name",
            "job_code",
            "vat_rate",
            "address",
            "project_value",
            "material_estimate",
            "labour_estimate",
            "prelims_estimate",
            "start_date",
            "completion_date",
            "is_completed",
        ]


class ProjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "project_name",
            "job_code",
            "vat_rate",
            "address",
            "project_value",
            "material_estimate",
            "labour_estimate",
            "prelims_estimate",
            "start_date",
            "completion_date",
            "is_completed",
        ]


class UserAccountMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = ['id', 'first_name', 'last_name', 'email']

class RoleAssignmentSerializer(serializers.ModelSerializer):
    user = UserAccountMinimalSerializer(read_only=True)
    
    class Meta:
        model = RoleAssignment
        fields = ['id', 'user', 'role', 'project']


from .models import ProjectFolder, ProjectSubfolder, FolderAssignment

class FolderAssignmentSerializer(serializers.ModelSerializer):
    user = UserAccountMinimalSerializer(read_only=True)
    class Meta:
        model = FolderAssignment
        fields = ['id', 'user', 'hide_labour_target', 'is_management_assignment']

class ProjectSubfolderSerializer(serializers.ModelSerializer):
    assignments = FolderAssignmentSerializer(many=True, read_only=True)
    class Meta:
        model = ProjectSubfolder
        fields = ['id', 'name', 'project_value', 'labour_target', 'rows', 'assignments']

class ProjectFolderSerializer(serializers.ModelSerializer):
    subfolders = ProjectSubfolderSerializer(many=True, read_only=True)
    class Meta:
        model = ProjectFolder
        fields = ['id', 'name', 'is_management', 'subfolders']


from .models import ApprovalConfiguration

class ApprovalConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalConfiguration
        fields = ['id', 'action_type', 'condition_value', 'required_roles', 'is_active']

