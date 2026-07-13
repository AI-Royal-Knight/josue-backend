from rest_framework import serializers
from app.project_admin.models import Project, ProjectFolder, ProjectSubfolder
from app.project_admin.serializers import FolderAssignmentSerializer

class SubfolderRowsSerializer(serializers.ModelSerializer):
    assignments = FolderAssignmentSerializer(many=True, read_only=True)
    class Meta:
        model = ProjectSubfolder
        fields = ('id', 'name', 'rows', 'project_value', 'labour_target', 'assignments')

class FolderWithSubfoldersSerializer(serializers.ModelSerializer):
    subfolders = SubfolderRowsSerializer(many=True, read_only=True)
    
    class Meta:
        model = ProjectFolder
        fields = ('id', 'name', 'subfolders', 'is_management')

class CMProjectSerializer(serializers.ModelSerializer):
    folders = FolderWithSubfoldersSerializer(many=True, read_only=True)
    
    class Meta:
        model = Project
        fields = ('id', 'project_name', 'folders')
