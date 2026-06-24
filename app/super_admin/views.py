from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from app.super_admin.services import DashboardService

from app.super_admin.serializers import (
    AdminInviteSerializer,
    CompanyListSerializer
)

from app.account.permissions import IsSuperAdmin
from app.account.models import UserAccount, Company
from app.super_admin.models import CompanyInvitation

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
        
        # Dummy data as requested
        projects_count = 789
        active_count = 12
        suspended_count = 3
        
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
                activate=False,
                status=Company.Status.SUSPENDED,
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

            invitation_link = (
                f"https://yourfrontend.com/invitation/"
                f"{invitation.token}"
            )

            # TODO:
            # Send email here
            #
            # send_invitation_email(
            #     user=admin_user,
            #     invitation_link=invitation_link
            # )

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
