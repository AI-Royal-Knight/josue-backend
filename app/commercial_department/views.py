from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
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
    return user.assigned_projects.filter(id=project_id).exists()


class VariationListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

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
                project__in=user.assigned_projects.all()
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
                evidence_url = upload_result.get('secure_url')
            except Exception as e:
                return Response({"error": f"Failed to upload evidence: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

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


class VariationSubmitToClientView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        """Mark variation as submitted to client."""
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

        variation.submitted_to_client = True
        variation.save()
        return Response(VariationSerializer(variation).data)


class VariationAssignUsersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        """Assign users to a variation."""
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

        # Update assigned users
        variation.assigned_users.set(assigned_user_ids)
        variation.save()
        return Response(VariationSerializer(variation).data)

from .models import MonthlyApplication
from .serializers import MonthlyApplicationSerializer
from app.project_admin.models import ProjectFolder, ProjectSubfolder
import datetime

class MonthlyApplicationListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"error": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not check_project_access(request.user, project_id):
            return Response({"error": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        
        apps = MonthlyApplication.objects.filter(project_id=project_id)
        serializer = MonthlyApplicationSerializer(apps, many=True)
        return Response({"monthly_applications": serializer.data})

    def post(self, request):
        project_id = request.data.get("project_id")
        if not project_id:
            return Response({"error": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not check_project_access(request.user, project_id):
            return Response({"error": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        # Basic financial snapshot calculations
        contract_works_total = sum(float(sub.project_value) for sub in ProjectSubfolder.objects.filter(folder__project_id=project_id))
        
        variations = Variation.objects.filter(project_id=project_id, approval_status="approved")
        variations_total = sum(float(v.amount_claimed) for v in variations)
        
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

    def get(self, request):
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"error": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not check_project_access(request.user, project_id):
            return Response({"error": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        folders = ProjectFolder.objects.filter(project_id=project_id).prefetch_related("subfolders")
        
        groups = []
        for folder in folders:
            groups.append({
                "groupId": folder.name.lower().replace(" ", "_"),
                "headerName": folder.name,
                "subfolders": [
                    {
                        "name": sub.name,
                        "project_value": float(sub.project_value)
                    } for sub in folder.subfolders.all()
                ]
            })

        return Response({"groups": groups})
