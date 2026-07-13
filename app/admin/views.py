from rest_framework.views import APIView
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status

from app.account.permissions import IsAdmin
from app.account.models import UserAccount
from app.project_admin.models import Project

from .serializers import AdminProfileSerializer, AdminProfileUpdateSerializer
from drf_spectacular.utils import extend_schema

class HomeView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        company = request.user.company
        if company and company.company_name:
            total_users = UserAccount.objects.filter(company__company_name__iexact=company.company_name).count()
            active_projects = Project.objects.filter(company__company_name__iexact=company.company_name, is_completed=False).count()
        else:
            total_users = UserAccount.objects.filter(company=company).count()
            active_projects = Project.objects.filter(company=company, is_completed=False).count()

        return Response({
            "total_users": total_users,
            "active_projects": active_projects
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
from .serializers import ProjectAdminInviteSerializer, ProjectAdminListSerializer

class ProjectAdminsView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses={200: ProjectAdminListSerializer(many=True)})
    def get(self, request):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        if request.user.company and request.user.company.company_name:
            project_admins = UserAccount.objects.filter(
                company__company_name__iexact=request.user.company.company_name,
                role=UserAccount.Role.PROJECT_ADMIN
            ).order_by('-date_joined')
        else:
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

        existing_user = UserAccount.objects.filter(email=data["email"]).first()
        if existing_user and existing_user.is_active:
            return Response(
                {"error": "User with this email already exists and is active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            if existing_user:
                existing_user.first_name = data["first_name"]
                existing_user.last_name = data["last_name"]
                existing_user.role = UserAccount.Role.PROJECT_ADMIN
                existing_user.company = request.user.company
                existing_user.save()
                project_admin_user = existing_user
                
                CompanyInvitation.objects.filter(user=project_admin_user).delete()
            else:
                project_admin_user = UserAccount.objects.create_user(
                    email=data["email"],
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    role=UserAccount.Role.PROJECT_ADMIN,
                    company=request.user.company,
                    is_active=False,
                )

            if "project_ids" in data and data["project_ids"]:
                projects = Project.objects.filter(id__in=data["project_ids"], company=request.user.company)
                project_admin_user.assigned_projects.set(projects)


            invitation = CompanyInvitation.objects.create(
                company=request.user.company,
                user=project_admin_user,
                token=uuid.uuid4(),
                expires_at=timezone.now() + timedelta(days=7),
            )

            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
            invitation_link = f"{frontend_url}/invitation/{invitation.token}"
            
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
                settings.DEFAULT_FROM_EMAIL or 'noreply@tresta.com',
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


from .serializers import AdminProjectSerializer, ManagingDirectorInviteSerializer, ManagingDirectorListSerializer

class ManagingDirectorsView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses={200: ManagingDirectorListSerializer(many=True)})
    def get(self, request):
        managing_directors = UserAccount.objects.filter(
            role=UserAccount.Role.MANAGING_DIRECTOR
        )
        if request.user.company and request.user.company.company_name:
            managing_directors = managing_directors.filter(
                company__company_name__iexact=request.user.company.company_name
            )
        else:
            managing_directors = managing_directors.filter(
                company=request.user.company
            )
            
        managing_directors = managing_directors.order_by('-date_joined')
        
        serializer = ManagingDirectorListSerializer(managing_directors, many=True)
        return Response({
            "managing_directors": serializer.data,
            "total_count": managing_directors.count()
        }, status=status.HTTP_200_OK)

    @extend_schema(request=ManagingDirectorInviteSerializer, responses={201: dict})
    def post(self, request):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ManagingDirectorInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        existing_user = UserAccount.objects.filter(email=data["email"]).first()
        if existing_user and existing_user.is_active:
            return Response(
                {"error": "User with this email already exists and is active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            if existing_user:
                existing_user.first_name = data["first_name"]
                existing_user.last_name = data["last_name"]
                existing_user.role = UserAccount.Role.MANAGING_DIRECTOR
                existing_user.company = request.user.company
                existing_user.save()
                md_user = existing_user
                
                CompanyInvitation.objects.filter(user=md_user).delete()
            else:
                md_user = UserAccount.objects.create_user(
                    email=data["email"],
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    role=UserAccount.Role.MANAGING_DIRECTOR,
                    company=request.user.company,
                    is_active=False,
                )

            invitation = CompanyInvitation.objects.create(
                company=request.user.company,
                user=md_user,
                token=uuid.uuid4(),
                expires_at=timezone.now() + timedelta(days=7),
            )

            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
            invitation_link = f"{frontend_url}/invitation/{invitation.token}"
            
            subject = 'Invitation to join as Managing Director'
            message = (
                f'Hello {md_user.first_name},\n\n'
                f'You have been invited as a Managing Director for {request.user.company.company_name}.\n'
                f'Please use the following link to accept your invitation and set up your account:\n'
                f'{invitation_link}\n\n'
                f'This link will expire in 7 days.\n\n'
                f'Thank you.'
            )
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL or 'noreply@tresta.com',
                [md_user.email],
                fail_silently=False,
            )

        return Response(
            {
                "message": "Managing Director created successfully. Invitation email sent.",
                "user_id": md_user.id,
                "invitation_expires_at": invitation.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )

class AdminProjectListView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses={200: AdminProjectSerializer(many=True)})
    def get(self, request):
        if not request.user.company:
            return Response({"error": "Admin has no associated company."}, status=status.HTTP_400_BAD_REQUEST)

        if request.user.company and request.user.company.company_name:
            projects = Project.objects.filter(
                company__company_name__iexact=request.user.company.company_name,
                is_completed=False
            ).order_by('-created_at')
        else:
            projects = Project.objects.filter(
                company=request.user.company,
                is_completed=False
            ).order_by('-created_at')
        serializer = AdminProjectSerializer(projects, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
