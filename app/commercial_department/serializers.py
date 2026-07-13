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
    assigned_user_ids = serializers.PrimaryKeyRelatedField(
        source="assigned_users",
        many=True,
        read_only=True
    )
    
    # Custom fields for Variation Summary UI
    no = serializers.CharField(source="vo_number", read_only=True)
    siteInstructionNumber = serializers.CharField(source="site_instruction_no", read_only=True)
    evidence = serializers.SerializerMethodField()
    variationSheetNumber = serializers.CharField(source="variation_sheet_number", read_only=True)
    descriptionOfWorks = serializers.CharField(source="description_of_works", read_only=True)
    workArea = serializers.SerializerMethodField()
    workSection = serializers.SerializerMethodField()
    labourCost = serializers.SerializerMethodField()
    materialCost = serializers.SerializerMethodField()
    variationAmount = serializers.SerializerMethodField()
    percentClaimed = serializers.SerializerMethodField()
    amountClaimed = serializers.SerializerMethodField()
    addToApplication = serializers.BooleanField(source="submitted_to_client", read_only=True)
    signByClient = serializers.SerializerMethodField()
    clientCertifiedAmount = serializers.SerializerMethodField()
    diffrenceAmount = serializers.SerializerMethodField()
    paymentStatusNr = serializers.SerializerMethodField()
    claimGQComment = serializers.SerializerMethodField()
    difference = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

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
            "assigned_user_ids",
            "no", "siteInstructionNumber", "evidence", "variationSheetNumber", "descriptionOfWorks",
            "workArea", "workSection", "labourCost", "materialCost", "variationAmount",
            "percentClaimed", "amountClaimed", "addToApplication", "signByClient",
            "clientCertifiedAmount", "diffrenceAmount", "paymentStatusNr", "claimGQComment",
            "valuation_amount", "percent_claimed", "amount_claimed", "client_certified_amount",
            "corresponding_notice_no", "client_qs_comment", "difference",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.full_name
        return ""

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.full_name
        return ""

    def get_evidence(self, obj):
        return "📄"

    def get_workArea(self, obj):
        return ", ".join(filter(None, set(line.work_area for line in obj.lines.all())))

    def get_workSection(self, obj):
        return ", ".join(filter(None, set(line.work_section for line in obj.lines.all())))

    def get_labourCost(self, obj):
        total = sum(line.labour * line.qty for line in obj.lines.all())
        return f"£{total:.2f}"

    def get_materialCost(self, obj):
        total = sum(line.material * line.qty for line in obj.lines.all())
        return f"£{total:.2f}"

    def get_variationAmount(self, obj):
        return f"£{obj.total_amount:.2f}"

    def get_percentClaimed(self, obj):
        return f"{obj.percent_claimed}%"

    def get_amountClaimed(self, obj):
        return f"£{obj.amount_claimed:.2f}"

    def get_signByClient(self, obj):
        return "Yes" if obj.signed_by_client else "No"

    def get_clientCertifiedAmount(self, obj):
        return f"£{obj.client_certified_amount:.2f}"

    def get_diffrenceAmount(self, obj):
        return f"£{obj.difference:.2f}"

    def get_paymentStatusNr(self, obj):
        return obj.corresponding_notice_no

    def get_claimGQComment(self, obj):
        return obj.client_qs_comment

from .models import MonthlyApplication

class MonthlyApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyApplication
        fields = "__all__"
