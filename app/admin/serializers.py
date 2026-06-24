from rest_framework import serializers
from app.account.models import UserAccount, Company

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            'id', 'company_name', 'company_logo', 'phone', 
            'company_number', 'building_number', 'street', 
            'postcode', 'vat_number', 'status',
            'bank_name', 'bank_address', 'sort_code', 
            'account_number', 'iban', 'swift_bic', 'attachment'
        ]

class AdminProfileSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = UserAccount
        fields = [
            'id', 'email', 'backup_email', 'first_name', 
            'last_name', 'role', 'company', 'profile_updated_at'
        ]
        read_only_fields = ['id', 'email', 'role', 'company']

class CompanyUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            'company_name', 'phone', 'company_number', 'building_number', 
            'street', 'postcode', 'vat_number', 'bank_name', 'bank_address', 
            'sort_code', 'account_number', 'iban', 'swift_bic', 'attachment'
        ]

class AdminProfileUpdateSerializer(serializers.ModelSerializer):
    company = CompanyUpdateSerializer(required=False)

    class Meta:
        model = UserAccount
        fields = ['first_name', 'last_name', 'backup_email', 'company']

    def update(self, instance, validated_data):
        company_data = validated_data.pop('company', None)
        
        # Update UserAccount fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update associated Company if data is provided and company exists
        if company_data and instance.company:
            for attr, value in company_data.items():
                setattr(instance.company, attr, value)
            instance.company.save()

        return instance

class ProjectAdminInviteSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()

class ProjectAdminListSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = ['id', 'first_name', 'last_name', 'email', 'is_active', 'date_joined']


