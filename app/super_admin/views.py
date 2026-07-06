from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from app.super_admin.services import DashboardService

from app.super_admin.serializers import (
    AdminInviteSerializer,
    CompanyListSerializer,
    AcceptCompanyInvitationSerializer
)

from app.account.permissions import IsSuperAdmin
from app.account.models import UserAccount, Company
from app.super_admin.models import CompanyInvitation, MonthlyInvoice, RecentActivity
from app.project_admin.models import Project

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from datetime import timedelta

import uuid

class Overview(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        data = DashboardService.get_super_admin_dashboard()

        return Response(data, status=status.HTTP_200_OK)


class CompaniesView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        companies = Company.objects.prefetch_related(
            Prefetch(
                'users', 
                queryset=UserAccount.objects.filter(role=UserAccount.Role.ADMIN), 
                to_attr='admin_users'
            )
        ).all()
        
        serializer = CompanyListSerializer(companies, many=True)
        
        admin_users_count = UserAccount.objects.filter(role=UserAccount.Role.ADMIN).count()
        users_count = UserAccount.objects.exclude(role=UserAccount.Role.SUPER_ADMIN).count()
        
        projects_count = Project.objects.count()
        active_count = Company.objects.filter(status=Company.Status.ACTIVE).count()
        suspended_count = Company.objects.filter(status=Company.Status.SUSPENDED).count()
        
        return Response({
            "summary": {
                "admin_users": admin_users_count,
                "users": users_count,
                "projects": projects_count,
                "active": active_count,
                "suspended": suspended_count
            },
            "companies": serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AdminInviteSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        if UserAccount.objects.filter(
            email=data["email"]
        ).exists():
            return Response(
                {
                    "error": "User with this email already exists."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():

            company = Company.objects.create(
                company_name=data["company_name"],
                phone=data["phone_number"],
                activate=True,
                status=Company.Status.ACTIVE,
            )

            admin_user = UserAccount.objects.create_user(
                email=data["email"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                role=UserAccount.Role.ADMIN,
                company=company,
                is_active=False,
            )

            invitation = CompanyInvitation.objects.create(
                company=company,
                user=admin_user,
                token=uuid.uuid4(),
                expires_at=timezone.now() + timedelta(days=7),
            )

            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
            invitation_link = (
                f"{frontend_url}/invitation/"
                f"{invitation.token}"
            )

            subject = 'Invitation to join as Admin'
            message = (
                f'Hello {admin_user.first_name},\n\n'
                f'You have been invited as an Admin for {company.company_name}.\n'
                f'Please use the following link to accept your invitation and set up your account:\n'
                f'{invitation_link}\n\n'
                f'This link will expire in 7 days.\n\n'
                f'Thank you.'
            )
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL or 'noreply@tresta.com',
                [admin_user.email],
                fail_silently=False,
            )
            
        RecentActivity.objects.create(activity_name=f"Super Admin invited {admin_user.email} as Admin for {company.company_name}.")

        return Response(
            {
                "message": (
                    "Company created successfully. "
                    "Invitation email sent."
                ),
                "company_id": company.id,
                "invitation_expires_at": invitation.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )


class CompanyDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    def patch(self, request, pk):
        try:
            company = Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return Response({"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND)

        data = request.data

        if "activate" in data:
            company.activate = data["activate"]
            if company.activate:
                company.status = Company.Status.ACTIVE
            else:
                company.status = Company.Status.SUSPENDED

        if "monthly_subscription" in data:
            company.monthly_subscription = data["monthly_subscription"]
            
        if "per_user_rate" in data:
            company.per_user_rate = data["per_user_rate"]
            
        if "auto_monthly_inv" in data:
            company.auto_monthly_inv = data["auto_monthly_inv"]
            
        company.save()

        # Prefetch the users again if returning the full serialized object
        company = Company.objects.prefetch_related(
            Prefetch(
                'users', 
                queryset=UserAccount.objects.filter(role=UserAccount.Role.ADMIN), 
                to_attr='admin_users'
            )
        ).get(pk=pk)

        serializer = CompanyListSerializer(company)
        return Response(serializer.data, status=status.HTTP_200_OK)

from drf_spectacular.utils import extend_schema

class ValidateCompanyInvitationView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        try:
            invitation = CompanyInvitation.objects.select_related('user', 'company').get(token=token, accepted=False)
            if timezone.now() > invitation.expires_at:
                return Response({"error": "Invitation expired"}, status=status.HTTP_400_BAD_REQUEST)
                
            return Response({
                "email": invitation.user.email,
                "first_name": invitation.user.first_name,
                "last_name": invitation.user.last_name,
                "company_name": invitation.company.company_name,
                "role": invitation.user.role
            })
        except CompanyInvitation.DoesNotExist:
            return Response({"error": "Invalid or already accepted token"}, status=status.HTTP_404_NOT_FOUND)

class AcceptCompanyInvitationView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=AcceptCompanyInvitationSerializer, responses={200: dict})
    def post(self, request):
        serializer = AcceptCompanyInvitationSerializer(data=request.data)
        if not serializer.is_valid():
            # Return first error
            errors = []
            for field, field_errors in serializer.errors.items():
                if isinstance(field_errors, list):
                    errors.append(field_errors[0])
                else:
                    errors.append(str(field_errors))
            return Response({"error": errors[0] if errors else "Invalid request"}, status=status.HTTP_400_BAD_REQUEST)

        token = serializer.validated_data["token"]
        try:
            invitation = CompanyInvitation.objects.select_related('user').get(token=token, accepted=False)
        except CompanyInvitation.DoesNotExist:
            return Response({"error": "Invalid or already accepted token"}, status=status.HTTP_404_NOT_FOUND)

        if timezone.now() > invitation.expires_at:
            return Response({"error": "Invitation expired"}, status=status.HTTP_400_BAD_REQUEST)

        user = invitation.user
        user.set_password(serializer.validated_data["password"])
        user.is_active = True
        user.save()

        invitation.accepted = True
        invitation.accepted_at = timezone.now()
        invitation.save()

        RecentActivity.objects.create(activity_name=f"User {user.first_name} {user.last_name} accepted the Admin invitation.")

        return Response({"success": True, "message": "Account activated successfully."})

class MonthlyInvoiceView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        year_str = request.query_params.get("year")
        if not year_str:
            return Response({"error": "year query parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            year = int(year_str)
        except ValueError:
            return Response({"error": "year must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
            
        invoices = MonthlyInvoice.objects.filter(year=year, is_sent=True)
        data = [
            {
                "id": inv.id,
                "company_id": inv.company_id,
                "year": inv.year,
                "month": inv.month,
                "amount": str(inv.amount) if inv.amount else None,
                "is_sent": inv.is_sent
            }
            for inv in invoices
        ]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        company_id = request.data.get("company_id")
        year = request.data.get("year")
        month = request.data.get("month")
        amount = request.data.get("amount")

        if not all([company_id, year, month]):
            return Response({"error": "company_id, year, and month are required"}, status=status.HTTP_400_BAD_REQUEST)

        invoice, created = MonthlyInvoice.objects.update_or_create(
            company_id=company_id,
            year=year,
            month=month,
            defaults={
                "amount": amount,
                "is_sent": True
            }
        )
        
        return Response({
            "id": invoice.id,
            "company_id": invoice.company_id,
            "year": invoice.year,
            "month": invoice.month,
            "amount": str(invoice.amount) if invoice.amount else None,
            "is_sent": invoice.is_sent
        }, status=status.HTTP_200_OK)

