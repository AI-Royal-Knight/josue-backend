from rest_framework import serializers
from app.account.models import Company

class AdminInviteSerializer(serializers.Serializer):
    company_name = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    phone_number = serializers.CharField()

class CompanyListSerializer(serializers.ModelSerializer):
    admin_name = serializers.SerializerMethodField()
    admin_surname = serializers.SerializerMethodField()
    admin_email = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'company_name', 'admin_name', 'admin_surname', 'admin_email',
            'phone', 'user', 'projects', 'activate', 'monthly_subscription',
            'per_user_rate', 'auto_monthly_inv', 'status'
        ]

    def get_admin_name(self, obj):
        # Assumes admin_users is populated via Prefetch
        if hasattr(obj, 'admin_users') and obj.admin_users:
            return obj.admin_users[0].first_name
        return None

    def get_admin_surname(self, obj):
        if hasattr(obj, 'admin_users') and obj.admin_users:
            return obj.admin_users[0].last_name
        return None

    def get_admin_email(self, obj):
        if hasattr(obj, 'admin_users') and obj.admin_users:
            return obj.admin_users[0].email
        return None

    def get_user(self, obj):
        from app.account.models import UserAccount
        if obj.company_name:
            return UserAccount.objects.filter(company__company_name__iexact=obj.company_name.strip()).exclude(role=UserAccount.Role.SUPER_ADMIN).count()
        return UserAccount.objects.filter(company=obj).exclude(role=UserAccount.Role.SUPER_ADMIN).count()

    def get_projects(self, obj):
        from app.project_admin.models import Project
        if obj.company_name:
            return Project.objects.filter(company__company_name__iexact=obj.company_name.strip()).count()
        return Project.objects.filter(company=obj).count()

class AcceptCompanyInvitationSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"password": "Passwords must match."})
        return data

