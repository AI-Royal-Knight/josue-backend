from rest_framework import serializers
from .models import RFI, RFIMessage, AttendanceLog, RAMS, DailyBriefing, ToolboxTalk, ToDoList
from app.account.models import UserAccount

class RFISerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = RFI
        fields = [
            'id', 'rfi_number', 'description', 
            'status', 'document_url', 'created_at', 'closed_at',
            'created_by_name'
        ]
        read_only_fields = ['id', 'rfi_number', 'status', 'created_at', 'closed_at', 'created_by_name']

    def get_created_by_name(self, obj):
        if obj.created_by:
            if hasattr(obj.created_by, 'profile') and obj.created_by.profile:
                return f"{obj.created_by.profile.first_name} {obj.created_by.profile.last_name}"
            return obj.created_by.email
        return "Unknown"

class RFIMessageSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_role = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = RFIMessage
        fields = ['id', 'author_name', 'author_role', 'text', 'attachments', 'created_at']

    def get_author_name(self, obj):
        return obj.author.full_name or obj.author.email.split('@')[0] if obj.author else "Unknown"

    def get_author_role(self, obj):
        return dict(UserAccount.Role.choices).get(obj.author.role, obj.author.role) if obj.author else "Unknown"

    def get_attachments(self, obj):
        if obj.document_url:
            filename = obj.document_url.split('/')[-1]
            return [{"name": filename, "url": obj.document_url}]
        return []

class DashboardRFISerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.project_name', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    messages = RFIMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = RFI
        fields = [
            'id', 'rfi_number', 'project_name', 'description', 'trade',
            'status', 'document_url', 'created_at', 'closed_at',
            'created_by_name', 'messages'
        ]

    def get_created_by_name(self, obj):
        return obj.created_by.full_name or obj.created_by.email.split('@')[0] if obj.created_by else "Unknown"

class DailyRegisterSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.first_name', read_only=True)
    surname = serializers.CharField(source='user.last_name', read_only=True)
    project_name = serializers.CharField(source='project.project_name', read_only=True)
    profession = serializers.SerializerMethodField()
    management = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceLog
        fields = [
            'id', 'name', 'surname', 'project_name', 'date', 
            'check_in_time', 'check_in_lat', 'check_in_long', 
            'check_out_time', 'check_out_lat', 'check_out_long',
            'profession', 'management'
        ]
        
    def get_profession(self, obj):
        if hasattr(obj.user, 'profile') and obj.user.profile:
            return obj.user.profile.profession
        return None
        
    def get_management(self, obj):
        return dict(UserAccount.Role.choices).get(obj.user.role, obj.user.role) if obj.user else None

class RAMSSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.project_name', read_only=True)

    class Meta:
        model = RAMS
        fields = ['id', 'project', 'project_name', 'title', 'date', 'review_date', 'document_url']

class DailyBriefingSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.project_name', read_only=True)

    class Meta:
        model = DailyBriefing
        fields = ['id', 'project', 'project_name', 'title', 'date', 'document_url']

class ToolboxTalkSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.project_name', read_only=True)

    class Meta:
        model = ToolboxTalk
        fields = ['id', 'project', 'project_name', 'title', 'date', 'document_url']

class ToDoListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.project_name', read_only=True)

    class Meta:
        model = ToDoList
        fields = ['id', 'project', 'project_name', 'title', 'date', 'completion_date', 'assign_user']
