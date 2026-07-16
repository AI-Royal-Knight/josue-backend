from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from drf_spectacular.utils import extend_schema

from app.account.service import ProfileService
from app.super_admin.models import RecentActivity

from .serializers import (
    LoginSerializer,
    SendInvitationSerializer,
    AcceptInvitationSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    SubmitApplicationSerializer,
    ChangePasswordSerializer,
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

        # Update profile info
        import json
        profile_data_raw = data.get("profile", {})
        if isinstance(profile_data_raw, str):
            try:
                profile_data = json.loads(profile_data_raw)
            except json.JSONDecodeError:
                profile_data = {}
        else:
            profile_data = profile_data_raw
            
        if profile_data:
            try:
                profile = user.profile
            except Exception:
                from .models import UserProfile
                profile = UserProfile.objects.create(user=user)
                
            for field in [
                'cscs_card_no', 'cscs_expiry_date', 'ipaf_certification', 'pasma_certification',
                'sssts_smsts', 'profession', 'emergency_contact_name', 'emergency_contact_number',
                'categories', 'insurance_policy', 'employer_liability', 'terms_accepted', 'digital_signature',
                'ni_number', 'utr', 'passport_number', 'passport_expiry_date'
            ]:
                if field in profile_data:
                    val = profile_data[field]
                    if val == "" and field.endswith('_date'):
                        val = None
                    setattr(profile, field, val)
                    
            if 'passport_document' in request.FILES:
                profile.passport_document = request.FILES['passport_document']
                
            profile.save()

        # Update company info
        company_data_raw = data.get("company", {})
        if isinstance(company_data_raw, str):
            try:
                company_data = json.loads(company_data_raw)
            except json.JSONDecodeError:
                company_data = {}
        else:
            company_data = company_data_raw
            
        if company_data:
            if not user.company:
                from .models import Company
                company = Company.objects.create()
                user.company = company
                user.save()
            
            company = user.company
            for field in [
                'company_name', 'company_number', 'building_number', 'street', 'town', 'city', 'postcode',
                'vat_number', 'phone', 'utr', 'bank_name', 'bank_address', 'sort_code', 'account_number',
                'iban', 'swift_bic', 'public_liability_policy', 'public_liability_expiry', 
                'employers_liability_policy', 'employers_liability_expiry'
            ]:
                if field in company_data:
                    val = company_data[field]
                    if val == "":
                        val = None
                    setattr(company, field, val)
                    
            if 'public_liability_document' in request.FILES:
                company.public_liability_document = request.FILES['public_liability_document']
            if 'employers_liability_document' in request.FILES:
                company.employers_liability_document = request.FILES['employers_liability_document']
                
            company.save()

        updated_data = ProfileService.get_profile(user)
        return Response(updated_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """Blacklists the refresh token to logout."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                from rest_framework_simplejwt.tokens import RefreshToken
                token = RefreshToken(refresh_token)
                token.blacklist()
                return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)
            return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


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

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = UserAccount.objects.filter(email=email).first()
        
        if not user or not user.check_password(password):
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"error": "Account is not active. Please verify your email or contact support."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if hasattr(user, 'profile') and not user.profile.is_approved:
            return Response(
                {"error": "Your account is pending approval by an administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if getattr(user, 'company', None) and not user.company.activate:
            return Response(
                {"error": "Your company account has been deactivated. Please contact support."},
                status=status.HTTP_403_FORBIDDEN,
            )

        tokens = get_tokens_for_user(user)

        response_data = {
            "success": True,
            "access_token": tokens["access"],
            "refresh_token": tokens["refresh"],
            "user": {
                "role": user.role,
                "email": user.email,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
            }
        }

        if user.role == 'employee':
            from django.utils import timezone
            from app.employee.models import AttendanceLog
            today = timezone.now().date()
            is_checked_in = AttendanceLog.objects.filter(
                user=user,
                date=today,
                status='checked_in'
            ).exists()
            response_data["user"]["checked_in"] = is_checked_in

        return Response(response_data, status=status.HTTP_200_OK)


class SendInvitationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=SendInvitationSerializer, responses={200: dict})
    def post(self, request):
        serializer = SendInvitationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)
            
        email = serializer.validated_data["email"]
        role = serializer.validated_data["role"]
        
        # Check if user already exists
        if UserAccount.objects.filter(email=email).exists():
            return Response({"error": "A user with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)
            
        # Create Invitation
        invitation = Invitation.objects.create(
            email=email,
            role=role,
            company=request.user.company,
            invited_by=request.user,
            expires_at=timezone.now() + timezone.timedelta(days=7)
        )
        
        # Send Email
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
        invitation_link = f"{frontend_url}/accept-invite/{invitation.token}"
        
        role_display = dict(UserAccount.Role.choices).get(role, role)
        company_name = request.user.company.company_name if request.user.company else "our platform"
        
        subject = f"Invitation to join as {role_display}"
        message = (
            f"Hello,\n\n"
            f"You have been invited to join {company_name} as a {role_display}.\n"
            f"Please click the link below to accept your invitation and set up your account:\n"
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
        
        RecentActivity.objects.create(activity_name=f"{request.user.get_role_display()} invited {email} as {role_display}.")
        
        return Response({"success": True, "message": "Invitation sent successfully."})


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
                'role': invitation.role,
                'company': invitation.company,
                'is_active': True,
            }
        )
        if created:
            user.set_password(serializer.validated_data["password"])
            user.save()
            
        # Create role assignment
        RoleAssignment.objects.get_or_create(
            user=user,
            role=invitation.role,
            company=invitation.company,
            project=invitation.project
        )
        
        # Mark invitation as accepted
        invitation.status = Invitation.Status.ACCEPTED
        invitation.save()
        
        RecentActivity.objects.create(activity_name=f"User {user.first_name} {user.last_name} accepted the {user.get_role_display()} invitation.")
        
        return Response({"success": True})


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=ForgotPasswordSerializer, responses={200: dict})
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        user = UserAccount.objects.filter(email=email).first()

        # Always return success to prevent email enumeration
        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
            reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"
            
            subject = "Reset Your Password"
            message = (
                f"Hello {user.first_name},\n\n"
                f"You requested to reset your password. Please click the link below to set a new password:\n"
                f"{reset_link}\n\n"
                f"If you did not request this, please ignore this email.\n\n"
                f"Thank you."
            )
            
            send_mail(
                subject,
                message,
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@tresta.cloud'),
                [user.email],
                fail_silently=True,
            )

        return Response({"success": True, "message": "If an account with that email exists, a reset link has been sent."})


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=ResetPasswordSerializer, responses={200: dict})
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)

        uid_b64 = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        try:
            uid = force_str(urlsafe_base64_decode(uid_b64))
            user = UserAccount.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, UserAccount.DoesNotExist):
            return Response({"error": "Invalid reset link."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"error": "Invalid or expired reset link."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({"success": True, "message": "Password has been successfully reset."})

class ChangePasswordView(APIView):
    """Allows an authenticated user to change their password."""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ChangePasswordSerializer, responses={200: dict})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        old_password = serializer.validated_data["old_password"]
        new_password = serializer.validated_data["new_password"]

        if not user.check_password(old_password):
            return Response({"error": "Incorrect current password."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({"message": "Password updated successfully."}, status=status.HTTP_200_OK)


class SubmitApplicationView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=SubmitApplicationSerializer, responses={200: dict})
    def post(self, request):
        serializer = SubmitApplicationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        email = data["email"]

        if UserAccount.objects.filter(email=email).exists():
            return Response({"error": "A user with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

        # Get or Create Company
        company_name = data.get("company_name")
        company = None
        if company_name:
            company = Company.objects.filter(company_name__iexact=company_name.strip()).first()
        if not company:
            company = Company.objects.create(
                company_name=company_name,
                company_number=data.get("company_house_number") if data.get("company_house_number") and data.get("company_house_number").isdigit() else None,
                vat_number=data.get("company_utr"),
                bank_name=data.get("bank_name"),
                bank_address=data.get("bank_address"),
                account_number=data.get("account_number"),
                sort_code=data.get("sort_code"),
                building_number=None, # Frontend just passes "building" string
                street=data.get("building"),
                postcode=data.get("postcode")
            )

        # Create User
        user = UserAccount.objects.create(
            email=email,
            first_name=data["first_name"],
            last_name=data["last_name"],
            role=data["role"],
            company=company,
            is_active=True,  # Wait, usually this is pending, but since frontend currently just toggles `is_approved`, we can leave it active but unapproved profile.
        )
        user.set_password(data["password"])
        user.save()

        # Create Role Assignment
        RoleAssignment.objects.create(
            user=user,
            role=data["role"],
            company=company
        )

        # Create User Profile
        UserProfile.objects.create(
            user=user,
            profession=data["role"],
            cscs_card_no=data.get("cscs"),
            cscs_expiry_date=data.get("cscs_expiry"),
            ipaf_certification=data.get("ipaf"),
            pasma_certification=data.get("pasma"),
            sssts_smsts=data.get("smsts"),
            categories=data.get("categories"),
            insurance_policy=data.get("insurance_policy"),
            employer_liability=data.get("employer_liability"),
            terms_accepted=data.get("terms_accepted", False),
            digital_signature=data.get("signature"),
            is_approved=False
        )

        return Response({"success": True, "message": "Application submitted successfully."})


class UsersListView(APIView):
    permission_classes = [permissions.AllowAny] # For demo purposes, realistically IsAuthenticated

    def get(self, request):
        users = UserAccount.objects.all().select_related('profile', 'company')
        
        if not request.user.is_authenticated:
            users = users.none()
        elif request.user.role == UserAccount.Role.SUPER_ADMIN:
            pass  # Super admin sees all
        elif request.user.role == UserAccount.Role.ADMIN:
            if request.user.company and request.user.company.company_name:
                users = users.filter(company__company_name__iexact=request.user.company.company_name).exclude(role=UserAccount.Role.SUPER_ADMIN)
            else:
                users = users.filter(company=request.user.company).exclude(role=UserAccount.Role.SUPER_ADMIN)
        else:
            if request.user.company and request.user.company.company_name:
                users = users.filter(company__company_name__iexact=request.user.company.company_name).exclude(role__in=[UserAccount.Role.SUPER_ADMIN, UserAccount.Role.ADMIN])
            else:
                users = users.filter(company=request.user.company).exclude(role__in=[UserAccount.Role.SUPER_ADMIN, UserAccount.Role.ADMIN])

        result = []
        for u in users:
            profile = getattr(u, 'profile', None)
            company = u.company

            # Expiry tone logic
            import datetime
            today = datetime.date.today()
            
            cscs_expiry_tone = "emerald"
            if profile and profile.cscs_expiry_date:
                if profile.cscs_expiry_date < today:
                    cscs_expiry_tone = "red"

            expiry_tone = "emerald"

            result.append({
                "id": str(u.id),
                "name": u.first_name,
                "surname": u.last_name,
                "email": u.email,
                "phone": company.phone if company else "",
                "role": u.role,
                "profession": dict(UserAccount.Role.choices).get(u.role, u.role),
                "cscsCardNo": profile.cscs_card_no if profile else "",
                "cscsExpiryDate": str(profile.cscs_expiry_date) if profile and profile.cscs_expiry_date else "",
                "cscsExpiryTone": cscs_expiry_tone,
                "ipaf": profile.ipaf_certification if profile else "",
                "pasma": profile.pasma_certification if profile else "",
                "company": company.company_name if company else "",
                "ssstsSmsts": profile.sssts_smsts if profile else "",
                "expiryDate": "",
                "expiryTone": expiry_tone,
                "approvedUser": profile.is_approved if profile else False,
                "approvedBy": dict(UserAccount.Role.choices).get(profile.approved_by.role, profile.approved_by.role) if profile and profile.approved_by else ""
            })
            
        return Response(result)

    def post(self, request):
        """Used to toggle user approval."""
        user_id = request.data.get("user_id")
        approved = request.data.get("approved")

        try:
            user = UserAccount.objects.get(id=user_id)
            
            # Get or create UserProfile
            try:
                profile = user.profile
            except UserAccount.profile.RelatedObjectDoesNotExist:
                profile = UserProfile.objects.create(
                    user=user,
                    profession=user.role
                )
                
            profile.is_approved = approved
            if approved and request.user.is_authenticated:
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
            RecentActivity.objects.create(activity_name=f"User {user.email} was {action} by {request.user.get_role_display() if request.user.is_authenticated else 'System'}.")

            return Response({"success": True})
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .models import Notification
        from .serializers import NotificationSerializer
        notifications = Notification.objects.filter(user=request.user)
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from .models import Notification
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
            notification.is_read = True
            notification.save()
            return Response({"success": True})
        except Notification.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

class NotificationMarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .models import Notification
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"success": True})

class RequestAdminView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from .models import Company, UserAccount
        from app.super_admin.models import CompanyInvitation, RecentActivity
        from django.db import transaction
        from django.utils import timezone
        from datetime import timedelta
        import uuid
        
        data = request.data
        email = data.get("email", "").lower().strip()
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        company_name = data.get("company_name", "")
        phone_number = data.get("phone_number", "")
        
        if not all([email, first_name, last_name, company_name, phone_number]):
            return Response({"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        if UserAccount.objects.filter(email=email).exists():
            return Response({"error": "A user with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)
            
        with transaction.atomic():
            company = Company.objects.filter(company_name__iexact=company_name.strip()).first()
            if not company:
                company = Company.objects.create(
                    company_name=company_name,
                    phone=phone_number,
                    activate=False,
                    status=Company.Status.SUSPENDED,
                )
            
            admin_user = UserAccount.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
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
            
            RecentActivity.objects.create(
                activity_name=f"New admin request received from {admin_user.email} for {company.company_name}."
            )
            
        return Response({"success": True, "message": "Your request has been submitted successfully."}, status=status.HTTP_201_CREATED)
