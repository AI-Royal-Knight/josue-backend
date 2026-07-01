from rest_framework import serializers
from .models import UserAccount, UserProfile, Company

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'cscs_card_no', 'cscs_expiry_date', 'ipaf_certification', 'pasma_certification', 
            'sssts_smsts', 'profession', 'emergency_contact_name', 'emergency_contact_number',
            'categories', 'insurance_policy', 'employer_liability', 'terms_accepted', 'digital_signature'
        ]

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            'id', 'company_name', 'company_number', 'building_number', 'street', 'town', 'city', 'postcode',
            'vat_number', 'phone', 'bank_name', 'bank_address', 'sort_code', 'account_number',
            'iban', 'swift_bic'
        ]

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    company = CompanySerializer(read_only=True)
    
    class Meta:
        model = UserAccount
        fields = [
            'id',
            'email',
            'backup_email',
            'first_name',
            'last_name',
            'role',
            'profile',
            'company'
        ]

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class SendInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.CharField()
    company_id = serializers.IntegerField(required=False)
    project_id = serializers.IntegerField(required=False)

class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    password = serializers.CharField(write_only=True)
    # Profile fields depending on role (we can make them optional here)
    company_name = serializers.CharField(required=False) # For Admin/Supplier
    profession = serializers.CharField(required=False)
    cscs_card_no = serializers.CharField(required=False)
    # etc...

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)


class SubmitApplicationSerializer(serializers.Serializer):
    # Role
    role = serializers.CharField()

    # Basic Information
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    # Professional Details
    categories = serializers.CharField(required=False, allow_blank=True)

    # Certifications & Compliance
    ipaf = serializers.CharField(required=False, allow_blank=True)
    ipaf_expiry = serializers.DateField(required=False, allow_null=True)
    pasma = serializers.CharField(required=False, allow_blank=True)
    pasma_expiry = serializers.DateField(required=False, allow_null=True)
    smsts = serializers.CharField(required=False, allow_blank=True)
    smsts_expiry = serializers.DateField(required=False, allow_null=True)
    cscs = serializers.CharField(required=False, allow_blank=True)
    cscs_expiry = serializers.DateField(required=False, allow_null=True)

    # Company Information
    company_name = serializers.CharField()
    company_house_number = serializers.CharField(required=False, allow_blank=True)
    company_utr = serializers.CharField(required=False, allow_blank=True)

    # Bank Details
    bank_name = serializers.CharField()
    account_name = serializers.CharField()
    bank_address = serializers.CharField(required=False, allow_blank=True)
    account_number = serializers.CharField()
    sort_code = serializers.CharField()

    # Insurance & Address
    insurance_policy = serializers.CharField(required=False, allow_blank=True)
    employer_liability = serializers.CharField(required=False, allow_blank=True)
    building = serializers.CharField()
    town = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField()
    postcode = serializers.CharField()

    # Terms & Signature
    terms_accepted = serializers.BooleanField()
    signature = serializers.CharField()
