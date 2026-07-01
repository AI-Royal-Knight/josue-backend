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

class AcceptCompanyInvitationSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"password": "Passwords must match."})
        return data

