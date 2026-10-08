from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import UserAccount, UserProfile, Company

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'employee_id', 'cscs_card_no', 'cscs_expiry_date', 'ipaf_certification', 'pasma_certification', 
            'sssts_smsts', 'profession', 'emergency_contact_name', 'emergency_contact_number',
            'categories', 'insurance_policy', 'employer_liability', 'terms_accepted', 'digital_signature',
            'ni_number', 'utr', 'passport_number', 'passport_expiry_date', 'passport_document',
            'drivers_license_document', 'cscs_card_document',
            'account_name', 'bank_name', 'bank_address', 'sort_code', 'account_number', 'iban', 'swift_bic',
            'vat_number', 'address', 'company_name', 'two_factor_enabled'
        ]

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            'id', 'company_name', 'company_logo', 'company_number', 'building_number', 'street', 'town', 'city', 'postcode',
            'vat_number', 'phone', 'utr', 'bank_name', 'bank_address', 'sort_code', 'account_number',
            'iban', 'swift_bic', 'public_liability_policy', 'public_liability_expiry', 
            'public_liability_document', 'employers_liability_policy', 'employers_liability_expiry', 
            'employers_liability_document', 'terms_and_conditions_document'
        ]

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    company = CompanySerializer(read_only=True)
    stats = serializers.SerializerMethodField()
    
    class Meta:
        model = UserAccount
        fields = [
            'id',
            'email',
            'backup_email',
            'first_name',
            'last_name',
            'role',
            'secondary_role',
            'profile',
            'company',
            'assigned_companies',
            'stats',
            'two_factor_enabled',
        ]
        
    assigned_companies = serializers.SerializerMethodField()

    @extend_schema_field(CompanySerializer(many=True))
    def get_assigned_companies(self, obj):
        from .models import RoleAssignment, Company
        company_ids = RoleAssignment.objects.filter(user=obj).values_list('company_id', flat=True).distinct()
        companies = Company.objects.filter(id__in=company_ids, activate=True)
        # Also include the user's primary company if it's active and not in the list
        if obj.company and obj.company.activate and obj.company.id not in company_ids:
            companies = companies | Company.objects.filter(id=obj.company.id)
        return CompanySerializer(companies, many=True).data
        
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_stats(self, obj):
        # Temporary mock stats for UI until further specification
        return {
            "total": 5,
            "approved": 1,
            "pending": 3
        }

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    otp = serializers.CharField(required=False, allow_blank=True, default="")


class Verify2FASerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)


class Resend2FASerializer(serializers.Serializer):
    email = serializers.EmailField()



class SendInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.CharField()
    secondary_role = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    company_id = serializers.IntegerField(required=False)
    project_id = serializers.IntegerField(required=False)

    # Roles that cannot be invited through this endpoint under any circumstances
    BLOCKED_ROLES = {'super_admin'}

    def validate_role(self, value):
        valid_roles = {choice[0] for choice in UserAccount.Role.choices}
        if value not in valid_roles:
            raise serializers.ValidationError(f"'{value}' is not a valid role.")
        if value in self.BLOCKED_ROLES:
            raise serializers.ValidationError(f"The '{value}' role cannot be assigned via invitation.")
        return value

class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    password = serializers.CharField(write_only=True)
    # Profile fields depending on role (we can make them optional here)
    company_name = serializers.CharField(required=False) # For Admin/Supplier
    profession = serializers.CharField(required=False)
    cscs_card_no = serializers.CharField(required=False)
    digital_signature = serializers.CharField(required=False)
    terms_accepted = serializers.BooleanField(required=False, default=False)

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=4)

class ResetPasswordSerializer(serializers.Serializer):
    # URL token-based
    uid = serializers.CharField(required=False, allow_blank=True)
    token = serializers.CharField(required=False, allow_blank=True)
    # OTP-based
    email = serializers.EmailField(required=False, allow_blank=True)
    otp = serializers.CharField(required=False, allow_blank=True, max_length=4)
    
    new_password = serializers.CharField(write_only=True)

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
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


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import Notification
        model = Notification
        fields = [
            'id', 'title', 'body', 'type', 'is_read', 'created_at'
        ]

