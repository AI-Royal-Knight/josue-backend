from rest_framework.views import APIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
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
        # Determine the company for the current user
        company = None
        
        if request.user.role == UserAccount.Role.ADMIN:
            company = request.user.company
        elif request.user.role == UserAccount.Role.SUPER_ADMIN:
            # Super admin can see all
            suppliers = CompanySupplier.objects.all()
            serializer = CompanySupplierSerializer(suppliers, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            # For Procurement dept, get company from role assignment
            role_assignment = RoleAssignment.objects.filter(user=request.user, role=UserAccount.Role.PROCUREMENT_DEPARTMENT).first()
            if role_assignment and role_assignment.company:
                company = role_assignment.company
            elif request.user.company:
                company = request.user.company
        
        if not company:
            # Fall back to suppliers linked to user's assigned projects' companies
            company_ids = request.user.assigned_projects.values_list('company_id', flat=True)
            if not company_ids:
                return Response({"detail": "No project access given."}, status=status.HTTP_403_FORBIDDEN)
            suppliers = CompanySupplier.objects.filter(company_id__in=company_ids).distinct()
            serializer = CompanySupplierSerializer(suppliers, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        # Get suppliers directly linked to this company
        direct_suppliers = CompanySupplier.objects.filter(company=company)
        
        # Also get supplier IDs linked via quotations for this company's projects
        from app.procurement_department.models import Quotation
        quoted_supplier_ids = Quotation.objects.filter(
            project__company=company,
            supplier__isnull=False
        ).values_list('supplier_id', flat=True).distinct()
        
        # Merge both sets
        from django.db.models import Q
        suppliers = CompanySupplier.objects.filter(
            Q(company=company) | Q(id__in=quoted_supplier_ids)
        ).distinct()
        
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
            projects = Project.objects.filter(company=request.user.company)
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
            return Quotation.objects.filter(project__company=self.request.user.company)

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

    @action(detail=True, methods=['patch'])
    def approve(self, request, pk=None):
        quotation = self.get_object()
        if quotation.status == Quotation.Status.APPROVED:
            return Response({"detail": "Quotation is already approved."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Recalculate quote_total from line items (supplier_price takes precedence over each)
        import decimal
        total = decimal.Decimal('0.0')
        for item in quotation.line_items.all():
            price = item.supplier_price if item.supplier_price is not None else item.each
            discount = item.discount or decimal.Decimal('0.0')
            qty = item.qty or decimal.Decimal('1.0')
            # using float for percentage math to avoid complex decimal conversion, then convert back
            line_total = float(qty) * float(price) * (1.0 - (float(discount) / 100.0))
            total += decimal.Decimal(str(round(line_total, 2)))
            
        quotation.quote_total = total
        quotation.status = Quotation.Status.APPROVED
        quotation.save(update_fields=['status', 'quote_total'])
        
        # We can also handle specific logic if we want to create POCallOff records here, 
        # but for now we just approve it so its line items appear in Call Off list.
        
        serializer = self.get_serializer(quotation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        quotation = serializer.save(created_by=self.request.user)
        
        # Generate PDF and send email
        try:
            from .pdf_utils import generate_quotation_pdf
            from django.core.mail import EmailMessage
            from django.conf import settings
            import os
            
            logo_path = None
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            candidate = os.path.join(base_dir, "app", "static", "logo.png")
            if os.path.exists(candidate):
                logo_path = candidate
                
            pdf_bytes = generate_quotation_pdf(quotation, logo_path=logo_path)
            
            # Use serializer data to get fallback email if needed
            email_to = quotation.supplier_email
            if not email_to and quotation.supplier and quotation.supplier.supplier:
                email_to = quotation.supplier.supplier.user.email
                
            if email_to:
                frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
                supplier_link = f"{frontend_url}/supplier-quote/{quotation.supplier_token}"
                
                subject = f"Request for Quotation: {quotation.quote_ref}"
                message = (
                    f"Hello,\n\n"
                    f"Please find attached our Request for Quotation ({quotation.quote_ref}).\n"
                    f"You can submit your pricing and upload your own quote PDF by clicking the link below:\n\n"
                    f"{supplier_link}\n\n"
                    f"Thank you."
                )
                
                email = EmailMessage(
                    subject,
                    message,
                    getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@payparo.tech'),
                    [email_to]
                )
                email.attach(f"Quotation_{quotation.quote_ref}.pdf", pdf_bytes, "application/pdf")
                email.send(fail_silently=True)
                
        except Exception as e:
            print(f"Error sending quotation email: {e}")

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        
        # Auto-create or resolve supplier if we receive raw names instead of ID
        if 'supplier' not in data and 'supplier_name' in data:
            supplier_name = data.get('supplier_name')
            supplier_email = data.get('supplier_email') or f"temp_supplier_{supplier_name.replace(' ', '_').lower()}@example.com"
            
            # Find user's company
            company = None
            if request.user.role == UserAccount.Role.ADMIN:
                company = request.user.company
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

    @action(detail=True, methods=['post'])
    def request_requote(self, request, pk=None):
        quotation = self.get_object()
        comments = request.data.get('comments', '')

        # Create history snapshot
        from app.procurement_department.models import QuotationHistory
        snapshot_line_items = [
            {
                "description": item.description,
                "qty": str(item.qty),
                "per": item.per,
                "supplier_price": str(item.supplier_price) if item.supplier_price else None
            }
            for item in quotation.line_items.all()
        ]
        
        QuotationHistory.objects.create(
            quotation=quotation,
            message=comments,
            previous_total=quotation.quote_total,
            previous_pdf=quotation.supplier_quote_pdf if quotation.supplier_quote_pdf else None,
            previous_line_items=snapshot_line_items
        )

        # Reset quotation state
        quotation.status = Quotation.Status.PENDING
        quotation.requote_comments = comments
        quotation.quote_total = 0
        quotation.supplier_quote_pdf = None
        quotation.save()

        # Send email to supplier
        from django.core.mail import send_mail
        from django.conf import settings
        
        email_to = quotation.supplier_email
        if not email_to and quotation.supplier and quotation.supplier.supplier:
            email_to = quotation.supplier.supplier.user.email
            
        if email_to:
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            supplier_link = f"{frontend_url}/supplier-quote/{quotation.supplier_token}"
            
            subject = f"Re-quote Requested: {quotation.quote_ref}"
            message = (
                f"Hello,\n\n"
                f"We have requested a re-quote for {quotation.quote_ref}.\n\n"
                f"Procurement feedback:\n{comments}\n\n"
                f"Please submit your revised pricing by clicking the link below:\n\n"
                f"{supplier_link}\n\n"
                f"Thank you."
            )
            
            send_mail(
                subject,
                message,
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@payparo.tech'),
                [email_to],
                fail_silently=True,
            )

        serializer = self.get_serializer(quotation)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
            company = request.user.company
            
            # If current user has no company or company has no logo, get the first company that does
            if not company or not company.company_logo:
                from app.account.models import Company
                company = Company.objects.exclude(company_logo='').first()

            if company and company.company_logo:
                try:
                    logo_path = company.company_logo.path
                except Exception:
                    pass
            
            # Fallback to static logo if company logo not uploaded
            if not logo_path:
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

from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
import json

class SupplierQuotationView(APIView):
    """
    GET /procurement/supplier-quote/<token>/ -> Returns quotation details
    PATCH /procurement/supplier-quote/<token>/ -> Update supplier prices & upload quote PDF
    """
    permission_classes = [AllowAny]

    def get(self, request, token):
        quotation = get_object_or_404(Quotation, supplier_token=token)
        serializer = QuotationSerializer(quotation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, token):
        quotation = get_object_or_404(Quotation, supplier_token=token)
        
        # Handle file upload if present
        if 'supplier_quote_pdf' in request.FILES:
            quotation.supplier_quote_pdf = request.FILES['supplier_quote_pdf']
            quotation.save(update_fields=['supplier_quote_pdf'])

        # Handle line items pricing update
        # If line_items are passed as a JSON string within form-data
        line_items_data = request.data.get('line_items')
        if line_items_data:
            if isinstance(line_items_data, str):
                try:
                    line_items_data = json.loads(line_items_data)
                except json.JSONDecodeError:
                    return Response({"error": "Invalid line_items JSON"}, status=status.HTTP_400_BAD_REQUEST)
            
            if isinstance(line_items_data, list):
                for item_data in line_items_data:
                    item_id = item_data.get('id')
                    supplier_price = item_data.get('supplier_price')
                    
                    if item_id is not None and supplier_price is not None:
                        try:
                            line_item = quotation.line_items.get(id=item_id)
                            line_item.supplier_price = supplier_price
                            line_item.save(update_fields=['supplier_price'])
                        except Exception:
                            pass # Skip invalid IDs
        
        # Recalculate quote_total if needed or keep existing logic
        serializer = QuotationSerializer(quotation)
        return Response(serializer.data, status=status.HTTP_200_OK)

class CallOffListViewSet(viewsets.GenericViewSet, viewsets.mixins.ListModelMixin, viewsets.mixins.UpdateModelMixin):
    """
    Handles Call Off List logic:
    - GET list: returns QuotationLineItems for Approved Quotations
    - PATCH: allows toggling management_approved
    - POST (custom action): create a new OrderLineCallOff
    """
    from .serializers import CallOffLineItemSerializer
    serializer_class = CallOffLineItemSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        from .models import QuotationLineItem
        
        # Base filter: Quotation must be approved
        queryset = QuotationLineItem.objects.filter(quotation__status='Approved')
        
        if self.request.user.role == UserAccount.Role.ADMIN:
            return queryset.filter(quotation__project__company=self.request.user.company)

        # Allow Procurement dept to see all company call-offs
        role_assignment = RoleAssignment.objects.filter(
            user=self.request.user, 
            role=UserAccount.Role.PROCUREMENT_DEPARTMENT
        ).first()
        
        user_qs = QuotationLineItem.objects.none()
        if role_assignment and role_assignment.company:
            user_qs = queryset.filter(quotation__project__company=role_assignment.company)
            
        # Include those assigned to user
        assigned_qs = queryset.filter(quotation__project__in=self.request.user.assigned_projects.all())
        
        return (user_qs | assigned_qs).distinct().select_related(
            'quotation', 'quotation__project', 'quotation__main_folder', 
            'quotation__sub_folder', 'quotation__supplier__supplier'
        ).prefetch_related('call_offs', 'call_offs__called_off_by', 'call_offs__approved_by')

    @action(detail=True, methods=['post'])
    def create_call_off(self, request, pk=None):
        from .models import OrderLineCallOff
        line_item = self.get_object()
        qty = request.data.get('qty')
        price = request.data.get('price')
        expected_delivery = request.data.get('expected_delivery_date')
        call_off_ref = request.data.get('call_off_ref')
        
        if not qty or not price:
            return Response({"error": "qty and price are required"}, status=status.HTTP_400_BAD_REQUEST)
            
        # Convert empty strings to None for date
        if not expected_delivery:
            expected_delivery = None
            
        # Create the call off
        call_off = OrderLineCallOff.objects.create(
            line_item=line_item,
            call_off_ref=call_off_ref or "",
            qty=qty,
            price=price,
            expected_delivery_date=expected_delivery,
            called_off_by=request.user
            # approved_by can be set later depending on workflow
        )
        
        serializer = self.get_serializer(line_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
