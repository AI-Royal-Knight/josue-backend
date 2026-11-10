from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import RFI, RFIMessage, AttendanceLog, RAMS, DailyBriefing, ToolboxTalk, ToDoList
from app.account.models import UserAccount

class RFIMessageSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_role = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = RFIMessage
        fields = ['id', 'author_name', 'author_role', 'text', 'attachments', 'document_url', 'created_at']

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_author_name(self, obj):
        if obj.author:
            if obj.author.first_name or obj.author.last_name:
                return f"{obj.author.first_name} {obj.author.last_name}".strip()
            return obj.author.email.split('@')[0]
        return "Unknown"

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_author_role(self, obj):
        role = getattr(obj, 'author_role', None) or (obj.author.role if obj.author else "Unknown")
        return dict(UserAccount.Role.choices).get(role, role.replace('_', ' ').title() if isinstance(role, str) else role)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_attachments(self, obj):
        if obj.document_url:
            import urllib.parse
            import re
            urls = [u.strip() for u in obj.document_url.split(',') if u.strip()]
            res = []
            for u in urls:
                raw = u.split('?')[0].split('/')[-1]
                filename = urllib.parse.unquote(raw) or "Attachment"
                clean_name = re.sub(r'^\d{10,}_', '', filename) or filename
                res.append({"name": clean_name, "url": u})
            return res
        return []

class RFISerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    messages = RFIMessageSerializer(many=True, read_only=True)

    class Meta:
        model = RFI
        fields = [
            'id', 'rfi_number', 'description', 'trade',
            'status', 'document_url', 'attachments', 'created_at', 'closed_at',
            'created_by', 'created_by_name', 'messages', 'assigned_to_technical_department'
        ]
        read_only_fields = ['id', 'rfi_number', 'status', 'created_at', 'closed_at', 'created_by_name']

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_created_by_name(self, obj):
        if obj.created_by:
            if obj.created_by.first_name or obj.created_by.last_name:
                return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
            return obj.created_by.email
        return "Unknown"

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_attachments(self, obj):
        if obj.document_url:
            import urllib.parse
            import re
            urls = [u.strip() for u in obj.document_url.split(',') if u.strip()]
            res = []
            for u in urls:
                raw = u.split('?')[0].split('/')[-1]
                filename = urllib.parse.unquote(raw) or "Attachment"
                clean_name = re.sub(r'^\d{10,}_', '', filename) or filename
                res.append({"name": clean_name, "url": u})
            return res
        return []

class DashboardRFISerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.project_name', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    messages = RFIMessageSerializer(many=True, read_only=True)
    attachments = serializers.SerializerMethodField()
    can_close = serializers.SerializerMethodField()
    
    class Meta:
        model = RFI
        fields = [
            'id', 'rfi_number', 'project', 'project_name', 'description', 'trade',
            'status', 'document_url', 'attachments', 'created_at', 'closed_at',
            'created_by', 'created_by_name', 'messages', 'assigned_to_technical_department',
            'can_close'
        ]

    @extend_schema_field(serializers.BooleanField())
    def get_can_close(self, obj):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return False
        user = request.user
        if obj.created_by_id == user.id:
            return True
        active_role = request.headers.get("X-Active-Role") or getattr(user, 'active_role', user.role)
        is_pd = (
            user.role == "project_director" or 
            active_role == "project_director" or 
            user.role_assignments.filter(role="project_director", project=obj.project).exists() or
            user.role in ["admin", "super_admin", "managing_director"] or
            active_role in ["admin", "super_admin", "managing_director"] or
            user.is_superuser or user.is_staff
        )
        if is_pd:
            return (
                (user.company and obj.project.company_id == user.company_id) or
                user.role_assignments.filter(project=obj.project).exists() or
                user.accessible_projects.filter(id=obj.project_id).exists() or
                user.is_superuser or user.is_staff
            )
        return False

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_created_by_name(self, obj):
        if obj.created_by:
            if obj.created_by.first_name or obj.created_by.last_name:
                return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
            return obj.created_by.email.split('@')[0]
        return "Unknown"

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_attachments(self, obj):
        if obj.document_url:
            import urllib.parse
            import re
            urls = [u.strip() for u in obj.document_url.split(',') if u.strip()]
            res = []
            for u in urls:
                raw = u.split('?')[0].split('/')[-1]
                filename = urllib.parse.unquote(raw) or "Attachment"
                clean_name = re.sub(r'^\d{10,}_', '', filename) or filename
                res.append({"name": clean_name, "url": u})
            return res
        return []

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
        
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_profession(self, obj):
        if hasattr(obj.user, 'profile') and obj.user.profile:
            return obj.user.profile.profession
        return None
        
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_management(self, obj):
        return dict(UserAccount.Role.choices).get(obj.user.role, obj.user.role) if obj.user else None

class RAMSSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.project_name', read_only=True)

    class Meta:
        model = RAMS
        fields = ['id', 'project', 'project_name', 'title', 'description', 'date', 'review_date', 'document_url', 'signed_document_url', 'completed_at']

class DailyBriefingSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.project_name', read_only=True)

    class Meta:
        model = DailyBriefing
        fields = ['id', 'project', 'project_name', 'title', 'description', 'date', 'document_url', 'signed_document_url', 'completed_at']

class ToolboxTalkSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.project_name', read_only=True)

    class Meta:
        model = ToolboxTalk
        fields = ['id', 'project', 'project_name', 'title', 'description', 'date', 'document_url', 'signed_document_url', 'completed_at']

class ToDoListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.project_name', read_only=True)

    class Meta:
        model = ToDoList
        fields = ['id', 'project', 'project_name', 'title', 'description', 'date', 'completion_date', 'assign_user', 'signed_document_url', 'completed_at']
