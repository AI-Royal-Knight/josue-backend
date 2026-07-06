from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.db import transaction

from .models import Variation, VariationLine
from .serializers import VariationSerializer


class VariationListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Return all variations the user has access to (filtered by their company's projects)."""
        if not request.user.company:
            return Response({"variations": []})

        variations = Variation.objects.filter(
            project__company=request.user.company
        ).select_related("project", "created_by", "approved_by").prefetch_related("lines")

        # Optional project filter
        project_id = request.query_params.get("project_id")
        if project_id:
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
        lines_data = request.data.get("lines", [])

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

        with transaction.atomic():
            variation = Variation.objects.create(
                project_id=project_id,
                created_by=request.user,
                site_instruction_no=site_instruction_no,
                attention_of=attention_of,
                description_of_works=description,
                comments=comments,
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

        variation.submitted_to_client = True
        variation.save()
        return Response(VariationSerializer(variation).data)
