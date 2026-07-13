from rest_framework import serializers
from app.account.models import CompanySupplier, SupplierProfile, UserAccount
from app.procurement_department.models import Quotation, QuotationLineItem
from app.project_admin.models import Project, ProjectFolder, ProjectSubfolder

class SupplierProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = SupplierProfile
        fields = ('id', 'company_name', 'email')

class CompanySupplierSerializer(serializers.ModelSerializer):
    supplier = SupplierProfileSerializer(read_only=True)
    
    class Meta:
        model = CompanySupplier
        fields = ('id', 'supplier', 'credit_limit', 'eom_payment_terms')

class InviteSupplierSerializer(serializers.Serializer):
    email = serializers.EmailField()
    company_name = serializers.CharField(max_length=255)

class QuotationLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationLineItem
        fields = ('id', 'description', 'qty', 'discount', 'per', 'each', 'comments')

class QuotationSerializer(serializers.ModelSerializer):
    line_items = QuotationLineItemSerializer(many=True, required=False)
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
