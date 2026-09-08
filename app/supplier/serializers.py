from rest_framework import serializers
from app.account.models import UserAccount, CompanySupplier, SupplierProfile, Company
from .models import SupplierInvitation, SupplierInvoice


class SupplierInvitationDetailSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.company_name", read_only=True)
    company_id = serializers.CharField(source="company.id", read_only=True)
    is_expired = serializers.SerializerMethodField()
    is_existing_user = serializers.SerializerMethodField()

    class Meta:
        model = SupplierInvitation
        fields = [
            "token",
            "email",
            "supplier_name",
            "company_name",
            "company_id",
            "status",
            "expires_at",
            "is_expired",
            "is_existing_user",
        ]

    def get_is_expired(self, obj):
        return obj.is_expired()

    def get_is_existing_user(self, obj):
        user = UserAccount.objects.filter(email=obj.email).first()
        return bool(user and user.has_usable_password())


class SupplierInvitationAcceptSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    company_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    password = serializers.CharField(min_length=8, write_only=True, required=False, allow_blank=True)


class SupplierCompanyRelationshipSerializer(serializers.ModelSerializer):
    company_id = serializers.CharField(source="company.id", read_only=True)
    company_name = serializers.CharField(source="company.company_name", read_only=True)
    company_logo = serializers.SerializerMethodField()
    relationship_status = serializers.CharField(source="status", read_only=True)

    class Meta:
        model = CompanySupplier
        fields = [
            "id",
            "company_id",
            "company_name",
            "company_logo",
            "relationship_status",
            "eom_payment_terms",
            "credit_limit",
            "invited_at",
            "accepted_at",
        ]

    def get_company_logo(self, obj):
        if obj.company.company_logo:
            return obj.company.company_logo.url
        return None


class SupplierInvoiceSerializer(serializers.ModelSerializer):
    company_id = serializers.CharField(source="company.id", read_only=True)
    company_name = serializers.CharField(source="company.company_name", read_only=True)
    supplier_name = serializers.CharField(source="company_supplier.supplier.company_name", read_only=True)
    supplier_email = serializers.CharField(source="company_supplier.supplier.user.email", read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = SupplierInvoice
        fields = [
            "id",
            "company_id",
            "company_name",
            "supplier_name",
            "supplier_email",
            "invoice_number",
            "invoice_date",
            "amount",
            "description",
            "file",
            "file_url",
            "status",
            "procurement_comments",
            "created_at",
        ]
        read_only_fields = ["id", "status", "procurement_comments", "created_at"]

    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None


class SupplierInvoiceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierInvoice
        fields = [
            "invoice_number",
            "invoice_date",
            "amount",
            "description",
            "file",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value
