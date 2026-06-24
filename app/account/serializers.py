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
