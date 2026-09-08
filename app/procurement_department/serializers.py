from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from app.account.models import CompanySupplier, SupplierProfile, UserAccount
from app.procurement_department.models import Quotation, QuotationLineItem, QuotationHistory, OrderLineCallOff
from app.project_admin.models import Project, ProjectFolder, ProjectSubfolder

class SupplierProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = SupplierProfile
        fields = ('id', 'company_name', 'email')

class CompanySupplierSerializer(serializers.ModelSerializer):
    supplier = SupplierProfileSerializer(read_only=True)
    invitation_token = serializers.SerializerMethodField()
    invitation_link = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanySupplier
        fields = (
            'id', 'supplier', 'status', 'credit_limit', 'eom_payment_terms',
            'invited_at', 'accepted_at', 'declined_at',
            'invitation_token', 'invitation_link'
        )

    def get_invitation_token(self, obj):
        inv = obj.invitations.filter(status='pending').order_by('-created_at').first()
        return inv.token if inv else None

    def get_invitation_link(self, obj):
        token = self.get_invitation_token(obj)
        if not token:
            return None
        request = self.context.get('request')
        from core.utils import get_frontend_url
        frontend_url = get_frontend_url(request) if request else "https://tresta.cloud"
        return f"{frontend_url}/supplier/invitation/{token}"


class ProcurementSupplierInvoiceSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='company_supplier.supplier.company_name', read_only=True)
    supplier_email = serializers.CharField(source='company_supplier.supplier.user.email', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        from app.supplier.models import SupplierInvoice
        model = SupplierInvoice
        fields = (
            'id', 'invoice_number', 'invoice_date', 'amount', 'description',
            'file', 'file_url', 'status', 'procurement_comments',
            'supplier_name', 'supplier_email', 'created_at', 'processed_at'
        )
        read_only_fields = ('id', 'invoice_number', 'invoice_date', 'amount', 'description', 'file', 'created_at')

    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None

class InviteSupplierSerializer(serializers.Serializer):
    email = serializers.EmailField()
    company_name = serializers.CharField(max_length=255)

class QuotationLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationLineItem
        fields = ('id', 'description', 'qty', 'discount', 'per', 'each', 'comments', 'supplier_price')

class QuotationHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationHistory
        fields = ('id', 'message', 'previous_total', 'previous_pdf', 'previous_line_items', 'date_recorded')

class OrderLineCallOffSerializer(serializers.ModelSerializer):
    call_off_by_name = serializers.CharField(source='called_off_by.full_name', read_only=True)
    approve_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)

    class Meta:
        model = OrderLineCallOff
        fields = '__all__'
        read_only_fields = ('call_off_ref',)

class CallOffLineItemSerializer(serializers.ModelSerializer):
    history = OrderLineCallOffSerializer(source='call_offs', many=True, read_only=True)
    qty_remaining = serializers.SerializerMethodField()
    po_ref = serializers.CharField(source='quotation.quote_ref', read_only=True)
    project_name = serializers.CharField(source='quotation.project.project_name', read_only=True)
    main_folder_name = serializers.CharField(source='quotation.main_folder.name', read_only=True)
    sub_folder_name = serializers.CharField(source='quotation.sub_folder.name', read_only=True)
    variation_ref = serializers.CharField(source='quotation.variation_ref', read_only=True)
    supplier_name = serializers.CharField(source='quotation.supplier.supplier.company_name', read_only=True)
    supplier_email = serializers.CharField(source='quotation.supplier_email', read_only=True)

    class Meta:
        model = QuotationLineItem
        fields = (
            'id', 'description', 'qty', 'per', 'each', 
            'po_ref', 'project_name', 'main_folder_name', 'sub_folder_name',
            'variation_ref', 'supplier_name', 'supplier_email',
            'management_approved', 'management_approved_date',
            'qty_remaining', 'history'
        )

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_qty_remaining(self, obj):
        called_off_qty = sum(c.qty for c in obj.call_offs.all())
        return obj.qty - called_off_qty


class QuotationSerializer(serializers.ModelSerializer):
    line_items = QuotationLineItemSerializer(many=True, required=False)
    history = QuotationHistorySerializer(many=True, read_only=True)
    project_name = serializers.CharField(source='project.project_name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.supplier.company_name', read_only=True)
    main_folder_name = serializers.CharField(source='main_folder.name', read_only=True)
    sub_folder_name = serializers.CharField(source='sub_folder.name', read_only=True)
    
    class Meta:
        model = Quotation
        fields = '__all__'
        read_only_fields = ('quote_ref',)

    def create(self, validated_data):
        line_items_data = validated_data.pop('line_items', [])
        if validated_data.get('po_created') and not validated_data.get('date_po_created'):
            from django.utils import timezone
            validated_data['date_po_created'] = timezone.now().date()
        quotation = Quotation.objects.create(**validated_data)
        for item_data in line_items_data:
            QuotationLineItem.objects.create(quotation=quotation, **item_data)
        return quotation

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Fallback to the supplier's registered account email if none was provided
        if not ret.get('supplier_email'):
            try:
                ret['supplier_email'] = instance.supplier.supplier.user.email
            except AttributeError:
                pass
        return ret

# Nested Serializers for Project -> Folders -> Subfolders
class ProjectSubfolderNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectSubfolder
        fields = ('id', 'name')

class ProjectFolderNestedSerializer(serializers.ModelSerializer):
    subfolders = ProjectSubfolderNestedSerializer(many=True, read_only=True)
    
    class Meta:
        model = ProjectFolder
        fields = ('id', 'name', 'subfolders')

class ProjectNestedSerializer(serializers.ModelSerializer):
    folders = ProjectFolderNestedSerializer(many=True, read_only=True)
    
    class Meta:
        model = Project
        fields = ('id', 'project_name', 'folders')
