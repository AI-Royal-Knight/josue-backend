from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from django.contrib.auth import authenticate

from drf_spectacular.utils import extend_schema

from app.account.service import ProfileService

from .serializers import (
    LoginSerializer,
    SendInvitationSerializer,
    AcceptInvitationSerializer,
)
from .tokens import get_tokens_for_user
from .models import Invitation, RoleAssignment, UserProfile, SupplierProfile, CompanySupplier, Company, UserAccount
from app.project_admin.models import Project

# Helpers

def _first_error(serializer) -> str:
    """Extract the first human-readable error from serializer.errors."""
    for field, messages in serializer.errors.items():
        msg = str(messages[0]) if isinstance(messages, list) and messages else str(messages)
        if field == "non_field_errors":
            return msg
        return f"{field}: {msg}"
    return "Invalid data."

# Helpers End

class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = ProfileService.get_profile(
            request.user
        )

        return Response(data, status=status.HTTP_200_OK)

    def put(self, request):
        user = request.user
        data = request.data

        # Update basic info
        user.first_name = data.get("first_name", user.first_name)
        user.last_name = data.get("last_name", user.last_name)
        # Email can be tricky if we want to enforce uniqueness or confirmation, but for now we'll allow it:
        if "email" in data and data["email"]:
            user.email = data["email"]
        if "backup_email" in data:
            user.backup_email = data["backup_email"]
            
        user.save()

        updated_data = ProfileService.get_profile(user)
        return Response(updated_data, status=status.HTTP_200_OK)



class LoginView(APIView):
    """Authenticate with email + password; returns JWT pair."""
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=LoginSerializer, responses={200: dict})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": _first_error(serializer)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if not user:
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"error": "Account is not active. Please verify your email."},
                status=status.HTTP_403_FORBIDDEN,
            )

        tokens = get_tokens_for_user(user)

        return Response(
            {
                "success": True,
                "access_token": tokens["access"],
                "refresh_token": tokens["refresh"],
                "user": {
                    "role": user.role,
                    "email": user.email,
                    "first_name": user.first_name or "",
                    "last_name": user.last_name or "",
                }
            },
            status=status.HTTP_200_OK,
        )


class SendInvitationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=SendInvitationSerializer, responses={200: dict})
    def post(self, request):
        serializer = SendInvitationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": _first_error(serializer)}, status=status.HTTP_400_BAD_request)
            
        # Logic to create Invitation and send email
        # ...
        return Response({"success": True, "message": "Invitation sent"})


class ValidateInvitationView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        try:
            invitation = Invitation.objects.get(token=token, status=Invitation.Status.PENDING)
            if invitation.is_expired():
                return Response({"error": "Invitation expired"}, status=status.HTTP_400_BAD_REQUEST)
                
            return Response({
                "email": invitation.email,
                "role": invitation.role,
                "company_id": invitation.company_id,
                "project_id": invitation.project_id
            })
        except Invitation.DoesNotExist:
            return Response({"error": "Invalid token"}, status=status.HTTP_404_NOT_FOUND)


class AcceptInvitationView(APIView):
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(request=AcceptInvitationSerializer, responses={200: dict})
    def post(self, request):
        serializer = AcceptInvitationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)
            
        token = serializer.validated_data["token"]
        try:
            invitation = Invitation.objects.get(token=token, status=Invitation.Status.PENDING)
        except Invitation.DoesNotExist:
            return Response({"error": "Invalid token"}, status=status.HTTP_404_NOT_FOUND)
            
        if invitation.is_expired():
            return Response({"error": "Invitation expired"}, status=status.HTTP_400_BAD_REQUEST)
            
        # Create or update user
        user, created = UserAccount.objects.get_or_create(
            email=invitation.email,
            defaults={
                'first_name': serializer.validated_data["first_name"],
                'last_name': serializer.validated_data["last_name"],
            }
        )
        if created:
            user.set_password(serializer.validated_data["password"])
            user.save()
            
        # Create role assignment
        RoleAssignment.objects.create(
            user=user,
            role=invitation.role,
            company=invitation.company,
            project=invitation.project
        )
        
        # Mark invitation as accepted
        invitation.status = Invitation.Status.ACCEPTED
        invitation.save()
        
        return Response({"success": True})
