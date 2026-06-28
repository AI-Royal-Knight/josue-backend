from rest_framework import serializers
from .models import UserAccount

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = [
            'id',
            'email',
            'backup_email',
            'first_name',
            'last_name',
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
