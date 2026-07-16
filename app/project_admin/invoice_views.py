"""
User Invoice API views.
- GET  /api/v1/invoices/user-invoices/          – list all invoices for the company (management) or only finance-approved ones
- GET  /api/v1/invoices/user-invoices/?project_id=<id>  – filter by project
- GET  /api/v1/invoices/user-invoices/?finance_view=true  – fully-approved invoices only (for /invoice-list)
- POST /api/v1/invoices/user-invoices/<id>/approve/  – management roles toggle their approval signature
- POST /api/v1/invoices/user-invoices/<id>/pay/      – finance marks as paid/unpaid
"""
import datetime

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from app.project_admin.models import UserInvoice


# ── Role → approval field mapping ─────────────────────────────────────────────

ROLE_TO_APPROVAL_FIELD = {
    "supervisor": "supervisor_approved",
    "manager": "manager_approved",
    "contracts_manager": "contracts_manager_approved",
    "project_director": "project_director_approved",
    "managing_director": "managing_director_approved",
}

ROLE_TO_DATE_FIELD = {
    "supervisor": "supervisor_approved_date",
    "manager": "manager_approved_date",
    "contracts_manager": "contracts_manager_approved_date",
    "project_director": "project_director_approved_date",
    "managing_director": "managing_director_approved_date",
}

ROLE_TO_BY_FIELD = {
    "supervisor": "supervisor_approved_by",
    "manager": "manager_approved_by",
    "contracts_manager": "contracts_manager_approved_by",
    "project_director": "project_director_approved_by",
    "managing_director": "managing_director_approved_by",
}


def _serialize_invoice(inv: UserInvoice) -> dict:
    user = inv.created_by
    return {
        "id": str(inv.id),
        "invoiceNumber": inv.invoice_number,
        "date": inv.date.strftime("%d/%m/%Y") if inv.date else "",
        "variationSheetNo": inv.variation_sheet_no,
        "nfiProformaNo": inv.proforma_no,
        "project": inv.project.project_name if inv.project else "",
        "workArea": inv.work_area,
        "workSection": inv.work_section,
        "description": inv.description,
        "sourceType": inv.source_type,
        "createdBy": user.full_name if user and user.full_name else (user.email if user else ""),
        "userName": user.full_name if user and user.full_name else (user.email if user else ""),
        "sortCode": getattr(user, "sort_code", "") or "" if user else "",
        "accountNumber": getattr(user, "account_number", "") or "" if user else "",
        "total": f"£{inv.total:,.2f}",
        "totalRaw": float(inv.total),
        # Approval chain
        "supervisorApproved": inv.supervisor_approved,
        "supervisorApprovedDate": inv.supervisor_approved_date.strftime("%d/%m/%Y") if inv.supervisor_approved_date else "",
        "managerApproved": inv.manager_approved,
        "managerApprovedDate": inv.manager_approved_date.strftime("%d/%m/%Y") if inv.manager_approved_date else "",
        "contractsManagerApproved": inv.contracts_manager_approved,
        "contractsManagerApprovedDate": inv.contracts_manager_approved_date.strftime("%d/%m/%Y") if inv.contracts_manager_approved_date else "",
        "projectDirectorApproved": inv.project_director_approved,
        "projectDirectorApprovedDate": inv.project_director_approved_date.strftime("%d/%m/%Y") if inv.project_director_approved_date else "",
        "managingDirectorApproved": inv.managing_director_approved,
        "managingDirectorApprovedDate": inv.managing_director_approved_date.strftime("%d/%m/%Y") if inv.managing_director_approved_date else "",
        "fullyApproved": inv.fully_approved,
        # Finance
        "paid": inv.finance_paid,
        "approved": inv.fully_approved,  # alias used by /users-invoices UI
        "approvedBy": inv.managing_director_approved_by.full_name if inv.managing_director_approved_by else "",
        "datePaid": inv.finance_paid_date.strftime("%d/%m/%Y") if inv.finance_paid_date else "",
        "paidBy": inv.finance_paid_by.full_name if inv.finance_paid_by else "",
        "financeComments": inv.finance_comments,
        "commercialComments": inv.commercial_comments,
        # For /invoice-list
        "dateScheduled": "",
        "releaseDate": inv.finance_paid_date.strftime("%d/%m/%Y") if inv.finance_paid_date else "",
        "comments": inv.finance_comments,
        "scheduledBy": "",
        "no": str(inv.id),  # used as row key in the tables
    }


class UserInvoiceListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        company = user.company
        if not company:
            from app.account.models import RoleAssignment
            role_assignment = RoleAssignment.objects.filter(user=user, role=user.role).first()
            if role_assignment:
                company = role_assignment.company

        from django.db.models import Q
        if company:
            qs = UserInvoice.objects.filter(status=UserInvoice.Status.SUBMITTED).filter(Q(project__company__company_name__iexact=company.company_name) | Q(project__in=user.assigned_projects.all()))
        else:
            qs = UserInvoice.objects.filter(status=UserInvoice.Status.SUBMITTED, project__in=user.assigned_projects.all())

        qs = qs.select_related("project", "created_by", "managing_director_approved_by", "finance_paid_by")


        # Optional project filter
        project_id = request.query_params.get("project_id")
        if project_id and project_id != "all":
            qs = qs.filter(project_id=project_id)

        # We removed the finance_view filter here so Finance can see ALL invoices (approved or pending)

        invoices = [_serialize_invoice(inv) for inv in qs]

        # Summary stats
        total_count = len(invoices)
        paid_count = sum(1 for inv in invoices if inv["paid"])
        unpaid_count = total_count - paid_count
        money_on_hold = sum(inv["totalRaw"] for inv in invoices if not inv["paid"])

        return Response({
            "invoices": invoices,
            "summary": {
                "total": total_count,
                "paid": paid_count,
                "unpaid": unpaid_count,
                "money_on_hold": f"£{money_on_hold:,.2f}",
            }
        })


class UserInvoiceApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invoice_id):
        user = request.user
        role = user.role
        
        # UI sends "managers" sometimes, we map it back to "manager" in backend for role logic.
        if role == "managers":
            role = "manager"

        if role not in ROLE_TO_APPROVAL_FIELD:
            return Response(
                {"error": "Your role is not permitted to approve invoices."},
                status=status.HTTP_403_FORBIDDEN,
            )

        company = user.company
        if not company:
            from app.account.models import RoleAssignment
            role_assignment = RoleAssignment.objects.filter(user=user, role=role).first()
            if role_assignment:
                company = role_assignment.company

        try:
            from django.db.models import Q
            if company:
                invoice = UserInvoice.objects.get(Q(id=invoice_id) & (Q(project__company__company_name__iexact=company.company_name) | Q(project__in=user.assigned_projects.all())))
            else:
                invoice = UserInvoice.objects.get(id=invoice_id, project__in=user.assigned_projects.all())
        except UserInvoice.DoesNotExist:
            return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)

        approve = request.data.get("approve", True)
        field = ROLE_TO_APPROVAL_FIELD[role]
        date_field = ROLE_TO_DATE_FIELD[role]
        by_field = ROLE_TO_BY_FIELD[role]

        setattr(invoice, field, approve)
        setattr(invoice, date_field, datetime.date.today() if approve else None)
        setattr(invoice, by_field, user if approve else None)
        invoice.save()

        return Response({"invoice": _serialize_invoice(invoice)})


class UserInvoicePayView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invoice_id):
        if request.user.role != "finance_department":
            return Response(
                {"error": "Only Finance Department can mark invoices as paid."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = request.user
        company = user.company
        if not company:
            from app.account.models import RoleAssignment
            role_assignment = RoleAssignment.objects.filter(user=user, role=user.role).first()
            if role_assignment:
                company = role_assignment.company

        try:
            from django.db.models import Q
            if company:
                invoice = UserInvoice.objects.get(Q(id=invoice_id) & (Q(project__company__company_name__iexact=company.company_name) | Q(project__in=user.assigned_projects.all())))
            else:
                invoice = UserInvoice.objects.get(id=invoice_id, project__in=user.assigned_projects.all())
        except UserInvoice.DoesNotExist:
            return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)

        paid = request.data.get("paid", True)

        if paid and not invoice.fully_approved:
            return Response(
                {"error": "Invoice must be fully approved before it can be marked as paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comments = request.data.get("finance_comments", invoice.finance_comments)

        invoice.finance_paid = paid
        invoice.finance_paid_date = datetime.date.today() if paid else None
        invoice.finance_paid_by = request.user if paid else None
        if comments is not None:
            invoice.finance_comments = comments
        invoice.save()

        return Response({"invoice": _serialize_invoice(invoice)})


class UserInvoiceCommercialCommentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invoice_id):
        if request.user.role != "commercial_department":
            return Response(
                {"error": "Only Commercial Department can update commercial comments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = request.user
        company = user.company
        if not company:
            from app.account.models import RoleAssignment
            role_assignment = RoleAssignment.objects.filter(user=user, role=user.role).first()
            if role_assignment:
                company = role_assignment.company

        try:
            from django.db.models import Q
            if company:
                invoice = UserInvoice.objects.get(Q(id=invoice_id) & (Q(project__company__company_name__iexact=company.company_name) | Q(project__in=user.assigned_projects.all())))
            else:
                invoice = UserInvoice.objects.get(id=invoice_id, project__in=user.assigned_projects.all())
        except UserInvoice.DoesNotExist:
            return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)

        comments = request.data.get("commercial_comments")
        if comments is not None:
            invoice.commercial_comments = comments
            invoice.save()

        return Response({"invoice": _serialize_invoice(invoice)})


class BucketListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = UserInvoice.objects.filter(status=UserInvoice.Status.BUCKET, created_by=user)
        qs = qs.select_related("project", "created_by")
        
        project_id = request.query_params.get("project_id")
        if project_id and project_id != "all":
            qs = qs.filter(project_id=project_id)
            
        invoices = [_serialize_invoice(inv) for inv in qs]
        return Response({
            "invoices": invoices,
            "total_count": len(invoices)
        })

class BucketSubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        invoice_ids = request.data.get("invoice_ids", [])
        
        if not isinstance(invoice_ids, list):
            return Response({"error": "invoice_ids must be a list"}, status=status.HTTP_400_BAD_REQUEST)
            
        invoices = UserInvoice.objects.filter(
            id__in=invoice_ids, 
            status=UserInvoice.Status.BUCKET,
            created_by=user
        )
        
        submitted_count = 0
        for inv in invoices:
            inv.status = UserInvoice.Status.SUBMITTED
            inv.save()
            submitted_count += 1
            
        return Response({"message": f"Successfully submitted {submitted_count} items."})
