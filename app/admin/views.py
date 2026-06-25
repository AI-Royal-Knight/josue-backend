from rest_framework.views import APIView
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status

from app.account.permissions import IsAdmin

from .serializers import AdminProfileSerializer, AdminProfileUpdateSerializer
from drf_spectacular.utils import extend_schema

class HomeView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response({
            "total_users": 12,
            "active_projects": 23
        }, status=status.HTTP_200_OK)


class AdminProfileView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses={200: AdminProfileSerializer})
    def get(self, request):
        serializer = AdminProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=AdminProfileUpdateSerializer, responses={200: AdminProfileSerializer})
    def put(self, request):
        serializer = AdminProfileUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(AdminProfileSerializer(request.user).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import uuid
from app.super_admin.models import CompanyInvitation
from app.account.models import UserAccount
from .serializers import ProjectAdminInviteSerializer, ProjectAdminListSerializer

class ProjectAdminsView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses={200: ProjectAdminListSerializer(many=True)})
    def get(self, request):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        project_admins = UserAccount.objects.filter(
            company=request.user.company,
            role=UserAccount.Role.PROJECT_ADMIN
        ).order_by('-date_joined')
        
        serializer = ProjectAdminListSerializer(project_admins, many=True)
        return Response({
            "project_admins": serializer.data,
            "total_count": project_admins.count()
        }, status=status.HTTP_200_OK)

    @extend_schema(request=ProjectAdminInviteSerializer, responses={201: dict})
    def post(self, request):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ProjectAdminInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if UserAccount.objects.filter(email=data["email"]).exists():
            return Response(
                {"error": "User with this email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            project_admin_user = UserAccount.objects.create_user(
                email=data["email"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                role=UserAccount.Role.PROJECT_ADMIN,
                company=request.user.company,
                is_active=False,
            )

            invitation = CompanyInvitation.objects.create(
                company=request.user.company,
                user=project_admin_user,
                token=uuid.uuid4(),
                expires_at=timezone.now() + timedelta(days=7),
            )

            invitation_link = f"https://yourfrontend.com/invitation/{invitation.token}"
            
            subject = 'Invitation to join as Project Admin'
            message = (
                f'Hello {project_admin_user.first_name},\n\n'
                f'You have been invited as a Project Admin for {request.user.company.company_name}.\n'
                f'Please use the following link to accept your invitation and set up your account:\n'
                f'{invitation_link}\n\n'
                f'This link will expire in 7 days.\n\n'
                f'Thank you.'
            )
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [project_admin_user.email],
                fail_silently=False,
            )

        return Response(
            {
                "message": "Project admin created successfully. Invitation email sent.",
                "user_id": project_admin_user.id,
                "invitation_expires_at": invitation.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )

