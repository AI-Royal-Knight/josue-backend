from rest_framework.views import APIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from app.account.models import CompanySupplier, SupplierProfile, UserAccount, Invitation, RoleAssignment
from app.project_admin.models import Project
from app.procurement_department.models import Quotation
from .serializers import (
    CompanySupplierSerializer, InviteSupplierSerializer,
    QuotationSerializer, ProjectNestedSerializer
)

class SupplierListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Admins can access everything in their company
        if request.user.role == UserAccount.Role.ADMIN:
            company = request.user.admin_profile.company
            suppliers = CompanySupplier.objects.filter(company=company)
            serializer = CompanySupplierSerializer(suppliers, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # For Procurement dept, get company from role assignment
        role_assignment = RoleAssignment.objects.filter(user=request.user, role=UserAccount.Role.PROCUREMENT_DEPARTMENT).first()
        if role_assignment and role_assignment.company:
            suppliers = CompanySupplier.objects.filter(company=role_assignment.company)
            serializer = CompanySupplierSerializer(suppliers, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # For all other users, get suppliers linked to their assigned projects' companies
        company_ids = request.user.assigned_projects.values_list('company_id', flat=True)
        if not company_ids:
            return Response({"detail": "No project access given."}, status=status.HTTP_403_FORBIDDEN)
            
        suppliers = CompanySupplier.objects.filter(company_id__in=company_ids).distinct()
        serializer = CompanySupplierSerializer(suppliers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SupplierInviteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role_assignment = RoleAssignment.objects.filter(user=request.user, role=UserAccount.Role.PROCUREMENT_DEPARTMENT).first()
        if not role_assignment or not role_assignment.company:
            return Response({"detail": "User is not associated with a company as a procurement admin."}, status=status.HTTP_403_FORBIDDEN)
            
        company = role_assignment.company
        
        serializer = InviteSupplierSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            company_name = serializer.validated_data['company_name']
            
            # Check if user exists
            user, created = UserAccount.objects.get_or_create(
                email=email,
                defaults={'role': UserAccount.Role.SUPPLIER, 'is_active': True}
            )
            
            # Ensure they have the supplier role
            if user.role != UserAccount.Role.SUPPLIER:
                # If they were another role, we don't necessarily override it, but for this context they are a supplier.
                # Usually a supplier might have multiple roles, but the system assumes 'supplier' is the primary role for these users.
                pass

            # Create or get supplier profile
            supplier_profile, _ = SupplierProfile.objects.get_or_create(
                user=user,
                defaults={'company_name': company_name}
            )
            
            # Link supplier to company
            company_supplier, created_cs = CompanySupplier.objects.get_or_create(
                company=company,
                supplier=supplier_profile,
                defaults={'eom_payment_terms': 30, 'credit_limit': 0.00}
            )
            
            # Create Invitation
            invitation, _ = Invitation.objects.get_or_create(
                email=email,
                role=UserAccount.Role.SUPPLIER,
                company=company,
                defaults={
                    'status': Invitation.Status.PENDING,
                    'expires_at': timezone.now() + timezone.timedelta(days=7)
                }
            )

            # Send email
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            invitation_link = f"{frontend_url}/sign-up?email={email}&role=supplier"
            
            subject = f"You have been invited by {company.company_name} as a Supplier"
            message = (
                f"Hello,\n\n"
                f"You have been invited as a Supplier for {company.company_name}.\n"
                f"Please use the following link to accept your invitation and set up your account:\n"
                f"{invitation_link}\n\n"
                f"This link will expire in 7 days.\n\n"
                f"Thank you."
            )
            send_mail(
                subject,
                message,
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@payparo.tech'),
                [email],
                fail_silently=False,
            )

            return Response({
                "detail": "Supplier invited successfully.",
                "supplier": CompanySupplierSerializer(company_supplier).data
            }, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProcurementProjectListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == UserAccount.Role.ADMIN:
            projects = Project.objects.filter(company=request.user.admin_profile.company)
            serializer = ProjectNestedSerializer(projects, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Fetch projects the user is explicitly assigned to
        projects = request.user.assigned_projects.all()
        if not projects.exists():
            return Response({"detail": "No project access given."}, status=status.HTTP_403_FORBIDDEN)
            
        serializer = ProjectNestedSerializer(projects, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class QuotationViewSet(viewsets.ModelViewSet):
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        if self.request.user.role == UserAccount.Role.ADMIN:
            return Quotation.objects.filter(project__company=self.request.user.admin_profile.company)

        # Allow Procurement dept to see all company quotations
        role_assignment = RoleAssignment.objects.filter(
            user=self.request.user, 
            role=UserAccount.Role.PROCUREMENT_DEPARTMENT
        ).first()
        
        queryset = Quotation.objects.none()
        if role_assignment and role_assignment.company:
            queryset = Quotation.objects.filter(project__company=role_assignment.company)
            
        # Always include quotations for projects this user is explicitly assigned to
        assigned_qs = Quotation.objects.filter(project__in=self.request.user.assigned_projects.all())
        
        return (queryset | assigned_qs).distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        
        # Auto-create or resolve supplier if we receive raw names instead of ID
        if 'supplier' not in data and 'supplier_name' in data:
            supplier_name = data.get('supplier_name')
            supplier_email = data.get('supplier_email') or f"temp_supplier_{supplier_name.replace(' ', '_').lower()}@example.com"
            
            # Find user's company
            company = None
            if request.user.role == UserAccount.Role.ADMIN:
                company = request.user.admin_profile.company
            else:
                from app.account.models import RoleAssignment
                role_assignment = RoleAssignment.objects.filter(user=request.user, role=UserAccount.Role.PROCUREMENT_DEPARTMENT).first()
                if role_assignment:
                    company = role_assignment.company
                    
            if company:
                user, _ = UserAccount.objects.get_or_create(
                    email=supplier_email,
                    defaults={'role': UserAccount.Role.SUPPLIER, 'is_active': True}
                )
                from app.account.models import SupplierProfile, CompanySupplier
                supplier_profile, _ = SupplierProfile.objects.get_or_create(
                    user=user,
                    defaults={'company_name': supplier_name}
                )
                company_supplier, _ = CompanySupplier.objects.get_or_create(
                    company=company,
                    supplier=supplier_profile,
                    defaults={'eom_payment_terms': 30, 'credit_limit': 0.00}
                )
                data['supplier'] = company_supplier.id
                
        # We need to temporarily set the modified data for the serializer
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class ParsePOPDFView(APIView):
    """POST /procurement/po/parse-pdf/  → parse a supplier PDF and return structured data."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        if not uploaded.name.lower().endswith(".pdf"):
            return Response({"error": "Only PDF files are supported."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from .pdf_utils import parse_po_pdf
            parsed = parse_po_pdf(uploaded)
            return Response(parsed, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GenerateBrandedPOPDFView(APIView):
    """POST /procurement/po/generate-pdf/  → create a branded PDF and return it as a download."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import json
        from django.http import HttpResponse

        try:
            parsed_data = request.data  # DRF parses JSON body
            if not isinstance(parsed_data, dict):
                return Response({"error": "Expected JSON body."}, status=status.HTTP_400_BAD_REQUEST)

            logo_path = None
            # Try to locate a logo relative to the Django project
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            candidate = os.path.join(base_dir, "app", "static", "logo.png")
            if os.path.exists(candidate):
                logo_path = candidate

            from .pdf_utils import generate_branded_po_pdf
            pdf_bytes = generate_branded_po_pdf(parsed_data, logo_path=logo_path)

            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            ref = parsed_data.get("quotation_number", "PO")
            response["Content-Disposition"] = f'attachment; filename="PO_{ref}.pdf"'
            return response
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
