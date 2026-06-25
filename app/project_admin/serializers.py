from rest_framework import serializers
from .models import Project


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
