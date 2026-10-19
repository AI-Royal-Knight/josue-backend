from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction

from .models import Variation, VariationLine
from .serializers import VariationSerializer
import json
import cloudinary.uploader


def check_project_access(user, project_id):
    if not user.is_authenticated or not user.company:
        return False
    if user.role in ["admin", "project_admin"]:
        from app.project_admin.models import Project
        return Project.objects.filter(id=project_id, company=user.company).exists()
    return user.accessible_projects.filter(id=project_id).exists()


class VariationListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(responses={200: dict})
    def get(self, request):
        """Return all variations the user has access to (filtered by their company's projects / assigned projects)."""
        user = request.user
        if not user.company:
            return Response({"variations": []})

        if user.role in ["admin", "project_admin"]:
            variations = Variation.objects.filter(
                project__company=user.company
            )
        else:
            variations = Variation.objects.filter(
                project__in=user.accessible_projects
            )

        variations = variations.select_related("project", "created_by", "approved_by").prefetch_related("lines")

        # Optional project filter
        project_id = request.query_params.get("project_id")
        if project_id:
            if not check_project_access(user, project_id):
                return Response(
                    {"error": "Not authorized to access this project's variations."},
                    status=status.HTTP_403_FORBIDDEN
                )
            variations = variations.filter(project_id=project_id)

        serializer = VariationSerializer(variations, many=True)
        return Response({"variations": serializer.data})

    @extend_schema(request=dict, responses={200: dict})
    def post(self, request):
        """Create a new variation with line items."""
        project_id = request.data.get("project_id")
        description = request.data.get("description_of_works", "").strip()
        site_instruction_no = request.data.get("site_instruction_no", "")
        attention_of = request.data.get("attention_of", "")
        comments = request.data.get("comments", "")
        lines_data_raw = request.data.get("lines", [])
        
        lines_data = []
        if isinstance(lines_data_raw, str):
            try:
                lines_data = json.loads(lines_data_raw)
            except json.JSONDecodeError:
                lines_data = []
        else:
            lines_data = lines_data_raw
            
        evidence_file = request.FILES.get("evidence")

        if not project_id:
            return Response(
                {"error": "Please select a project for this variation."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not description:
            return Response(
                {"error": "Please provide a description of works."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check project access
        if not check_project_access(request.user, project_id):
            return Response(
                {"error": "You do not have access to this project."},
                status=status.HTTP_403_FORBIDDEN,
            )

        import math
        def safe_float(val, default=0.0):
            try:
                if val is None or str(val).strip() == "":
                    return float(default)
                f_val = float(val)
                if math.isnan(f_val) or math.isinf(f_val):
                    return float(default)
                return f_val
            except (ValueError, TypeError):
                return float(default)

        # Calculate total from lines: (labour + material) * qty
        total_amount = sum(
            (safe_float(l.get("labour")) + safe_float(l.get("material"))) * safe_float(l.get("qty"), 1.0)
            for l in lines_data
        )

        # Determine variation sheet number (A, B, C... based on count for this project)
        count = Variation.objects.filter(project_id=project_id).count()
        sheet_letter = chr(65 + count) if count < 26 else str(count + 1)
        
        evidence_url = ""
        if evidence_file:
            try:
                upload_result = cloudinary.uploader.upload(
                    evidence_file,
                    resource_type='auto',
                    folder=f"josue_variations/{project_id}"
                )
                evidence_url = upload_result.get('secure_url', '')
            except Exception as e:
                print("Cloudinary upload failed for variation evidence, saving to media storage:", str(e))
                from django.core.files.storage import default_storage
                from django.conf import settings
                file_name = default_storage.save(f"variations/{project_id}/{evidence_file.name}", evidence_file)
                evidence_url = request.build_absolute_uri(settings.MEDIA_URL + file_name)

        with transaction.atomic():
            variation = Variation.objects.create(
                project_id=project_id,
                created_by=request.user,
                site_instruction_no=site_instruction_no,
                attention_of=attention_of,
                description_of_works=description,
                comments=comments,
                evidence_url=evidence_url,
                total_amount=total_amount,
                variation_sheet_number=sheet_letter,
            )

            for line in lines_data:
                VariationLine.objects.create(
                    variation=variation,
                    site_instruction=line.get("siteInstruction", ""),
                    work_area=line.get("workArea", ""),
                    work_section=line.get("workSection", ""),
                    labour=safe_float(line.get("labour")),
                    labour_target=safe_float(line.get("labourTarget")),
                    material=safe_float(line.get("material")),
                    qty=safe_float(line.get("qty"), 1.0),
                )

        serializer = VariationSerializer(variation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VariationApprovalView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=dict, responses={200: dict})
    def post(self, request, pk):
        """Approve or reject a variation."""
        action = request.data.get("action")  # "approve" or "reject"

        if action not in ("approve", "reject"):
            return Response(
                {"error": "Invalid action. Use 'approve' or 'reject'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            variation = Variation.objects.get(pk=pk)
        except Variation.DoesNotExist:
            return Response({"error": "Variation not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check project access
        if not check_project_access(request.user, variation.project_id):
            return Response(
                {"error": "You do not have access to this project's variations."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if action == "approve":
            variation.approval_status = Variation.ApprovalStatus.APPROVED
            variation.approved_by = request.user
        else:
            variation.approval_status = Variation.ApprovalStatus.REJECTED
            variation.approved_by = request.user

        variation.save()
        return Response(VariationSerializer(variation).data)

class VariationToggleSignatureView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=dict, responses={200: dict})
    def post(self, request, pk):
        try:
            variation = Variation.objects.get(pk=pk)
        except Variation.DoesNotExist:
            return Response({"error": "Variation not found."}, status=status.HTTP_404_NOT_FOUND)

        if not check_project_access(request.user, variation.project_id):
            return Response(
                {"error": "You do not have access to this project's variations."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = request.user
        role = user.role
        if role == "managers":
            role = "manager"

        ROLE_TO_FIELD = {
            "supervisor": ("supervisor_approved", "supervisor_approved_date"),
            "manager": ("manager_approved", "manager_approved_date"),
            "contracts_manager": ("contracts_manager_approved", "contracts_manager_approved_date"),
            "project_director": ("project_director_approved", "project_director_approved_date"),
            "managing_director": ("managing_director_approved", "managing_director_approved_date"),
            "commercial_department": ("commercial_department_approved", "commercial_department_approved_date"),
        }

        if role not in ROLE_TO_FIELD:
            return Response({"error": "Your role is not permitted to sign variations."}, status=status.HTTP_403_FORBIDDEN)

        approve = request.data.get("approve", True)
        sig_field, date_field = ROLE_TO_FIELD[role]

        setattr(variation, sig_field, approve)
        import datetime
        setattr(variation, date_field, datetime.date.today() if approve else None)
        
        variation.save()
        return Response(VariationSerializer(variation).data)


class VariationSubmitToClientView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=dict, responses={200: dict})
    def post(self, request, pk):
        """Mark variation as submitted to client. Only commercial department allowed."""
        user = request.user
        if user.role != "commercial_department" and user.role not in ["admin", "project_admin"]:
            return Response(
                {"error": "Only the commercial department can issue variations to clients."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            variation = Variation.objects.select_related("project").get(pk=pk)
        except Variation.DoesNotExist:
            return Response({"error": "Variation not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check project access
        if not check_project_access(user, variation.project_id):
            return Response(
                {"error": "You do not have access to this project's variations."},
                status=status.HTTP_403_FORBIDDEN,
            )

        client_name = request.data.get("client_name")
        client_email = request.data.get("client_email")

        if client_name:
            variation.client_name = str(client_name).strip()
        if client_email:
            variation.client_email = str(client_email).strip()

        variation.submitted_to_client = True
        variation.save()

        # Send notification email if client_email is provided
        if variation.client_email:
            from django.core.mail import send_mail
            from app.account.views import get_default_from_email
            subject = f"Variation Order {variation.vo_number} Issued - {variation.project.project_name}"
            message = (
                f"Dear {variation.client_name or 'Client'},\n\n"
                f"Variation Order {variation.vo_number} for project {variation.project.project_name} has been issued for your signature.\n\n"
                f"Description of Works:\n{variation.description_of_works}\n\n"
                f"Total Amount: £{variation.total_amount}\n\n"
                f"Thank you."
            )
            try:
                send_mail(
                    subject,
                    message,
                    get_default_from_email(),
                    [variation.client_email],
                    fail_silently=True,
                )
            except Exception:
                pass

        return Response(VariationSerializer(variation).data)


class VariationRemindClientView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=dict, responses={200: dict})
    def post(self, request, pk):
        """Send email reminder to client to sign variation. Only commercial department allowed."""
        user = request.user
        if user.role != "commercial_department" and user.role not in ["admin", "project_admin"]:
            return Response(
                {"error": "Only the commercial department can send reminders to the client."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            variation = Variation.objects.select_related("project").get(pk=pk)
        except Variation.DoesNotExist:
            return Response({"error": "Variation not found."}, status=status.HTTP_404_NOT_FOUND)

        if not check_project_access(user, variation.project_id):
            return Response(
                {"error": "You do not have access to this project's variations."},
                status=status.HTTP_403_FORBIDDEN,
            )

        client_email = request.data.get("client_email") or variation.client_email
        if not client_email or not str(client_email).strip():
            return Response(
                {"error": "No client email has been provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client_name = request.data.get("client_name") or variation.client_name

        variation.client_email = str(client_email).strip()
        if client_name:
            variation.client_name = str(client_name).strip()
        variation.save()

        # Send reminder email
        from django.core.mail import send_mail
        from app.account.views import get_default_from_email

        subject = f"Reminder: Variation {variation.vo_number} Signature Required"
        message = (
            f"Dear {variation.client_name or 'Client'},\n\n"
            f"This is a reminder regarding Variation Order {variation.vo_number} for project {variation.project.project_name}.\n\n"
            f"Description of Works:\n{variation.description_of_works}\n\n"
            f"Total Amount: £{variation.total_amount}\n\n"
            f"Please review and sign this variation order at your earliest convenience.\n\n"
            f"Thank you."
        )

        try:
            send_mail(
                subject,
                message,
                get_default_from_email(),
                [variation.client_email],
                fail_silently=False,
            )
        except Exception as e:
            pass

        return Response(VariationSerializer(variation).data)


class VariationAssignUsersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=dict, responses={200: dict})
    def post(self, request, pk):
        """Assign users to a variation (app users / employees only)."""
        try:
            variation = Variation.objects.get(pk=pk)
        except Variation.DoesNotExist:
            return Response({"error": "Variation not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check project access
        if not check_project_access(request.user, variation.project_id):
            return Response(
                {"error": "You do not have access to this project's variations."},
                status=status.HTTP_403_FORBIDDEN,
            )

        assigned_user_ids = request.data.get("assigned_user_ids", [])
        if not isinstance(assigned_user_ids, list):
            return Response({"error": "assigned_user_ids must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        # Assigning app users requires the variation to be approved by the Commercial Manager
        if variation.approval_status != Variation.ApprovalStatus.APPROVED and not variation.commercial_department_approved:
            return Response(
                {"error": "App users can only be assigned once the variation has been approved by the Commercial Manager."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only app users (role == 'employee') from the user's company who have been approved by the document controller can be assigned
        from app.account.models import UserAccount
        valid_users = UserAccount.objects.filter(
            id__in=assigned_user_ids,
            role=UserAccount.Role.EMPLOYEE,
            company=request.user.company,
            profile__is_approved=True,
        )

        variation.assigned_users.set(valid_users)
        variation.save()
        return Response(VariationSerializer(variation).data)

from .models import MonthlyApplication
from .serializers import MonthlyApplicationSerializer
from app.project_admin.models import ProjectFolder, ProjectSubfolder
import datetime

class MonthlyApplicationListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: dict})
    def get(self, request):
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"error": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not check_project_access(request.user, project_id):
            return Response({"error": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        
        apps = MonthlyApplication.objects.filter(project_id=project_id)
        serializer = MonthlyApplicationSerializer(apps, many=True)

        # Calculate current draft based on actual booked app user labour targets and approved variations
        from app.project_admin.models import UserInvoice, ProjectSubfolder, Project, FolderAssignment
        
        assignments = FolderAssignment.objects.filter(
            subfolder__folder__project_id=project_id
        ).select_related('subfolder')
        assignment_map = {str(a.id): a.subfolder for a in assignments}
        
        invoices = UserInvoice.objects.filter(
            project_id=project_id,
            source_type=UserInvoice.SourceType.LABOUR_TARGET,
            status=UserInvoice.Status.SUBMITTED
        )
        
        contract_works_total = 0.0
        for inv in invoices:
            sid = inv.source_id or ""
            parts = sid.split(":")
            aid = parts[0]
            subfolder = assignment_map.get(aid)
            if not subfolder:
                continue
            rows = subfolder.rows or []
            if len(parts) == 2:
                try:
                    row_idx = int(parts[1])
                    if 0 <= row_idx < len(rows):
                        row = rows[row_idx]
                        row_pv = float(row.get('projectValue', 0) or 0)
                        row_lt = float(row.get('labourTarget', 0) or 0)
                        booked_val = float(inv.total or 0)
                        if row_lt > 0:
                            contract_works_total += (booked_val / row_lt) * row_pv
                        else:
                            contract_works_total += booked_val
                except (ValueError, TypeError):
                    pass
            else:
                sub_pv = float(subfolder.project_value or 0)
                sub_lt = float(subfolder.labour_target or 0) if hasattr(subfolder, 'labour_target') else 0
                booked_val = float(inv.total or 0)
                if sub_lt > 0:
                    contract_works_total += (booked_val / sub_lt) * sub_pv
                else:
                    contract_works_total += booked_val

        approved_variations = Variation.objects.filter(
            project_id=project_id, 
            approval_status=Variation.ApprovalStatus.APPROVED,
            submitted_to_client=True
        )
        variations_total = sum(float(v.amount_claimed) if v.amount_claimed else float(v.total_amount) for v in approved_variations)

        original_project_value = sum(float(sub.project_value) for sub in ProjectSubfolder.objects.filter(folder__project_id=project_id))

        project_obj = Project.objects.filter(id=project_id).first()
        current_draft = {
            "contract_works_total": contract_works_total,
            "variations_total": variations_total,
            "gross_total": contract_works_total + variations_total,
            "original_project_value": original_project_value,
            "order_no": project_obj.job_code if project_obj else "",
            "order_value": float(project_obj.project_value) if project_obj else 0.0,
        }
        
        return Response({
            "monthly_applications": serializer.data,
            "current_draft": current_draft
        })

    @extend_schema(request=dict, responses={200: dict})
    def post(self, request):
        project_id = request.data.get("project_id")
        if not project_id:
            return Response({"error": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not check_project_access(request.user, project_id):
            return Response({"error": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        # Basic financial snapshot calculations
        from app.project_admin.models import UserInvoice, ProjectSubfolder, FolderAssignment
        import datetime
        
        assignments = FolderAssignment.objects.filter(
            subfolder__folder__project_id=project_id
        ).select_related('subfolder')
        assignment_map = {str(a.id): a.subfolder for a in assignments}
        
        invoices = UserInvoice.objects.filter(
            project_id=project_id,
            source_type=UserInvoice.SourceType.LABOUR_TARGET,
            status=UserInvoice.Status.SUBMITTED
        )
        contract_works_total = 0.0
        for inv in invoices:
            sid = inv.source_id or ""
            parts = sid.split(":")
            aid = parts[0]
            subfolder = assignment_map.get(aid)
            if not subfolder:
                continue
            rows = subfolder.rows or []
            if len(parts) == 2:
                try:
                    row_idx = int(parts[1])
                    if 0 <= row_idx < len(rows):
                        row = rows[row_idx]
                        row_pv = float(row.get('projectValue', 0) or 0)
                        row_lt = float(row.get('labourTarget', 0) or 0)
                        booked_val = float(inv.total or 0)
                        if row_lt > 0:
                            contract_works_total += (booked_val / row_lt) * row_pv
                        else:
                            contract_works_total += booked_val
                except (ValueError, TypeError):
                    pass
            else:
                sub_pv = float(subfolder.project_value or 0)
                sub_lt = float(subfolder.labour_target or 0) if hasattr(subfolder, 'labour_target') else 0
                booked_val = float(inv.total or 0)
                if sub_lt > 0:
                    contract_works_total += (booked_val / sub_lt) * sub_pv
                else:
                    contract_works_total += booked_val
        
        approved_variations = Variation.objects.filter(
            project_id=project_id, 
            approval_status=Variation.ApprovalStatus.APPROVED,
            submitted_to_client=True
        )
        variations_total = sum(float(v.amount_claimed) if v.amount_claimed else float(v.total_amount) for v in approved_variations)
        
        count = MonthlyApplication.objects.filter(project_id=project_id).count()
        app_number = count + 1

        app = MonthlyApplication.objects.create(
            project_id=project_id,
            application_number=app_number,
            date=datetime.date.today(),
            contract_works_total=contract_works_total,
            variations_total=variations_total,
            retention_percentage=request.data.get("retention_percentage", 2.5),
            discount_percentage=request.data.get("discount_percentage", 0.0),
        )
        serializer = MonthlyApplicationSerializer(app)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WhiteCardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: dict})
    def get(self, request):
        params = getattr(request, 'query_params', getattr(request, 'GET', {}))
        project_id = params.get("project_id")
        if not project_id:
            return Response({"error": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not check_project_access(request.user, project_id):
            return Response({"error": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        folders = ProjectFolder.objects.filter(project_id=project_id).prefetch_related("subfolders")
        
        from app.project_admin.models import FolderAssignment, UserInvoice
        assignments = FolderAssignment.objects.filter(
            subfolder__folder__project_id=project_id
        ).values('id', 'subfolder_id')
        
        subfolder_to_aids = {}
        for a in assignments:
            subfolder_to_aids.setdefault(str(a['subfolder_id']), []).append(str(a['id']))
            
        invoices = UserInvoice.objects.filter(
            project_id=project_id,
            source_type=UserInvoice.SourceType.LABOUR_TARGET,
            status=UserInvoice.Status.SUBMITTED
        ).values('source_id', 'total')
        
        booked_by_source = {}
        for inv in invoices:
            sid = inv['source_id']
            booked_by_source[sid] = booked_by_source.get(sid, 0.0) + float(inv['total'] or 0.0)

        groups = []
        for folder in folders:
            subfolders_data = []
            for sub in folder.subfolders.all():
                sub_id_str = str(sub.id)
                aids = subfolder_to_aids.get(sub_id_str, [])
                rows = sub.rows if isinstance(sub.rows, list) else []
                
                enhanced_rows = []
                for i, r in enumerate(rows):
                    r_copy = dict(r) if isinstance(r, dict) else {}
                    row_booked = 0.0
                    for aid in aids:
                        row_booked += booked_by_source.get(f"{aid}:{i}", 0.0)
                    r_copy['bookedLabour'] = row_booked
                    enhanced_rows.append(r_copy)
                
                sub_booked = 0.0
                for aid in aids:
                    sub_booked += booked_by_source.get(aid, 0.0)
                    
                subfolders_data.append({
                    "id": sub_id_str,
                    "name": sub.name,
                    "project_value": float(sub.project_value),
                    "labour_target": float(sub.labour_target) if hasattr(sub, 'labour_target') else 0.0,
                    "booked_labour": sub_booked,
                    "rows": enhanced_rows
                })
                
            groups.append({
                "groupId": str(folder.id),
                "headerName": folder.name,
                "subfolders": subfolders_data
            })

        return Response({"groups": groups})

class MonthlyApplicationUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=dict, responses={200: dict})
    def patch(self, request, pk):
        try:
            app = MonthlyApplication.objects.get(pk=pk)
        except MonthlyApplication.DoesNotExist:
            return Response({"error": "Monthly Application not found."}, status=status.HTTP_404_NOT_FOUND)
            
        if not check_project_access(request.user, app.project_id):
            return Response({"error": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
            
        certified_amount = request.data.get("certified_amount")
        if certified_amount is not None:
            try:
                app.client_certified_amount = float(certified_amount)
            except (ValueError, TypeError):
                pass
                
        payment_certificate = request.FILES.get("payment_certificate")
        if payment_certificate:
            try:
                upload_result = cloudinary.uploader.upload(
                    payment_certificate,
                    resource_type='auto',
                    folder=f"josue_applications/{app.project_id}"
                )
                app.payment_certificate_url = upload_result.get('secure_url')
            except Exception as e:
                return Response({"error": f"Failed to upload invoice: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
                
        app.save()
        serializer = MonthlyApplicationSerializer(app)
        return Response(serializer.data, status=status.HTTP_200_OK)
