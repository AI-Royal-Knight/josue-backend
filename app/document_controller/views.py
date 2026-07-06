from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema

from app.account.models import UserAccount, Invitation
from app.super_admin.models import RecentActivity
from .serializers import InviteEmployeeSerializer, ApproveEmployeeSerializer

def _first_error(serializer) -> str:
    """Extract the first human-readable error from serializer.errors."""
    for field, messages in serializer.errors.items():
        msg = str(messages[0]) if isinstance(messages, list) and messages else str(messages)
        if field == "non_field_errors":
            return msg
        return f"{field}: {msg}"
    return "Invalid data."

class InviteEmployeeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=InviteEmployeeSerializer, responses={200: dict})
    def post(self, request):
        if request.user.role not in [UserAccount.Role.DOCUMENT_CONTROLLER, UserAccount.Role.SUPER_ADMIN, UserAccount.Role.ADMIN]:
            return Response({"error": "You do not have permission to invite employees."}, status=status.HTTP_403_FORBIDDEN)

        serializer = InviteEmployeeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)
            
        email = serializer.validated_data["email"]
        first_name = serializer.validated_data["first_name"]
        last_name = serializer.validated_data["last_name"]
        
        if UserAccount.objects.filter(email=email).exists():
            return Response({"error": "A user with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)
            
        invitation = Invitation.objects.create(
            email=email,
            role=UserAccount.Role.EMPLOYEE,
            company=request.user.company,
            invited_by=request.user,
            expires_at=timezone.now() + timezone.timedelta(days=7)
        )
        
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
        invitation_link = f"{frontend_url}/accept-invite/{invitation.token}"
        
        company_name = request.user.company.company_name if request.user.company else "our platform"
        
        subject = f"Invitation to join as Employee"
        message = (
            f"Hello {first_name} {last_name},\n\n"
            f"You have been invited to join {company_name} as an Employee.\n"
            f"Please click the link below to accept your invitation and provide the necessary information:\n"
            f"{invitation_link}\n\n"
            f"This link will expire in 7 days.\n\n"
            f"Thank you."
        )
        
        send_mail(
            subject,
            message,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@tresta.com'),
            [email],
            fail_silently=False,
        )
        
        RecentActivity.objects.create(activity_name=f"{request.user.get_role_display()} invited employee {email}.")
        
        return Response({"success": True, "message": "Invitation sent successfully."})

class ApproveEmployeeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ApproveEmployeeSerializer, responses={200: dict})
    def post(self, request):
        if request.user.role not in [UserAccount.Role.DOCUMENT_CONTROLLER, UserAccount.Role.SUPER_ADMIN, UserAccount.Role.ADMIN]:
            return Response({"error": "You do not have permission to approve employees."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ApproveEmployeeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)

        user_id = serializer.validated_data["user_id"]
        approved = serializer.validated_data["approved"]

        try:
            user = UserAccount.objects.get(id=user_id)
            profile = user.profile
            profile.is_approved = approved
            if approved:
                profile.approved_by = request.user
            else:
                profile.approved_by = None
            profile.save()

            if approved and user.company:
                user.company.activate = True
                user.company.save()
            elif not approved and user.company:
                user.company.activate = False
                user.company.save()

            action = "approved" if approved else "unapproved"
            RecentActivity.objects.create(activity_name=f"User {user.email} was {action} by {request.user.get_role_display()}.")

            return Response({"success": True})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

