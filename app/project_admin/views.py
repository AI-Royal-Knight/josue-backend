from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from drf_spectacular.utils import extend_schema

from app.account.permissions import IsAdmin
from .models import Project
from .serializers import (
    ProjectListSerializer,
    ProjectCreateSerializer,
    ProjectUpdateSerializer,
)


class ProjectListCreateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses={200: ProjectListSerializer(many=True)})
    def get(self, request):
        if not request.user.company:
            return Response(
                {"error": "Admin has no associated company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        projects = Project.objects.filter(company=request.user.company)

        serializer = ProjectListSerializer(projects, many=True)
        return Response(
            {
                "projects": serializer.data,
                "total_count": projects.count(),
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=ProjectCreateSerializer,
        responses={201: ProjectListSerializer},
    )
    def post(self, request):
        if not request.user.company:
            return Response(
                {"error": "Admin has no associated company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProjectCreateSerializer(data=request.data)
        if serializer.is_valid():
            project = serializer.save(company=request.user.company)
            return Response(
                ProjectListSerializer(project).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProjectDetailView(APIView):
    permission_classes = [IsAdmin]

    def get_object(self, pk, company):
        try:
            return Project.objects.get(pk=pk, company=company)
        except Project.DoesNotExist:
            return None

    @extend_schema(responses={200: ProjectListSerializer})
    def get(self, request, pk):
        if not request.user.company:
            return Response(
                {"error": "Admin has no associated company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = self.get_object(pk, request.user.company)
        if not project:
            return Response(
                {"error": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProjectListSerializer(project)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=ProjectUpdateSerializer,
        responses={200: ProjectListSerializer},
    )
    def put(self, request, pk):
        if not request.user.company:
            return Response(
                {"error": "Admin has no associated company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = self.get_object(pk, request.user.company)
        if not project:
            return Response(
                {"error": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProjectUpdateSerializer(project, data=request.data, partial=True)
        if serializer.is_valid():
            project = serializer.save()
            return Response(
                ProjectListSerializer(project).data,
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not request.user.company:
            return Response(
                {"error": "Admin has no associated company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = self.get_object(pk, request.user.company)
        if not project:
            return Response(
                {"error": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        project.delete()
        return Response(
            {"message": "Project deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )

class CompanyUsersView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)
        
        from app.account.models import UserAccount
        users = UserAccount.objects.filter(company=request.user.company).exclude(role__in=[UserAccount.Role.SUPER_ADMIN, UserAccount.Role.ADMIN])
        
        users_data = []
        for user in users:
            users_data.append({
                "id": str(user.id),
                "name": user.full_name,
                "email": user.email
            })
            
        return Response({"users": users_data}, status=status.HTTP_200_OK)


class ProjectRoleAssignmentsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = Project.objects.get(pk=pk, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        # Get all role assignments for this project
        from app.account.models import RoleAssignment, UserAccount
        from .serializers import RoleAssignmentSerializer

        assignments = RoleAssignment.objects.filter(project=project)
        
        # Group by role
        roles_data = []
        for role_key, role_name in UserAccount.Role.choices:
            if role_key in [UserAccount.Role.SUPER_ADMIN, UserAccount.Role.ADMIN]:
                continue # Skip system roles
                
            role_assignments = assignments.filter(role=role_key)
            users_data = []
            for assignment in role_assignments:
                if assignment.user:
                    users_data.append({
                        "id": str(assignment.user.id),
                        "name": assignment.user.full_name,
                        "checked": True
                    })
                    
            roles_data.append({
                "role": role_name,
                "role_key": role_key,
                "users": users_data
            })

        return Response(roles_data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = Project.objects.get(pk=pk, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        # payload: {"role_key": "supervisor", "user_id": 123}
        role_key = request.data.get("role_key")
        user_id = request.data.get("user_id")

        if not role_key or not user_id:
            return Response({"error": "role_key and user_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        from app.account.models import RoleAssignment, UserAccount
        
        try:
            user = UserAccount.objects.get(id=user_id)
        except UserAccount.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
            
        assignment, created = RoleAssignment.objects.get_or_create(
            user=user,
            role=role_key,
            project=project,
            defaults={"company": request.user.company}
        )
        
        return Response({"message": "User assigned to role successfully."}, status=status.HTTP_200_OK)


from .models import ProjectFolder, ProjectSubfolder
from .serializers import ProjectFolderSerializer

class ProjectFoldersView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = Project.objects.get(pk=pk, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        folders = ProjectFolder.objects.filter(project=project)
        serializer = ProjectFolderSerializer(folders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = Project.objects.get(pk=pk, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
            
        # payload format: {"name": "Electrical", "is_management": False, "subfolders": [{"name": "Wiring", "project_value": 1000, "labour_target": 200}]}
        name = request.data.get("name")
        is_management = request.data.get("is_management", False)
        subfolders = request.data.get("subfolders", [])

        if not name:
            return Response({"error": "Folder name is required."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            folder = ProjectFolder.objects.create(
                project=project,
                name=name,
                is_management=is_management
            )
            for sub in subfolders:
                ProjectSubfolder.objects.create(
                    folder=folder,
                    name=sub.get("name", "Unnamed"),
                    project_value=sub.get("project_value", 0),
                    labour_target=sub.get("labour_target", 0)
                )

        # return full updated list
        folders = ProjectFolder.objects.filter(project=project)
        serializer = ProjectFolderSerializer(folders, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectFoldersBulkUpdateView(APIView):
    permission_classes = [IsAdmin]

    def put(self, request, pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = Project.objects.get(pk=pk, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        # payload format: [{"id": "...", "name": "...", "subfolders": [{"id": "...", "name": "...", "rows": []}]}]
        folders_data = request.data
        if not isinstance(folders_data, list):
            return Response({"error": "Expected a list of folders."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Delete existing folders not in payload
            folder_ids = [f.get("id") for f in folders_data if f.get("id") and not str(f.get("id")).startswith("new_")]
            ProjectFolder.objects.filter(project=project).exclude(id__in=folder_ids).delete()
            
            for f_data in folders_data:
                f_id = f_data.get("id")
                f_name = f_data.get("name")
                
                if str(f_id).startswith("new_") or not f_id:
                    folder = ProjectFolder.objects.create(project=project, name=f_name, is_management=f_data.get("is_management", False))
                else:
                    folder = ProjectFolder.objects.filter(id=f_id, project=project).first()
                    if folder:
                        folder.name = f_name
                        folder.is_management = f_data.get("is_management", False)
                        folder.save()
                    else:
                        continue
                        
                subfolders_data = f_data.get("subfolders", [])
                sub_ids = [s.get("id") for s in subfolders_data if s.get("id") and not str(s.get("id")).startswith("new_")]
                ProjectSubfolder.objects.filter(folder=folder).exclude(id__in=sub_ids).delete()
                
                for s_data in subfolders_data:
                    s_id = s_data.get("id")
                    s_name = s_data.get("name")
                    s_rows = s_data.get("rows", [])
                    s_pv = s_data.get("project_value", 0)
                    s_lt = s_data.get("labour_target", 0)
                    
                    if str(s_id).startswith("new_") or not s_id:
                        ProjectSubfolder.objects.create(
                            folder=folder, 
                            name=s_name, 
                            rows=s_rows,
                            project_value=s_pv,
                            labour_target=s_lt
                        )
                    else:
                        sub = ProjectSubfolder.objects.filter(id=s_id, folder=folder).first()
                        if sub:
                            sub.name = s_name
                            sub.rows = s_rows
                            sub.project_value = s_pv
                            sub.labour_target = s_lt
                            sub.save()

        # return full updated list
        folders = ProjectFolder.objects.filter(project=project)
        serializer = ProjectFolderSerializer(folders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


from .models import ApprovalConfiguration
from .serializers import ApprovalConfigurationSerializer

class ProjectApprovalConfigurationsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = Project.objects.get(pk=pk, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        configs = ApprovalConfiguration.objects.filter(project=project)
        serializer = ApprovalConfigurationSerializer(configs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = Project.objects.get(pk=pk, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        # payload format: list of dicts with action_type, condition_value, required_roles
        configs_data = request.data
        if not isinstance(configs_data, list):
            return Response({"error": "Expected a list of approval configurations."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            ApprovalConfiguration.objects.filter(project=project).delete()
            
            for c_data in configs_data:
                action_type = c_data.get("action_type")
                if not action_type:
                    continue
                ApprovalConfiguration.objects.create(
                    project=project,
                    action_type=action_type,
                    condition_value=c_data.get("condition_value", "ALL"),
                    required_roles=c_data.get("required_roles", ""),
                    is_active=c_data.get("is_active", True)
                )

        configs = ApprovalConfiguration.objects.filter(project=project)
        serializer = ApprovalConfigurationSerializer(configs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


