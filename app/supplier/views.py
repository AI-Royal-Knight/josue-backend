from django.utils import timezone
from django.contrib.auth import authenticate
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema

from app.account.models import UserAccount, SupplierProfile, CompanySupplier
from .models import SupplierInvitation, SupplierInvoice
from .permissions import IsSupplier, IsActiveSupplierForCompany
from .serializers import (
    SupplierInvitationDetailSerializer,
    SupplierInvitationAcceptSerializer,
    SupplierCompanyRelationshipSerializer,
    SupplierInvoiceSerializer,
    SupplierInvoiceCreateSerializer,
)


class SupplierInvitationDetailsView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: SupplierInvitationDetailSerializer})
    def get(self, request, token):
        try:
            invitation = SupplierInvitation.objects.select_related(
                "company", "company_supplier", "company_supplier__supplier"
            ).get(token=token)
        except SupplierInvitation.DoesNotExist:
            return Response(
                {"detail": "Invitation not found.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if invitation.is_expired() and invitation.status == SupplierInvitation.Status.PENDING:
            invitation.status = SupplierInvitation.Status.EXPIRED
            invitation.save(update_fields=["status"])

        serializer = SupplierInvitationDetailSerializer(invitation)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SupplierInvitationAcceptView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=SupplierInvitationAcceptSerializer, responses={200: dict})
    def post(self, request, token):
        try:
            invitation = SupplierInvitation.objects.select_related(
                "company", "company_supplier", "company_supplier__supplier"
            ).get(token=token)
        except SupplierInvitation.DoesNotExist:
            return Response(
                {"detail": "Invitation not found.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if invitation.status == SupplierInvitation.Status.ACCEPTED:
            return Response(
                {"detail": "This invitation has already been accepted.", "code": "already_accepted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if invitation.status == SupplierInvitation.Status.DECLINED:
            return Response(
                {"detail": "This invitation was declined.", "code": "declined"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if invitation.is_expired():
            invitation.status = SupplierInvitation.Status.EXPIRED
            invitation.save(update_fields=["status"])
            return Response(
                {"detail": "This invitation has expired.", "code": "expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SupplierInvitationAcceptSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve or create the user account
        user = UserAccount.objects.filter(email__iexact=invitation.email).first()
        is_new_user = not user or not user.has_usable_password()

        if is_new_user:
            password = serializer.validated_data.get("password")
            if not password or len(password) < 8:
                return Response(
                    {"password": ["Password must be at least 8 characters long."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not user:
                user = UserAccount(
                    email=invitation.email.lower().strip(),
                    role=UserAccount.Role.SUPPLIER,
                )

            user.first_name = serializer.validated_data.get("first_name", user.first_name) or "Supplier"
            user.last_name = serializer.validated_data.get("last_name", user.last_name) or ""
            user.set_password(password)
            user.is_active = True
            user.role = UserAccount.Role.SUPPLIER
            user.save()
        else:
            # User already exists and has credentials
            user.is_active = True
            user.save(update_fields=["is_active"])

        # Ensure SupplierProfile exists
        company_name_input = serializer.validated_data.get("company_name") or invitation.supplier_name
        supplier_profile, _ = SupplierProfile.objects.get_or_create(
            user=user,
            defaults={"company_name": company_name_input or "Supplier"}
        )
        if company_name_input and not supplier_profile.company_name:
            supplier_profile.company_name = company_name_input
            supplier_profile.save(update_fields=["company_name"])

        # Create/ensure RoleAssignment for supplier
        from app.account.models import RoleAssignment
        RoleAssignment.objects.get_or_create(
            user=user,
            role=UserAccount.Role.SUPPLIER,
            company=invitation.company,
        )

        # Ensure CompanySupplier is linked and marked ACTIVE
        cs = invitation.company_supplier
        cs.supplier = supplier_profile
        cs.status = CompanySupplier.Status.ACTIVE
        cs.accepted_at = timezone.now()
        cs.save()

        # Update Invitation
        invitation.status = SupplierInvitation.Status.ACCEPTED
        invitation.accepted_at = timezone.now()
        invitation.save()

        # Issue JWT tokens for instant seamless login
        refresh = RefreshToken.for_user(user)

        return Response({
            "success": True,
            "message": f"Invitation accepted! You are now connected to {invitation.company.company_name}.",
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
            },
            "company": {
                "id": str(invitation.company.id),
                "company_name": invitation.company.company_name,
            },
        }, status=status.HTTP_200_OK)


class SupplierInvitationDeclineView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: dict})
    def post(self, request, token):
        try:
            invitation = SupplierInvitation.objects.select_related("company_supplier").get(token=token)
        except SupplierInvitation.DoesNotExist:
            return Response(
                {"detail": "Invitation not found.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if invitation.status == SupplierInvitation.Status.ACCEPTED:
            return Response(
                {"detail": "This invitation has already been accepted.", "code": "already_accepted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation.status = SupplierInvitation.Status.DECLINED
        invitation.declined_at = timezone.now()
        invitation.save(update_fields=["status", "declined_at"])

        cs = invitation.company_supplier
        cs.status = CompanySupplier.Status.DECLINED
        cs.declined_at = timezone.now()
        cs.save(update_fields=["status", "declined_at"])

        return Response(
            {"success": True, "message": "You have declined this invitation."},
            status=status.HTTP_200_OK,
        )


class SupplierAuthLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=dict, responses={200: dict})
    def post(self, request):
        email = request.data.get("email", "").lower().strip()
        password = request.data.get("password", "")

        if not email or not password:
            return Response(
                {"detail": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = UserAccount.objects.filter(email=email).first()
        if not user or not user.check_password(password):
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"detail": "Your account is inactive. Please contact support."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Verify supplier role
        if user.role != UserAccount.Role.SUPPLIER:
            from app.account.models import RoleAssignment
            has_supplier_profile = SupplierProfile.objects.filter(user=user).exists()
            has_supplier_role = RoleAssignment.objects.filter(user=user, role=UserAccount.Role.SUPPLIER).exists()
            if not has_supplier_profile and not has_supplier_role:
                return Response(
                    {"detail": "This login portal is reserved for suppliers."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        refresh = RefreshToken.for_user(user)

        # Get active company relationships
        active_relationships = CompanySupplier.objects.select_related("company").filter(
            supplier__user=user,
            status=CompanySupplier.Status.ACTIVE
        )
        companies_data = [
            {
                "id": str(rel.company.id),
                "company_name": rel.company.company_name,
                "credit_limit": str(rel.credit_limit),
                "eom_payment_terms": rel.eom_payment_terms,
            }
            for rel in active_relationships
        ]

        return Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": UserAccount.Role.SUPPLIER,
            },
            "active_companies": companies_data,
        }, status=status.HTTP_200_OK)


class SupplierCompanyListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSupplier]

    @extend_schema(responses={200: SupplierCompanyRelationshipSerializer(many=True)})
    def get(self, request):
        relationships = CompanySupplier.objects.select_related("company", "supplier").filter(
            supplier__user=request.user
        ).order_by("-created_at")

        serializer = SupplierCompanyRelationshipSerializer(relationships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SupplierInvoiceListView(APIView):
    permission_classes = [IsActiveSupplierForCompany]

    @extend_schema(responses={200: SupplierInvoiceSerializer(many=True)})
    def get(self, request):
        invoices = SupplierInvoice.objects.select_related(
            "company", "company_supplier", "company_supplier__supplier", "company_supplier__supplier__user"
        ).filter(
            company=request.active_company,
            company_supplier=request.active_company_supplier
        ).order_by("-created_at")

        serializer = SupplierInvoiceSerializer(invoices, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=SupplierInvoiceCreateSerializer, responses={201: SupplierInvoiceSerializer})
    def post(self, request):
        serializer = SupplierInvoiceCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        invoice = serializer.save(
            company=request.active_company,
            company_supplier=request.active_company_supplier,
            submitted_by=request.user,
            status=SupplierInvoice.Status.SUBMITTED
        )

        output_serializer = SupplierInvoiceSerializer(invoice)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class SupplierInvoiceDetailView(APIView):
    permission_classes = [IsActiveSupplierForCompany]

    @extend_schema(responses={200: SupplierInvoiceSerializer})
    def get(self, request, pk):
        try:
            invoice = SupplierInvoice.objects.select_related(
                "company", "company_supplier", "company_supplier__supplier", "company_supplier__supplier__user"
            ).get(
                id=pk,
                company=request.active_company,
                company_supplier=request.active_company_supplier
            )
        except SupplierInvoice.DoesNotExist:
            return Response(
                {"detail": "Invoice not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SupplierInvoiceSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SupplierQuotationListView(APIView):
    permission_classes = [IsActiveSupplierForCompany]

    @extend_schema(responses={200: dict})
    def get(self, request):
        from app.procurement_department.models import Quotation
        from app.procurement_department.serializers import QuotationSerializer
        from django.db.models import Q

        quotations = Quotation.objects.select_related(
            "project", "supplier", "supplier__supplier", "main_folder", "sub_folder"
        ).prefetch_related(
            "line_items", "history"
        ).filter(
            Q(supplier=request.active_company_supplier) |
            (Q(project__company=request.active_company) & Q(supplier_email__icontains=request.user.email))
        ).distinct().order_by("-created_at")

        serializer = QuotationSerializer(quotations, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class SupplierQuotationDetailView(APIView):
    permission_classes = [IsActiveSupplierForCompany]

    @extend_schema(responses={200: dict})
    def get(self, request, pk):
        from app.procurement_department.models import Quotation
        from app.procurement_department.serializers import QuotationSerializer
        from django.db.models import Q

        try:
            quotation = Quotation.objects.select_related(
                "project", "supplier", "supplier__supplier", "main_folder", "sub_folder"
            ).prefetch_related(
                "line_items", "history"
            ).get(
                Q(id=pk) & (
                    Q(supplier=request.active_company_supplier) |
                    (Q(project__company=request.active_company) & Q(supplier_email__icontains=request.user.email))
                )
            )
        except Quotation.DoesNotExist:
            return Response({"detail": "Quotation not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = QuotationSerializer(quotation, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=dict, responses={200: dict})
    def patch(self, request, pk):
        from app.procurement_department.models import Quotation
        from app.procurement_department.serializers import QuotationSerializer
        from django.db.models import Q
        import json
        import decimal

        try:
            quotation = Quotation.objects.get(
                Q(id=pk) & (
                    Q(supplier=request.active_company_supplier) |
                    (Q(project__company=request.active_company) & Q(supplier_email__icontains=request.user.email))
                )
            )
        except Quotation.DoesNotExist:
            return Response({"detail": "Quotation not found."}, status=status.HTTP_404_NOT_FOUND)

        if 'supplier_quote_pdf' in request.FILES:
            quotation.supplier_quote_pdf = request.FILES['supplier_quote_pdf']
            quotation.save(update_fields=['supplier_quote_pdf'])

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
                            pass

        # Recalculate quote_total from line items
        total = decimal.Decimal('0.0')
        has_supplier_price = False
        for item in quotation.line_items.all():
            if item.supplier_price is not None:
                has_supplier_price = True
            price = item.supplier_price if item.supplier_price is not None else item.each
            discount = item.discount or decimal.Decimal('0.0')
            qty = item.qty or decimal.Decimal('1.0')
            line_total = float(qty) * float(price) * (1.0 - (float(discount) / 100.0))
            total += decimal.Decimal(str(round(line_total, 2)))

        if has_supplier_price:
            quotation.quote_total = total
            quotation.save(update_fields=['quote_total'])

        serializer = QuotationSerializer(quotation, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

