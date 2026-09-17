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
    # Call-off enrichment — derived from the FK if linked
    call_off_amount = serializers.SerializerMethodField()
    call_off_qty = serializers.SerializerMethodField()

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
            "po_reference",
            "call_off_reference",
            "call_off_amount",
            "call_off_qty",
            "created_at",
        ]
        read_only_fields = ["id", "status", "procurement_comments", "created_at"]

    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None

    def get_call_off_amount(self, obj):
        """Return the total value of the linked call-off (price × qty) if FK is present."""
        if obj.call_off:
            try:
                return str(obj.call_off.price * obj.call_off.qty)
            except Exception:
                pass
        return None

    def get_call_off_qty(self, obj):
        if obj.call_off:
            return str(obj.call_off.qty)
        return None


class SupplierInvoiceCreateSerializer(serializers.ModelSerializer):
    """
    Used by the supplier portal to submit a new invoice.
    Accepts po_reference and call_off (UUID FK) / call_off_reference.
    If a call_off FK is provided, call_off_reference is auto-populated from it.
    """
    call_off = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = SupplierInvoice
        fields = [
            "invoice_number",
            "invoice_date",
            "amount",
            "description",
            "file",
            "po_reference",
            "call_off",
            "call_off_reference",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value

    def validate(self, data):
        call_off_id = data.get("call_off")
        if call_off_id:
            from app.procurement_department.models import OrderLineCallOff
            try:
                call_off_obj = OrderLineCallOff.objects.get(id=call_off_id)
                # Auto-populate call_off_reference from the FK object
                data["call_off_reference"] = call_off_obj.call_off_ref
                # Auto-populate po_reference from the linked quotation if not provided
                if not data.get("po_reference"):
                    data["po_reference"] = call_off_obj.line_item.quotation.quote_ref
                # Store the actual instance for saving
                data["call_off"] = call_off_obj
            except OrderLineCallOff.DoesNotExist:
                raise serializers.ValidationError({"call_off": "Call-off reference not found."})
        return data

    def create(self, validated_data):
        return SupplierInvoice.objects.create(**validated_data)
