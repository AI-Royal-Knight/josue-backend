from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from drf_spectacular.utils import extend_schema

from app.account.permissions import (
    IsAdmin, 
    IsAdminOrProjectAdmin, 
    CanManageProjectFolders, 
    CanManageProjectRoles, 
    IsAdminOrProjectAdminOrCompanyManager
)
from .models import Project
from .serializers import (
    ProjectListSerializer,
    ProjectCreateSerializer,
    ProjectUpdateSerializer,
)

from django.db.models import Sum
from datetime import date
from dateutil.relativedelta import relativedelta
import calendar

from app.procurement_department.models import PurchaseOrder, POCallOff
from app.commercial_department.models import Variation
from app.finance_department.models import ProformaNR
from .models import (
    LabourBooking,
    PlantHireBooking,
    LoadingClearingBooking,
    ManagementPrelimBooking,
    ProjectValueBooking
)


class MyProjectsView(APIView):
    """Returns projects visible to the currently authenticated user.
    - admin / project_admin  → all projects belonging to their company
    - all other roles        → only the projects they are directly assigned to
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role in ["admin", "project_admin"]:
            if not user.company:
                return Response({"projects": [], "total_count": 0}, status=status.HTTP_200_OK)
            projects = Project.objects.filter(company=user.company)
        else:
            projects = user.assigned_projects.all()

        serializer = ProjectListSerializer(projects, many=True)
        return Response(
            {"projects": serializer.data, "total_count": projects.count()},
            status=status.HTTP_200_OK,
        )


class ProjectListCreateView(APIView):
    permission_classes = [IsAdminOrProjectAdmin]

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


class ProjectFinancialBreakdownView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        start_date = project.start_date or project.created_at.date()
        today = date.today()
        
        app_date = project.monthly_application_date or 15
        
        # Start from the first application period
        current_start = start_date
        if current_start.day >= app_date:
            current_start = current_start.replace(day=app_date)
        else:
            current_start = (current_start - relativedelta(months=1)).replace(day=app_date)
            
        breakdown_data = []
        
        while current_start <= today:
            current_end = current_start + relativedelta(months=1) - relativedelta(days=1)
            
            # Period String
            month_name_start = calendar.month_name[current_start.month]
            month_name_end = calendar.month_name[current_end.month]
            period_str = f"{current_start.day} {month_name_start[:3]} - {current_end.day} {month_name_end[:3]}"

            # Queries
            # Variations
            variations = Variation.objects.filter(project=project, date__lte=current_end, date__gte=current_start)
            var_agg = variations.aggregate(
                val=Sum('total_amount'),
                lab=Sum('lines__labour_target'),
                mat=Sum('lines__material')
            )
            var_val = var_agg['val'] or 0
            var_lab = var_agg['lab'] or 0
            var_mat = var_agg['mat'] or 0
            var_claim = 0  # Deprecated in new Variation schema
            
            # PO Call Offs
            pos = PurchaseOrder.objects.filter(project=project)
            call_offs = POCallOff.objects.filter(po__in=pos, date__lte=current_end, date__gte=current_start, is_approved=True)
            po_called_off = call_offs.aggregate(total=Sum('amount'))['total'] or 0
            
            # Proforma NR
            proformas = ProformaNR.objects.filter(project=project, date__lte=current_end, date__gte=current_start)
            prof_agg = proformas.aggregate(amt=Sum('amount'), mat=Sum('material_estimate'))
            prof_nr = prof_agg['amt'] or 0
            prof_nr_mat = prof_agg['mat'] or 0
            
            # Bookings
            project_value_booked = ProjectValueBooking.objects.filter(project=project, date__lte=current_end, date__gte=current_start, is_approved=True).aggregate(t=Sum('amount'))['t'] or 0
            labour_target = LabourBooking.objects.filter(project=project, date__lte=current_end, date__gte=current_start, is_approved=True).aggregate(t=Sum('amount'))['t'] or 0
            plant_hire = PlantHireBooking.objects.filter(project=project, date__lte=current_end, date__gte=current_start, is_approved=True).aggregate(t=Sum('amount'))['t'] or 0
            loading_clearing = LoadingClearingBooking.objects.filter(project=project, date__lte=current_end, date__gte=current_start, is_approved=True).aggregate(t=Sum('amount'))['t'] or 0
            management_prelims = ManagementPrelimBooking.objects.filter(project=project, date__lte=current_end, date__gte=current_start, is_approved=True).aggregate(t=Sum('amount'))['t'] or 0
            
            # Derived fields
            project_value = project_value_booked
            application_value = project_value + var_claim
            
            # Overspend logic requires knowing actual labour cost, since we don't have payroll yet, default to 0
            overspend = 0
            
            unclaimed = var_val - var_claim
            money_on_hold = 0  # no retainage module yet
            
            breakdown_data.append({
                "period": period_str,
                "applicationValue": float(application_value),
                "projectValue": float(project_value),
                "labourTarget": float(labour_target),
                "overspend": float(overspend),
                "unclaimed": float(unclaimed),
                "moneyOnHold": float(money_on_hold),
                "poCalledOff": float(po_called_off),
                "loadingAndClearing": float(loading_clearing),
                "managementPrelims": float(management_prelims),
                "plantHire": float(plant_hire),
                "proformaNR": float(prof_nr),
                "proformaNRMaterialEstimate": float(prof_nr_mat),
                "variationValue": float(var_val),
                "variationLabourValue": 0, # not tracked separately from var_val yet
                "variationLabourTarget": float(var_lab),
                "variationPoCalledOff": 0, # variation specific POs not tracked
                "variationClaimed": float(var_claim),
            })
            
            current_start += relativedelta(months=1)
            
        return Response({"breakdown": breakdown_data}, status=status.HTTP_200_OK)


class ProjectDetailView(APIView):
    permission_classes = [IsAdminOrProjectAdmin]

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
    permission_classes = [IsAdminOrProjectAdminOrCompanyManager]

    def get(self, request):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)
        
        from app.account.models import UserAccount
        from django.db.models import Q
        
        company = request.user.company
        company_query = Q(company=company)
        
        if company.company_name:
            company_query |= Q(company__company_name__iexact=company.company_name)
        if company.company_number:
            company_query |= Q(company__company_number=company.company_number)
            
        users = UserAccount.objects.filter(company_query).exclude(
            role__in=[UserAccount.Role.SUPER_ADMIN, UserAccount.Role.ADMIN]
        ).distinct()
        role_param = request.query_params.get("role")
        if role_param:
            users = users.filter(role=role_param)
            
        users_data = []
        for user in users:
            name = user.full_name
            if not name:
                name = user.email.split('@')[0]
            users_data.append({
                "id": str(user.id),
                "name": name,
                "email": user.email
            })
            
        print(f"CompanyUsersView(role={role_param}, company={request.user.company}) returned {len(users_data)} users.")
        return Response({"users": users_data}, status=status.HTTP_200_OK)


class ProjectRoleAssignmentsView(APIView):
    permission_classes = [CanManageProjectRoles]

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
            seen_users = set()
            for assignment in role_assignments:
                if assignment.user and assignment.user.id not in seen_users:
                    seen_users.add(assignment.user.id)
                    name = assignment.user.full_name
                    if not name:
                        name = assignment.user.email.split('@')[0]
                    users_data.append({
                        "id": str(assignment.user.id),
                        "name": name,
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

        role_key = request.data.get("role_key")
        user_ids = request.data.get("user_ids", [])

        if not role_key:
            return Response({"error": "role_key is required."}, status=status.HTTP_400_BAD_REQUEST)

        from app.account.models import RoleAssignment, UserAccount
        from django.db.models import Q
        
        # Verify users exist and are in the company (using the same logic as GET)
        company = request.user.company
        company_query = Q(company=company)
        
        if company.company_name:
            company_query |= Q(company__company_name__iexact=company.company_name)
        if company.company_number:
            company_query |= Q(company__company_number=company.company_number)

        users = UserAccount.objects.filter(company_query, id__in=user_ids).distinct()
        
        # Get existing assignments for this role
        old_assignments = RoleAssignment.objects.filter(role=role_key, project=project)
        old_user_ids = list(old_assignments.values_list('user_id', flat=True))

        # Delete existing assignments for this role and project
        old_assignments.delete()
        
        # Create new assignments
        for user in users:
            RoleAssignment.objects.create(
                user=user,
                role=role_key,
                project=project,
                company=request.user.company
            )
            # Add project to user's assigned projects list so they can see it
            if not user.assigned_projects.filter(id=project.id).exists():
                user.assigned_projects.add(project)
                # Create a notification for the user
                from app.account.models import Notification
                Notification.objects.create(
                    user=user,
                    title="Project Assigned",
                    body=f"You have been assigned to {project.project_name} as {role_key}.",
                    type=Notification.Type.PROJECT_ASSIGNED
                )
            
        # For any user removed from this role, if they have no other roles in the project,
        # remove the project from their assigned_projects
        for uid in old_user_ids:
            if uid not in [u.id for u in users]:
                still_assigned = RoleAssignment.objects.filter(user_id=uid, project=project).exists()
                if not still_assigned:
                    try:
                        u = UserAccount.objects.get(id=uid)
                        u.assigned_projects.remove(project)
                    except UserAccount.DoesNotExist:
                        pass
        
        return Response({"message": "Role assignments updated successfully."}, status=status.HTTP_200_OK)


from .models import ProjectFolder, ProjectSubfolder
from .serializers import ProjectFolderSerializer

class ProjectFoldersView(APIView):
    permission_classes = [CanManageProjectFolders]

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
    permission_classes = [CanManageProjectFolders]

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
            import uuid
            def is_valid_uuid(val):
                try:
                    uuid.UUID(str(val))
                    return True
                except ValueError:
                    return False

            # Delete existing folders not in payload (only filter valid UUIDs)
            folder_ids = [f.get("id") for f in folders_data if f.get("id") and is_valid_uuid(f.get("id"))]
            ProjectFolder.objects.filter(project=project).exclude(id__in=folder_ids).delete()
            
            for f_data in folders_data:
                f_id = f_data.get("id")
                f_name = f_data.get("name")
                
                folder = None
                if f_id and is_valid_uuid(f_id):
                    folder = ProjectFolder.objects.filter(id=f_id, project=project).first()
                
                if folder:
                    folder.name = f_name
                    folder.is_management = f_data.get("is_management", False)
                    folder.save()
                else:
                    folder = ProjectFolder.objects.create(project=project, name=f_name, is_management=f_data.get("is_management", False))
                        
                subfolders_data = f_data.get("subfolders", [])
                sub_ids = [s.get("id") for s in subfolders_data if s.get("id") and is_valid_uuid(s.get("id"))]
                ProjectSubfolder.objects.filter(folder=folder).exclude(id__in=sub_ids).delete()
                
                for s_data in subfolders_data:
                    s_id = s_data.get("id")
                    s_name = s_data.get("name")
                    s_rows = s_data.get("rows", [])
                    s_pv = s_data.get("project_value", 0)
                    s_lt = s_data.get("labour_target", 0)
                    
                    sub = None
                    if s_id and is_valid_uuid(s_id):
                        sub = ProjectSubfolder.objects.filter(id=s_id, folder=folder).first()

                    if sub:
                        sub.name = s_name
                        sub.rows = s_rows
                        sub.project_value = s_pv
                        sub.labour_target = s_lt
                        sub.save()
                    else:
                        sub = ProjectSubfolder.objects.create(
                            folder=folder, 
                            name=s_name, 
                            rows=s_rows,
                            project_value=s_pv,
                            labour_target=s_lt
                        )

                    if sub:
                        s_assignments = s_data.get("assignments", [])
                        # extract user_id from either direct 'user_id' key or nested 'user' dict
                        assign_user_ids = []
                        for a in s_assignments:
                            if a.get("user_id"):
                                assign_user_ids.append(a.get("user_id"))
                            elif a.get("user") and isinstance(a.get("user"), dict) and a["user"].get("id"):
                                assign_user_ids.append(a["user"]["id"])
                        
                        from .models import FolderAssignment
                        FolderAssignment.objects.filter(subfolder=sub).exclude(user_id__in=assign_user_ids).delete()
                        
                        from app.account.models import UserAccount
                        for a_data in s_assignments:
                            u_id = a_data.get("user_id")
                            if not u_id and a_data.get("user") and isinstance(a_data.get("user"), dict):
                                u_id = a_data["user"].get("id")
                            if not u_id:
                                continue
                            try:
                                user_obj = UserAccount.objects.get(id=u_id, company=request.user.company)
                                FolderAssignment.objects.update_or_create(
                                    subfolder=sub,
                                    user=user_obj,
                                    defaults={
                                        "hide_labour_target": a_data.get("hide_labour_target", False),
                                        "is_management_assignment": a_data.get("is_management_assignment", False)
                                    }
                                )
                                # Ensure user can see the project
                                user_obj.assigned_projects.add(project)
                            except UserAccount.DoesNotExist:
                                pass

        # return full updated list
        folders = ProjectFolder.objects.filter(project=project)
        serializer = ProjectFolderSerializer(folders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


from .models import ApprovalConfiguration
from .serializers import ApprovalConfigurationSerializer

class ProjectApprovalConfigurationsView(APIView):
    permission_classes = [IsAdminOrProjectAdmin]

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
                    toggle_states=c_data.get("toggle_states", []),
                    is_active=c_data.get("is_active", True)
                )

        configs = ApprovalConfiguration.objects.filter(project=project)
        serializer = ApprovalConfigurationSerializer(configs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



from app.employee.models import RFI, RFIMessage
from app.employee.serializers import DashboardRFISerializer, RFIMessageSerializer

class DashboardRFIListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role in ["admin", "project_admin", "super_admin"]:
            if not user.company:
                return Response({"rfis": []}, status=status.HTTP_200_OK)
            rfis = RFI.objects.filter(project__company=user.company)
        else:
            rfis = RFI.objects.filter(project__in=user.assigned_projects.all())

        serializer = DashboardRFISerializer(rfis.order_by('-created_at'), many=True)
        return Response({"rfis": serializer.data}, status=status.HTTP_200_OK)

class RFICloseView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            rfi = RFI.objects.get(pk=pk)
        except RFI.DoesNotExist:
            return Response({"error": "RFI not found"}, status=status.HTTP_404_NOT_FOUND)
            
        rfi.status = 'CLOSED'
        rfi.save()
        
        serializer = DashboardRFISerializer(rfi)
        return Response(serializer.data, status=status.HTTP_200_OK)

class RFIMessageCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            rfi = RFI.objects.get(pk=pk)
        except RFI.DoesNotExist:
            return Response({"error": "RFI not found"}, status=status.HTTP_404_NOT_FOUND)
            
        text = request.data.get('text', '')
        attachment = request.FILES.get('attachment')
        
        message = RFIMessage.objects.create(
            rfi=rfi,
            author=request.user,
            text=text
        )
        
        if attachment:
            from cloudinary.uploader import upload
            try:
                upload_data = upload(attachment)
                message.document_url = upload_data.get('secure_url')
                message.save()
            except Exception as e:
                pass
                
        serializer = RFIMessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


from .models import ProformaAccess
from .serializers import ProformaAccessSerializer

class ProformaAccessListView(APIView):
    permission_classes = [CanManageProjectRoles]

    def get(self, request, pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = Project.objects.get(pk=pk, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        accesses = ProformaAccess.objects.filter(project=project)
        serializer = ProformaAccessSerializer(accesses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = Project.objects.get(pk=pk, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        user_ids = request.data.get('user_ids', [])
        if not isinstance(user_ids, list):
            return Response({"error": "user_ids must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        from app.account.models import UserAccount
        for u_id in user_ids:
            try:
                u = UserAccount.objects.get(id=u_id, company=request.user.company)
                _, created = ProformaAccess.objects.get_or_create(project=project, user=u)
                if created:
                    created_count += 1
            except UserAccount.DoesNotExist:
                continue

        accesses = ProformaAccess.objects.filter(project=project)
        serializer = ProformaAccessSerializer(accesses, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProformaAccessDetailView(APIView):
    permission_classes = [CanManageProjectRoles]

    def patch(self, request, pk, access_pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            access = ProformaAccess.objects.get(pk=access_pk, project__id=pk, project__company=request.user.company)
        except ProformaAccess.DoesNotExist:
            return Response({"error": "Access not found."}, status=status.HTTP_404_NOT_FOUND)

        is_active = request.data.get('is_active')
        if is_active is not None:
            access.is_active = bool(is_active)
            access.save()

        serializer = ProformaAccessSerializer(access)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk, access_pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            access = ProformaAccess.objects.get(pk=access_pk, project__id=pk, project__company=request.user.company)
            access.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProformaAccess.DoesNotExist:
            return Response({"error": "Access not found."}, status=status.HTTP_404_NOT_FOUND)


from .models import LoadingClearingAccess
from .serializers import LoadingClearingAccessSerializer

class LoadingClearingAccessListView(APIView):
    permission_classes = [CanManageProjectRoles]

    def get(self, request, pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = Project.objects.get(pk=pk, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        accesses = LoadingClearingAccess.objects.filter(project=project)
        serializer = LoadingClearingAccessSerializer(accesses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = Project.objects.get(pk=pk, company=request.user.company)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        user_ids = request.data.get('user_ids', [])
        if not isinstance(user_ids, list):
            return Response({"error": "user_ids must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        from app.account.models import UserAccount
        for u_id in user_ids:
            try:
                u = UserAccount.objects.get(id=u_id, company=request.user.company)
                _, created = LoadingClearingAccess.objects.get_or_create(project=project, user=u)
                if created:
                    created_count += 1
            except UserAccount.DoesNotExist:
                continue

        accesses = LoadingClearingAccess.objects.filter(project=project)
        serializer = LoadingClearingAccessSerializer(accesses, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LoadingClearingAccessDetailView(APIView):
    permission_classes = [CanManageProjectRoles]

    def patch(self, request, pk, access_pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            access = LoadingClearingAccess.objects.get(pk=access_pk, project__id=pk, project__company=request.user.company)
        except LoadingClearingAccess.DoesNotExist:
            return Response({"error": "Access not found."}, status=status.HTTP_404_NOT_FOUND)

        is_active = request.data.get('is_active')
        if is_active is not None:
            access.is_active = bool(is_active)
            access.save()

        serializer = LoadingClearingAccessSerializer(access)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk, access_pk):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            access = LoadingClearingAccess.objects.get(pk=access_pk, project__id=pk, project__company=request.user.company)
            access.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except LoadingClearingAccess.DoesNotExist:
            return Response({"error": "Access not found."}, status=status.HTTP_404_NOT_FOUND)
