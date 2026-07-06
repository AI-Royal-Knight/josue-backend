from rest_framework import serializers

class InviteEmployeeSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()

class ApproveEmployeeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    approved = serializers.BooleanField()

