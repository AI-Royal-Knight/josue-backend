from rest_framework.views import APIView
from rest_framework.response import Response
from decimal import Decimal, InvalidOperation
from datetime import datetime
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
from app.project_admin.models import VariationsAccess, LoadingClearingAccess, LoadingClearingBooking
from app.commercial_department.models import Variation

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
            has_variations_access = VariationsAccess.objects.filter(
                project=active_log.project,
                user=request.user,
                is_active=True
            ).exists()

            next_variation_no = f"VO-{str(Variation.objects.count() + 1).zfill(3)}"

            return Response({
                "status": "checked_in",
                "project_id": str(active_log.project.id),
                "project_name": active_log.project.project_name,
                "check_in_time": active_log.check_in_time,
                "has_variations_access": has_variations_access,
                "next_variation_no": next_variation_no
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
                }

        return Response({"folders": list(folder_map.values())}, status=status.HTTP_200_OK)


class MyFolderSubfoldersView(APIView):
    """
    Returns all assigned subfolders for a specific project folder
    for the current employee on their active project.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, folder_id):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can access this."}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.now().date()
        active_log = AttendanceLog.objects.filter(
            user=request.user,
            date=today,
            status='checked_in'
        ).select_related('project').first()

        if not active_log:
            return Response({"subfolders": []}, status=status.HTTP_200_OK)

        project = active_log.project

        from app.project_admin.models import FolderAssignment
        assignments = FolderAssignment.objects.filter(
            user=request.user,
            subfolder__folder__id=folder_id,
            subfolder__folder__project=project
        ).select_related('subfolder', 'subfolder__folder')

        if not assignments.exists():
            return Response({"subfolders": []}, status=status.HTTP_200_OK)

        subfolders_data = []
        for assignment in assignments:
            subfolder = assignment.subfolder
            
            calculated_labour_target = 0
            if subfolder.rows:
                for row in subfolder.rows:
                    val = row.get("labourTarget", 0)
                    try:
                        calculated_labour_target += float(val) if val else 0
                    except (ValueError, TypeError):
                        pass
            if calculated_labour_target == 0 and subfolder.labour_target:
                calculated_labour_target = float(subfolder.labour_target)

            subfolders_data.append({
                "id": str(subfolder.id),
                "name": subfolder.name,
                "project_value": str(subfolder.project_value),
                "labour_target": str(calculated_labour_target),
                "rows": subfolder.rows,
                "hide_labour_target": assignment.hide_labour_target,
                "assignment_id": str(assignment.id),
                "employee_labour_value": str(assignment.employee_labour_value) if assignment.employee_labour_value is not None else None,
            })

        return Response({"subfolders": subfolders_data}, status=status.HTTP_200_OK)


class SubmitLabourTargetView(APIView):
    """
    Allows an employee to submit their own labour target value if the management's
    target is hidden.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, assignment_id):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can access this."}, status=status.HTTP_403_FORBIDDEN)

        from app.project_admin.models import FolderAssignment
        try:
            assignment = FolderAssignment.objects.get(id=assignment_id, user=request.user)
        except FolderAssignment.DoesNotExist:
            return Response({"error": "Assignment not found."}, status=status.HTTP_404_NOT_FOUND)

        value = request.data.get('employee_labour_value')
        if value is None:
            return Response({"error": "employee_labour_value is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            assignment.employee_labour_value = float(value)
            assignment.save()

            # Auto-generate a UserInvoice
            try:
                from app.project_admin.models import UserInvoice
                UserInvoice.objects.create(
                    project=assignment.subfolder.folder.project,
                    created_by=request.user,
                    source_type=UserInvoice.SourceType.LABOUR_TARGET,
                    source_id=str(assignment.id),
                    work_area=assignment.subfolder.name,
                    description=f"Labour Target – {assignment.subfolder.name}",
                    total=float(value),
                    status=UserInvoice.Status.BUCKET,
                )
            except Exception as e:
                import traceback
                with open("/tmp/invoice_error.log", "a") as f:
                    f.write(f"Labour Target Error: {str(e)}\n")
                    f.write(traceback.format_exc() + "\n")

            return Response({"message": "Labour target submitted successfully."}, status=status.HTTP_200_OK)
        except ValueError:
            return Response({"error": "Invalid value provided."}, status=status.HTTP_400_BAD_REQUEST)


class SubfolderTasksView(APIView):
    """
    Returns the individual task rows for a specific subfolder assignment.
    Each row represents a dedicated task with its sent_to_bucket status.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, assignment_id):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can access this."}, status=status.HTTP_403_FORBIDDEN)

        from app.project_admin.models import FolderAssignment, UserInvoice
        try:
            assignment = FolderAssignment.objects.select_related(
                'subfolder', 'subfolder__folder', 'subfolder__folder__project'
            ).get(id=assignment_id, user=request.user)
        except FolderAssignment.DoesNotExist:
            return Response({"error": "Assignment not found."}, status=status.HTTP_404_NOT_FOUND)

        subfolder = assignment.subfolder
        rows = subfolder.rows or []

        # Find which row indices have already been submitted as UserInvoices
        # source_id format: "assignment_id:row_index"
        submitted_source_ids = set(
            UserInvoice.objects.filter(
                project=subfolder.folder.project,
                created_by=request.user,
                source_type=UserInvoice.SourceType.LABOUR_TARGET,
                source_id__startswith=f"{str(assignment_id)}:",
            ).values_list('source_id', flat=True)
        )
        submitted_row_indices = set()
        for sid in submitted_source_ids:
            parts = sid.split(":")
            if len(parts) == 2:
                try:
                    submitted_row_indices.add(int(parts[1]))
                except ValueError:
                    pass

        tasks = []
        for i, row in enumerate(rows):
            work_section = row.get('workSection', '') or ''
            work_area = row.get('workArea', '') or ''
            labour_target = row.get('labourTarget', None)
            project_value = row.get('projectValue', None)

            # Skip completely empty rows
            if not work_section and not work_area and not labour_target:
                continue

            tasks.append({
                "row_index": i,
                "work_section": work_section,
                "work_area": work_area,
                "labour_target": str(labour_target) if labour_target is not None else None,
                "project_value": str(project_value) if project_value is not None else None,
                "sent_to_bucket": i in submitted_row_indices,
            })

        # Sort tasks so unfinished (sent_to_bucket=False) appear first
        tasks.sort(key=lambda t: (t['sent_to_bucket'], t['row_index']))

        return Response({
            "subfolder_name": subfolder.name,
            "assignment_id": str(assignment.id),
            "hide_labour_target": assignment.hide_labour_target,
            "total_labour_target": str(assignment.subfolder.labour_target or 0),
            "tasks": tasks,
        }, status=status.HTTP_200_OK)


class SubmitSubfolderTaskView(APIView):
    """
    Submits a single row/task from a subfolder to the bucket.
    Each row is tracked individually via source_id = "assignment_id:row_index"
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, assignment_id):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can access this."}, status=status.HTTP_403_FORBIDDEN)

        from app.project_admin.models import FolderAssignment, UserInvoice
        try:
            assignment = FolderAssignment.objects.select_related(
                'subfolder', 'subfolder__folder', 'subfolder__folder__project'
            ).get(id=assignment_id, user=request.user)
        except FolderAssignment.DoesNotExist:
            return Response({"error": "Assignment not found."}, status=status.HTTP_404_NOT_FOUND)

        row_index = request.data.get('row_index')
        if row_index is None:
            return Response({"error": "row_index is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            row_index = int(row_index)
        except (ValueError, TypeError):
            return Response({"error": "row_index must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        subfolder = assignment.subfolder
        rows = subfolder.rows or []

        if row_index < 0 or row_index >= len(rows):
            return Response({"error": "Invalid row_index."}, status=status.HTTP_400_BAD_REQUEST)

        row = rows[row_index]
        work_section = row.get('workSection', '') or ''
        work_area = row.get('workArea', '') or ''
        labour_target = row.get('labourTarget', None)

        # Check if already submitted
        source_id = f"{str(assignment_id)}:{row_index}"
        if UserInvoice.objects.filter(
            project=subfolder.folder.project,
            created_by=request.user,
            source_type=UserInvoice.SourceType.LABOUR_TARGET,
            source_id=source_id,
        ).exists():
            return Response({"error": "This task has already been sent to the bucket."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = float(labour_target) if labour_target else 0.0
        except (ValueError, TypeError):
            amount = 0.0

        # Allow employee to override amount if hide_labour_target is True
        if assignment.hide_labour_target:
            employee_amount = request.data.get('amount')
            if employee_amount is not None:
                try:
                    amount = float(employee_amount)
                except (ValueError, TypeError):
                    return Response({"error": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)

        description_parts = []
        if work_section:
            description_parts.append(work_section)
        if work_area:
            description_parts.append(work_area)
        description = " – ".join(description_parts) if description_parts else subfolder.name

        try:
            UserInvoice.objects.create(
                project=subfolder.folder.project,
                created_by=request.user,
                source_type=UserInvoice.SourceType.LABOUR_TARGET,
                source_id=source_id,
                work_area=work_area,
                work_section=work_section,
                description=f"Labour Target – {description}",
                total=amount,
                status=UserInvoice.Status.BUCKET,
            )
        except Exception as e:
            import traceback
            with open("/tmp/invoice_error.log", "a") as f:
                f.write(f"Subfolder Task Error: {str(e)}\n")
                f.write(traceback.format_exc() + "\n")
            return Response({"error": "Failed to create invoice."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"message": "Task sent to bucket successfully.", "source_id": source_id}, status=status.HTTP_201_CREATED)


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
        if request.user.role not in ['manager', 'project_director', 'admin', 'super_admin']:
            return Response({"error": "Only managers can create operations."}, status=status.HTTP_403_FORBIDDEN)
            
        project_id = request.data.get('project_id')
        title = request.data.get('title')
        description = request.data.get('description')
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
            description=description,
            date=date,
            review_date=review_date if review_date else None,
            document_url=document_url
        )
        return Response(RAMSSerializer(rams).data, status=status.HTTP_201_CREATED)

class DailyBriefingCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if request.user.role not in ['manager', 'project_director', 'admin', 'super_admin']:
            return Response({"error": "Only managers can create operations."}, status=status.HTTP_403_FORBIDDEN)
            
        project_id = request.data.get('project_id')
        title = request.data.get('title')
        description = request.data.get('description')
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
                description=description,
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
        if request.user.role not in ['manager', 'project_director', 'admin', 'super_admin']:
            return Response({"error": "Only managers can create operations."}, status=status.HTTP_403_FORBIDDEN)
            
        project_id = request.data.get('project_id')
        title = request.data.get('title')
        description = request.data.get('description')
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
            description=description,
            date=date,
            document_url=document_url
        )
        return Response(ToolboxTalkSerializer(toolbox).data, status=status.HTTP_201_CREATED)

class OperationCompleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request, op_type, op_id):
        from django.utils import timezone
        
        models_map = {
            'rams': RAMS,
            'briefings': DailyBriefing,
            'toolbox-talks': ToolboxTalk,
            'todos': ToDoList
        }
        
        if op_type not in models_map:
            return Response({"error": "Invalid operation type"}, status=status.HTTP_400_BAD_REQUEST)
            
        model = models_map[op_type]
        try:
            instance = model.objects.get(id=op_id)
        except model.DoesNotExist:
            return Response({"error": "Operation not found"}, status=status.HTTP_404_NOT_FOUND)
            
        attachment = request.FILES.get('signature')
        signed_document_url = None
        
        if attachment:
            try:
                upload_result = cloudinary.uploader.upload(
                    attachment,
                    resource_type='auto',
                    folder=f"josue_operations/{instance.project.id}/signatures/{op_type}"
                )
                signed_document_url = upload_result.get('secure_url')
            except Exception as e:
                return Response({"error": f"Failed to upload document: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
                
        instance.completed_at = timezone.now()
        if signed_document_url:
            instance.signed_document_url = signed_document_url
            
        if op_type == 'todos':
            instance.completion_date = timezone.now().date()
            
        instance.save()
        return Response({"message": "Operation completed successfully"}, status=status.HTTP_200_OK)

class ToDoCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'manager':
            return Response({"error": "Only managers can create To Do items."}, status=status.HTTP_403_FORBIDDEN)
        project_id = request.data.get('project_id')
        title = request.data.get('title')
        description = request.data.get('description')
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
            description=description,
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

class LoadingClearingSubmitView(APIView):
    """
    Submit a Loading & Clearing booking.
    The employee must have an active LoadingClearingAccess for their current project.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can submit loading & clearing"}, status=status.HTTP_403_FORBIDDEN)

        # 1. Get the employee's active project from AttendanceLog
        today = timezone.localtime().date()
        try:
            attendance = AttendanceLog.objects.filter(
                user=request.user,
                date=today,
                check_in_time__isnull=False,
                check_out_time__isnull=True
            ).latest('check_in_time')
            active_project = attendance.project
        except AttendanceLog.DoesNotExist:
            return Response({"error": "You must be checked into a project to submit loading & clearing."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Check if user has LoadingClearingAccess for this project
        has_access = LoadingClearingAccess.objects.filter(
            project=active_project,
            user=request.user,
            is_active=True
        ).exists()

        if not has_access:
            return Response({"error": "You do not have Loading & Clearing access for this project."}, status=status.HTTP_403_FORBIDDEN)

        # 3. Extract and validate data
        data = request.data
        try:
            amount = Decimal(data.get("amount", 0))
            date_str = data.get("date")
            description = data.get("description", "")
            if not date_str:
                return Response({"error": "Date is required"}, status=status.HTTP_400_BAD_REQUEST)
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError, InvalidOperation):
            return Response({"error": "Invalid data format provided."}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Handle attachments
        attachment_urls = []
        attachments = request.FILES.getlist('attachments')
        for f in attachments:
            try:
                import cloudinary.uploader
                upload_result = cloudinary.uploader.upload(
                    f,
                    folder="josue/loading_clearing",
                    resource_type="auto"
                )
                attachment_urls.append(upload_result.get('secure_url'))
            except Exception as e:
                return Response({"error": f"Failed to upload attachment: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 5. Create the booking
        booking = LoadingClearingBooking.objects.create(
            project=active_project,
            user=request.user,
            amount=amount,
            description=description,
            attachment_urls=attachment_urls,
            date=booking_date
        )

        # 6. Auto-generate a UserInvoice
        try:
            from app.project_admin.models import UserInvoice
            UserInvoice.objects.create(
                project=active_project,
                created_by=request.user,
                source_type=UserInvoice.SourceType.LOADING_CLEARING,
                source_id=str(booking.id),
                description=description or "Loading & Clearing submission",
                total=amount,
                status=UserInvoice.Status.BUCKET,
            )
        except Exception as e:
            import traceback
            with open("/tmp/invoice_error.log", "a") as f:
                f.write(f"Loading Clearing Error: {str(e)}\n")
                f.write(traceback.format_exc() + "\n")  # Don't fail the main response if invoice creation fails

        return Response({
            "message": "Loading and clearing submitted successfully.",
            "booking_id": booking.id
        }, status=status.HTTP_201_CREATED)

class EmployeeVariationsListView(APIView):
    """
    Get a list of Variations assigned to the employee for their active project.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can view assigned variations"}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localtime().date()
        try:
            attendance = AttendanceLog.objects.filter(
                user=request.user,
                date=today,
                check_in_time__isnull=False,
                check_out_time__isnull=True
            ).latest('check_in_time')
            active_project = attendance.project
        except AttendanceLog.DoesNotExist:
            return Response({"error": "You must be checked into a project."}, status=status.HTTP_400_BAD_REQUEST)

        from app.commercial_department.models import Variation
        from app.project_admin.models import UserInvoice
        
        # Get variations assigned to this user in this project
        variations = Variation.objects.filter(
            project=active_project,
            assigned_users=request.user
        ).prefetch_related('lines')

        # Pre-fetch the set of submitted variation IDs for this user
        submitted_variation_ids = set(
            UserInvoice.objects.filter(
                created_by=request.user,
                source_type=UserInvoice.SourceType.VARIATION
            ).values_list('source_id', flat=True)
        )

        data = []
        for v in variations:
            lines_data = []
            for line in v.lines.all():
                lines_data.append({
                    "id": str(line.id),
                    "work_area": line.work_area,
                    "work_section": line.work_section,
                    "labour": str(line.labour),
                    "qty": str(line.qty),
                    "line_total": str(line.line_total)
                })
            
            data.append({
                "id": str(v.id),
                "vo_number": v.vo_number,
                "project_name": v.project.project_name,
                "site_instruction_no": v.site_instruction_no,
                "attention_of": v.attention_of,
                "description_of_works": v.description_of_works,
                "comments": v.comments,
                "evidence_url": v.evidence_url,
                "total_amount": str(v.total_amount),
                "lines": lines_data,
                "is_submitted": str(v.id) in submitted_variation_ids
            })
            
        return Response({"variations": data}, status=status.HTTP_200_OK)

class VariationSubmitView(APIView):
    """
    Submit an existing assigned Variation to the Bucket List.
    The employee must be checked into a project.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can submit variations"}, status=status.HTTP_403_FORBIDDEN)

        # 1. Get the employee's active project from AttendanceLog
        today = timezone.localtime().date()
        try:
            attendance = AttendanceLog.objects.filter(
                user=request.user,
                date=today,
                check_in_time__isnull=False,
                check_out_time__isnull=True
            ).latest('check_in_time')
            active_project = attendance.project
        except AttendanceLog.DoesNotExist:
            return Response({"error": "You must be checked into a project to submit variations."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Check if user has VariationsAccess for this project
        has_access = VariationsAccess.objects.filter(
            project=active_project,
            user=request.user,
            is_active=True
        ).exists()

        if not has_access:
            return Response({"error": "You do not have Variations access for this project."}, status=status.HTTP_403_FORBIDDEN)

        # 3. Extract data
        variation_id = request.data.get("variation_id")
        if not variation_id:
            return Response({"error": "variation_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        from app.commercial_department.models import Variation
        try:
            variation = Variation.objects.get(id=variation_id, project=active_project, assigned_users=request.user)
        except Variation.DoesNotExist:
            return Response({"error": "Variation not found or not assigned to you."}, status=status.HTTP_404_NOT_FOUND)

        # 4. Auto-generate a UserInvoice (Bucket list item)
        try:
            from app.project_admin.models import UserInvoice
            UserInvoice.objects.create(
                project=active_project,
                created_by=request.user,
                source_type=UserInvoice.SourceType.VARIATION,
                source_id=str(variation.id),
                variation_sheet_no=variation.vo_number,
                description=variation.description_of_works or f"Variation {variation.vo_number}",
                total=variation.total_amount,
                status=UserInvoice.Status.BUCKET,
            )
        except Exception as e:
            import traceback
            with open("/tmp/invoice_error.log", "a") as f:
                f.write(f"Variation Error: {str(e)}\n")
                f.write(traceback.format_exc() + "\n")  # Don't fail the main response if invoice creation fails

        return Response({
            "message": "Variation submitted to Bucket List successfully.",
            "variation_id": str(variation.id)
        }, status=status.HTTP_201_CREATED)

class ProformaNRSubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'employee':
            return Response({"error": "Only employees can submit Proforma NR."}, status=status.HTTP_403_FORBIDDEN)

        # 1. Get the employee's active project from AttendanceLog
        today = timezone.localtime().date()
        try:
            attendance = AttendanceLog.objects.filter(
                user=request.user,
                date=today,
                check_in_time__isnull=False,
                check_out_time__isnull=True
            ).latest('check_in_time')
            active_project = attendance.project
        except AttendanceLog.DoesNotExist:
            return Response({"error": "You must be checked into a project to submit proforma NR."}, status=status.HTTP_400_BAD_REQUEST)

        description = request.data.get("description", "")
        amount_str = request.data.get("amount", "0")

        try:
            amount = Decimal(str(amount_str))
        except (ValueError, TypeError, InvalidOperation):
            return Response({"error": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)

        from app.finance_department.models import ProformaNR
        import datetime

        proforma = ProformaNR.objects.create(
            project=active_project,
            amount=amount,
            date=datetime.date.today()
        )

        # Auto-generate a UserInvoice
        try:
            from app.project_admin.models import UserInvoice
            UserInvoice.objects.create(
                project=active_project,
                created_by=request.user,
                source_type=UserInvoice.SourceType.PROFORMA,
                source_id=str(proforma.id),
                description=description or "Proforma NR submission",
                total=amount,
                status=UserInvoice.Status.BUCKET,
            )
        except Exception as e:
            import traceback
            with open("/tmp/invoice_error.log", "a") as f:
                f.write(f"Proforma Error: {str(e)}\n")
                f.write(traceback.format_exc() + "\n")

        return Response({
            "message": "Proforma NR submitted successfully.",
            "proforma_id": proforma.id
        }, status=status.HTTP_201_CREATED)

class EmployeeHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from app.project_admin.models import UserInvoice
        
        invoices = UserInvoice.objects.filter(created_by=request.user).order_by('-date', '-created_at')
        
        history_data = []
        for invoice in invoices:
            status_text = "Pending"
            if invoice.status == UserInvoice.Status.BUCKET:
                status_text = "Bucket"
            elif invoice.finance_paid:
                status_text = "Paid"
            elif invoice.managing_director_approved or invoice.project_director_approved or invoice.contracts_manager_approved or invoice.manager_approved or invoice.supervisor_approved:
                status_text = "Approved"
            elif invoice.status == UserInvoice.Status.SUBMITTED:
                status_text = "Submitted"

            section = invoice.work_area or invoice.work_section or invoice.get_source_type_display()
            
            history_data.append({
                "id": str(invoice.id),
                "project": invoice.project.project_name if invoice.project else "Unknown",
                "section": section,
                "date": invoice.date.strftime("%b %d, %Y") if invoice.date else "",
                "items": 1,
                "amount": float(invoice.total),
                "status": status_text,
            })
            
        return Response({"history": history_data}, status=status.HTTP_200_OK)
