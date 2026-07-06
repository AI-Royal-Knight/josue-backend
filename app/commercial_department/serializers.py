from rest_framework import serializers
from .models import Variation, VariationLine


class VariationLineSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = VariationLine
        fields = [
            "id", "site_instruction", "work_area", "work_section",
            "labour", "labour_target", "material", "qty", "line_total",
        ]

    def get_line_total(self, obj):
        return float((obj.labour + obj.material) * obj.qty)


class VariationSerializer(serializers.ModelSerializer):
    lines = VariationLineSerializer(many=True, read_only=True)
    project_name = serializers.CharField(source="project.project_name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Variation
        fields = [
            "id", "vo_number", "variation_sheet_number", "date",
            "project", "project_name",
            "site_instruction_no", "attention_of", "description_of_works",
            "comments", "total_amount",
            "approval_status", "approved_by", "approved_by_name",
            "submitted_to_client", "signed_by_client",
            "created_by", "created_by_name",
            "lines",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.full_name
        return ""

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.full_name
        return ""
