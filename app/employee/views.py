from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_spectacular.utils import extend_schema
from app.project_admin.models import Project
from app.project_admin.serializers import ProjectListSerializer

class EmployeeAssignedProjectsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: ProjectListSerializer(many=True)})
    def get(self, request):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can access this."}, status=status.HTTP_403_FORBIDDEN)
        
        projects = request.user.assigned_projects.all()
        serializer = ProjectListSerializer(projects, many=True)
        return Response({"projects": serializer.data}, status=status.HTTP_200_OK)

class EmployeeAvailableProjectsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: ProjectListSerializer(many=True)})
    def get(self, request):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can access this."}, status=status.HTTP_403_FORBIDDEN)
            
        if not request.user.company:
            return Response({"error": "You do not belong to any company."}, status=status.HTTP_400_BAD_REQUEST)

        # Get all projects in the company
        projects = Project.objects.filter(company=request.user.company)
        serializer = ProjectListSerializer(projects, many=True)
        return Response({"projects": serializer.data}, status=status.HTTP_200_OK)

class EmployeeAssignProjectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can access this."}, status=status.HTTP_403_FORBIDDEN)
            
        if not request.user.company:
            return Response({"error": "You do not belong to any company."}, status=status.HTTP_400_BAD_REQUEST)

        project_id = request.data.get("project_id")
        if not project_id:
            return Response({"error": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = Project.objects.get(id=project_id, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found or you do not have access to it."}, status=status.HTTP_404_NOT_FOUND)

        # Check if already assigned
        if request.user.assigned_projects.filter(id=project_id).exists():
            return Response({"message": "You are already assigned to this project."}, status=status.HTTP_200_OK)

        # Self-assign to project
        request.user.assigned_projects.add(project)
        
        # Also create a RoleAssignment to mark them as an employee on this project
        from app.account.models import RoleAssignment
        RoleAssignment.objects.get_or_create(
            user=request.user,
            role='employee',
            project=project,
            company=request.user.company
        )

        return Response({"message": "Successfully assigned to project."}, status=status.HTTP_200_OK)

from django.utils import timezone
from .models import AttendanceLog

class AttendanceStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can access this."}, status=status.HTTP_403_FORBIDDEN)
            
        # Get today's active check-in if it exists
        today = timezone.now().date()
        active_log = AttendanceLog.objects.filter(
            user=request.user,
            date=today,
            status='checked_in'
        ).first()

        if active_log:
            return Response({
                "status": "checked_in",
                "project_id": str(active_log.project.id),
                "project_name": active_log.project.project_name,
                "check_in_time": active_log.check_in_time
            }, status=status.HTTP_200_OK)
        else:
            return Response({"status": "checked_out"}, status=status.HTTP_200_OK)

class CheckInView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can access this."}, status=status.HTTP_403_FORBIDDEN)
            
        project_id = request.data.get("project_id")
        lat = request.data.get("lat")
        long = request.data.get("long")

        if not project_id:
            return Response({"error": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = Project.objects.get(id=project_id, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.now().date()
        
        # Check if already checked in
        active_log = AttendanceLog.objects.filter(
            user=request.user,
            date=today,
            status='checked_in'
        ).first()

        if active_log:
            if active_log.project.id == project.id:
                return Response({"error": "Already checked in to this project today."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"error": f"You are currently checked into '{active_log.project.name}'. Please check out first before checking into a new project."}, status=status.HTTP_400_BAD_REQUEST)

        # Create new check-in
        new_log = AttendanceLog.objects.create(
            user=request.user,
            project=project,
            company=request.user.company,
            date=today,
            check_in_lat=float(lat) if lat is not None else None,
            check_in_long=float(long) if long is not None else None,
            status='checked_in'
        )

        return Response({"message": "Successfully checked in.", "log_id": str(new_log.id)}, status=status.HTTP_201_CREATED)

class CheckOutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can access this."}, status=status.HTTP_403_FORBIDDEN)

        lat = request.data.get("lat")
        long = request.data.get("long")
        today = timezone.now().date()

        active_log = AttendanceLog.objects.filter(
            user=request.user,
            date=today,
            status='checked_in'
        ).first()

        if not active_log:
            return Response({"error": "You are not currently checked in."}, status=status.HTTP_400_BAD_REQUEST)

        active_log.check_out_time = timezone.now()
        if lat is not None: active_log.check_out_lat = float(lat)
        if long is not None: active_log.check_out_long = float(long)
        active_log.status = 'checked_out'
        active_log.save()

        return Response({"message": "Successfully checked out."}, status=status.HTTP_200_OK)


class MyFoldersView(APIView):
    """
    Returns the folders and subfolders assigned to the currently authenticated employee
    for their active (checked-in) project.
    
    Folder-level assignment: if any subfolder in a folder is assigned to this user,
    the full folder (with only their assigned subfolders) is returned.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can access this."}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.now().date()
        active_log = AttendanceLog.objects.filter(
            user=request.user,
            date=today,
            status='checked_in'
        ).select_related('project').first()

        if not active_log:
            return Response({"folders": []}, status=status.HTTP_200_OK)

        project = active_log.project

        # Get all FolderAssignments for this user in this project
        from app.project_admin.models import FolderAssignment, ProjectFolder
        assignments = FolderAssignment.objects.filter(
            user=request.user,
            subfolder__folder__project=project
        ).select_related('subfolder', 'subfolder__folder')

        if not assignments.exists():
            return Response({"folders": []}, status=status.HTTP_200_OK)

        # Group assignments by folder
        folder_map = {}
        for assignment in assignments:
            subfolder = assignment.subfolder
            folder = subfolder.folder
            folder_id = str(folder.id)

            if folder_id not in folder_map:
                folder_map[folder_id] = {
                    "id": folder_id,
                    "name": folder.name,
                    "is_management": folder.is_management,
                    "subfolders": []
                }

            folder_map[folder_id]["subfolders"].append({
                "id": str(subfolder.id),
                "name": subfolder.name,
                "project_value": str(subfolder.project_value),
                "labour_target": str(subfolder.labour_target),
                "rows": subfolder.rows,
                "hide_labour_target": assignment.hide_labour_target,
            })

        return Response({"folders": list(folder_map.values())}, status=status.HTTP_200_OK)

from .models import RFI
from .serializers import RFISerializer, DailyRegisterSerializer
import cloudinary.uploader

class RFIListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=RFISerializer(many=True))
    def get(self, request):
        active_log = AttendanceLog.objects.filter(
            user=request.user,
            status='checked_in'
        ).first()

        if not active_log:
            return Response([], status=status.HTTP_200_OK)

        rfis = RFI.objects.filter(project=active_log.project)
        serializer = RFISerializer(rfis, many=True)
        return Response(serializer.data)

class DailyRegister(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        project_id = request.query_params.get('project_id')
        
        if user.role in ["super_admin", "admin", "project_director", "managing_director"]:
            logs = AttendanceLog.objects.filter(company=user.company)
        else:
            logs = AttendanceLog.objects.filter(project__in=user.assigned_projects.all())
            
        if project_id:
            logs = logs.filter(project_id=project_id)
            
        serializer = DailyRegisterSerializer(logs.order_by('-check_in_time'), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

from rest_framework.parsers import MultiPartParser, FormParser

class RFICreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        active_log = AttendanceLog.objects.filter(
            user=request.user,
            status='checked_in'
        ).first()

        if not active_log:
            return Response({"error": "You must be checked into a project to create an RFI."}, status=status.HTTP_400_BAD_REQUEST)

        description = request.data.get('description')
        attachment = request.FILES.get('attachment')

        if not description:
            return Response({"error": "Description is required."}, status=status.HTTP_400_BAD_REQUEST)

        document_url = None
        if attachment:
            try:
                # Upload to Cloudinary
                upload_result = cloudinary.uploader.upload(
                    attachment,
                    resource_type='auto',
                    folder=f"josue_rfis/{active_log.project.id}"
                )
                document_url = upload_result.get('secure_url')
            except Exception as e:
                return Response({"error": f"Failed to upload document: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        rfi = RFI.objects.create(
            project=active_log.project,
            created_by=request.user,
            description=description,
            document_url=document_url
        )

        serializer = RFISerializer(rfi)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


from .models import RAMS, DailyBriefing, ToolboxTalk, ToDoList
from .serializers import RAMSSerializer, DailyBriefingSerializer, ToolboxTalkSerializer, ToDoListSerializer

class OperationsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get('project_id')
        if not project_id:
            return Response({"error": "project_id is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        # Optional: check if user has access to project
        # ...
        
        rams = RAMS.objects.filter(project_id=project_id)
        briefings = DailyBriefing.objects.filter(project_id=project_id)
        toolbox_talks = ToolboxTalk.objects.filter(project_id=project_id)
        todos = ToDoList.objects.filter(project_id=project_id)
        
        return Response({
            "rams": RAMSSerializer(rams, many=True).data,
            "briefings": DailyBriefingSerializer(briefings, many=True).data,
            "toolbox_talks": ToolboxTalkSerializer(toolbox_talks, many=True).data,
            "todos": ToDoListSerializer(todos, many=True).data
        }, status=status.HTTP_200_OK)


class RAMSCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        project_id = request.data.get('project_id')
        title = request.data.get('title')
        date = request.data.get('date')
        review_date = request.data.get('review_date')
        attachment = request.FILES.get('attachment')
        
        if not project_id:
            return Response({"error": "Please select a project to assign this RAMS to."}, status=status.HTTP_400_BAD_REQUEST)
        if not title:
            return Response({"error": "Please enter a valid title for this RAMS."}, status=status.HTTP_400_BAD_REQUEST)
        if not date:
            return Response({"error": "Please select a date."}, status=status.HTTP_400_BAD_REQUEST)

        document_url = None
        if attachment:
            try:
                upload_result = cloudinary.uploader.upload(
                    attachment,
                    resource_type='auto',
                    folder=f"josue_operations/{project_id}/rams"
                )
                document_url = upload_result.get('secure_url')
            except Exception as e:
                return Response({"error": f"Failed to upload document: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
                
        rams = RAMS.objects.create(
            project_id=project_id,
            created_by=request.user,
            title=title,
            date=date,
            review_date=review_date if review_date else None,
            document_url=document_url
        )
        return Response(RAMSSerializer(rams).data, status=status.HTTP_201_CREATED)

class DailyBriefingCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        project_id = request.data.get('project_id')
        title = request.data.get('title')
        date = request.data.get('date')
        attachment = request.FILES.get('attachment')
        
        if not project_id:
            return Response({"error": "Please select a project to assign this Daily Briefing to."}, status=status.HTTP_400_BAD_REQUEST)
        if not title:
            return Response({"error": "Please enter a valid title for this Daily Briefing."}, status=status.HTTP_400_BAD_REQUEST)
        if not date:
            return Response({"error": "Please select a date."}, status=status.HTTP_400_BAD_REQUEST)

        document_url = None
        if attachment:
            try:
                upload_result = cloudinary.uploader.upload(
                    attachment,
                    resource_type='auto',
                    folder=f"josue_operations/{project_id}/briefings"
                )
                document_url = upload_result.get('secure_url')
            except Exception as e:
                return Response({"error": f"Failed to upload document: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
                
        try:
            briefing = DailyBriefing.objects.create(
                project_id=project_id,
                created_by=request.user,
                title=title,
                date=date,
                document_url=document_url
            )
        except Exception as e:
            return Response({"error": f"Invalid data provided: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DailyBriefingSerializer(briefing).data, status=status.HTTP_201_CREATED)

class ToolboxTalkCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        project_id = request.data.get('project_id')
        title = request.data.get('title')
        date = request.data.get('date')
        attachment = request.FILES.get('attachment')
        
        if not project_id:
            return Response({"error": "Please select a project to assign this Toolbox Talk to."}, status=status.HTTP_400_BAD_REQUEST)
        if not title:
            return Response({"error": "Please enter a valid title for this Toolbox Talk."}, status=status.HTTP_400_BAD_REQUEST)
        if not date:
            return Response({"error": "Please select a date."}, status=status.HTTP_400_BAD_REQUEST)

        document_url = None
        if attachment:
            try:
                upload_result = cloudinary.uploader.upload(
                    attachment,
                    resource_type='auto',
                    folder=f"josue_operations/{project_id}/toolbox_talks"
                )
                document_url = upload_result.get('secure_url')
            except Exception as e:
                return Response({"error": f"Failed to upload document: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
                
        toolbox = ToolboxTalk.objects.create(
            project_id=project_id,
            created_by=request.user,
            title=title,
            date=date,
            document_url=document_url
        )
        return Response(ToolboxTalkSerializer(toolbox).data, status=status.HTTP_201_CREATED)

class ToDoCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        project_id = request.data.get('project_id')
        title = request.data.get('title')
        date = request.data.get('date')
        completion_date = request.data.get('completion_date')
        assign_user = request.data.get('assign_user')
        
        if not project_id:
            return Response({"error": "Please select a project to assign this To Do item to."}, status=status.HTTP_400_BAD_REQUEST)
        if not title:
            return Response({"error": "Please enter a valid title for this To Do item."}, status=status.HTTP_400_BAD_REQUEST)
        if not date:
            return Response({"error": "Please select a date."}, status=status.HTTP_400_BAD_REQUEST)

        todo = ToDoList.objects.create(
            project_id=project_id,
            created_by=request.user,
            title=title,
            date=date,
            completion_date=completion_date if completion_date else None,
            assign_user=assign_user
        )
        return Response(ToDoListSerializer(todo).data, status=status.HTTP_201_CREATED)
class CompanyEmployeeListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.company:
            return Response({"error": "User has no associated company."}, status=status.HTTP_400_BAD_REQUEST)
        
        from app.account.models import UserAccount
        users = UserAccount.objects.filter(
            company=request.user.company,
            role=UserAccount.Role.EMPLOYEE
        )
        
        user_list = [{"id": str(u.id), "name": u.full_name} for u in users]
        
        return Response({"users": user_list}, status=status.HTTP_200_OK)
