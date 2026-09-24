from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

from drf_spectacular.utils import extend_schema

from app.account.service import ProfileService
from app.super_admin.models import RecentActivity
from core.utils import get_frontend_url, get_default_from_email

from .serializers import (
    LoginSerializer,
    SendInvitationSerializer,
    AcceptInvitationSerializer,
    ForgotPasswordSerializer,
    VerifyOTPSerializer,
    ResetPasswordSerializer,
    SubmitApplicationSerializer,
    ChangePasswordSerializer,
)
from .tokens import get_tokens_for_user
import random
from django.core.cache import cache
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

    @extend_schema(responses={200: dict})
    def get(self, request):
        data = ProfileService.get_profile(
            request.user, context={"request": request}
        )

        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(request=dict, responses={200: dict})
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
                'ni_number', 'utr', 'passport_number', 'passport_expiry_date',
                'bank_name', 'bank_address', 'sort_code', 'account_number', 'iban', 'swift_bic'
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
            if 'company_logo' in request.FILES:
                company.company_logo = request.FILES['company_logo']
                
            company.save()

        updated_data = ProfileService.get_profile(user, context={"request": request})
        return Response(updated_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """Blacklists the refresh token to logout."""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=dict, responses={200: dict})
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

        # Only employee (mobile app) users are blocked until the Document Controller approves them.
        # Management roles don't require profile approval to log in.
        if user.role == UserAccount.Role.EMPLOYEE:
            if hasattr(user, 'profile') and not user.profile.is_approved:
                return Response(
                    {"error": "Your account is pending review by the Document Controller. You will be notified once approved."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if getattr(user, 'company', None) and not user.company.activate:
            return Response(
                {"error": "Your company account has been deactivated. Please contact support."},
                status=status.HTTP_403_FORBIDDEN,
            )

        tokens = get_tokens_for_user(user)

        from app.account.models import RoleAssignment
        assignments = RoleAssignment.objects.filter(user=user)
        role_assignments_data = [
            {
                "id": str(a.id),
                "role": a.role,
                "company_id": str(a.company_id) if a.company_id else None,
                "project_id": str(a.project_id) if a.project_id else None,
            }
            for a in assignments
        ]

        response_data = {
            "success": True,
            "access_token": tokens["access"],
            "refresh_token": tokens["refresh"],
            "user": {
                "role": user.role,
                "secondary_role": getattr(user, 'secondary_role', None),
                "email": user.email,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "role_assignments": role_assignments_data,
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

    # Maps each caller role → the set of roles they are allowed to invite
    INVITE_PERMISSIONS = {
        UserAccount.Role.SUPER_ADMIN: {
            UserAccount.Role.ADMIN,
        },
        UserAccount.Role.ADMIN: {
            UserAccount.Role.PROJECT_ADMIN,
            UserAccount.Role.MANAGING_DIRECTOR,
        },
        UserAccount.Role.PROJECT_ADMIN: {
            UserAccount.Role.PROJECT_DIRECTOR,
            UserAccount.Role.CONTRACTS_MANAGER,
            UserAccount.Role.MANAGERS,
            UserAccount.Role.SUPERVISOR,
            UserAccount.Role.DOCUMENT_CONTROLLER,
            UserAccount.Role.PROCUREMENT_DEPARTMENT,
            UserAccount.Role.COMMERCIAL_DEPARTMENT,
            UserAccount.Role.FINANCE_DEPARTMENT,
            UserAccount.Role.TECHNICAL_DEPARTMENT,
        },
        # These management roles can only invite mobile-app (employee) users
        UserAccount.Role.CONTRACTS_MANAGER: {UserAccount.Role.EMPLOYEE},
        UserAccount.Role.MANAGERS: {UserAccount.Role.EMPLOYEE},
        "manager": {UserAccount.Role.EMPLOYEE},
        UserAccount.Role.PROJECT_DIRECTOR: {UserAccount.Role.EMPLOYEE},
        UserAccount.Role.SUPERVISOR: {UserAccount.Role.EMPLOYEE},
        UserAccount.Role.DOCUMENT_CONTROLLER: {UserAccount.Role.EMPLOYEE},
        # Supplier invitations are strictly separate and handled via /api/v1/procurement/suppliers/invite/
    }

    @extend_schema(request=SendInvitationSerializer, responses={200: dict})
    def post(self, request):
        serializer = SendInvitationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)

        caller_role = request.user.role
        if caller_role == "manager":
            caller_role = UserAccount.Role.MANAGERS
        email = serializer.validated_data["email"]
        role = serializer.validated_data["role"]

        # ── Role-based invite permission check ───────────────────────────────
        allowed_roles = self.INVITE_PERMISSIONS.get(caller_role, set())
        if not allowed_roles and caller_role == "manager":
            allowed_roles = self.INVITE_PERMISSIONS.get(UserAccount.Role.MANAGERS, set())
        if role not in allowed_roles:
            return Response(
                {"error": f"Your role ({caller_role}) is not permitted to invite users as '{role}'."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if user already exists
        if UserAccount.objects.filter(email=email).exists():
            return Response({"error": "A user with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

        # For employee invites, create them with is_active=False (pending document controller approval)
        # For all other roles, is_active=True after they accept the invite

        # Create Invitation
        invitation = Invitation.objects.create(
            email=email,
            role=role,
            secondary_role=serializer.validated_data.get("secondary_role"),
            company=request.user.company,
            invited_by=request.user,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )

        # Send Email
        frontend_url = get_frontend_url(request)
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

        html_message = render_to_string('emails/invite_email.html', {
            'role_display': role_display,
            'company_name': company_name,
            'invitation_link': invitation_link,
        })

        send_mail(
            subject,
            message,
            get_default_from_email(),
            [email],
            fail_silently=False,
            html_message=html_message,
        )

        RecentActivity.objects.create(
            activity_name=f"{request.user.get_role_display()} invited {email} as {role_display}."
        )

        return Response({"success": True, "message": "Invitation sent successfully."})


class AllowedInviteRolesView(APIView):
    """Returns the list of roles the current user is permitted to invite."""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: dict})
    def get(self, request):
        caller_role = request.user.role
        allowed = SendInvitationView.INVITE_PERMISSIONS.get(caller_role, set())
        if not allowed and caller_role == "manager":
            allowed = SendInvitationView.INVITE_PERMISSIONS.get(UserAccount.Role.MANAGERS, set())
        role_choices = dict(UserAccount.Role.choices)
        return Response({
            "allowed_roles": [
                {"value": r, "label": role_choices.get(r, r)}
                for r in allowed
            ],
            "caller_role": caller_role,
        })


class ValidateInvitationView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: dict})
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

        # Employee (mobile app) users stay inactive until document controller approves them
        is_employee = invitation.role == UserAccount.Role.EMPLOYEE
        is_active_on_accept = not is_employee

        # Create or update user
        user, created = UserAccount.objects.get_or_create(
            email=invitation.email,
            defaults={
                'first_name': serializer.validated_data["first_name"],
                'last_name': serializer.validated_data["last_name"],
                'role': invitation.role,
                'secondary_role': invitation.secondary_role,
                'company': invitation.company,
                'is_active': is_active_on_accept,
            }
        )
        # Always update credentials and details regardless of whether account was pre-created
        user.first_name = serializer.validated_data["first_name"]
        user.last_name = serializer.validated_data["last_name"]
        user.role = invitation.role
        if invitation.secondary_role:
            user.secondary_role = invitation.secondary_role
        if not user.company and invitation.company:
            user.company = invitation.company
        user.is_active = is_active_on_accept
        user.set_password(serializer.validated_data["password"])
        user.save()

        # Create UserProfile for employees so document controller can review & approve
        if is_employee:
            UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'profession': 'employee',
                    'is_approved': False,
                }
            )

        # If supplier, ensure SupplierProfile and CompanySupplier link are created
        if invitation.role == UserAccount.Role.SUPPLIER:
            from app.account.models import SupplierProfile, CompanySupplier
            from app.supplier.models import SupplierInvitation
            supplier_profile, _ = SupplierProfile.objects.get_or_create(
                user=user,
                defaults={'company_name': f"{user.first_name} {user.last_name}".strip() or "Supplier"}
            )
            if invitation.company:
                cs, _ = CompanySupplier.objects.get_or_create(
                    company=invitation.company,
                    supplier=supplier_profile,
                    defaults={'eom_payment_terms': 30, 'credit_limit': 0.00}
                )
                cs.status = CompanySupplier.Status.ACTIVE
                cs.accepted_at = timezone.now()
                cs.save()

                SupplierInvitation.objects.filter(
                    token=str(invitation.token),
                    status=SupplierInvitation.Status.PENDING
                ).update(status=SupplierInvitation.Status.ACCEPTED, accepted_at=timezone.now())

        # Create role assignment
        RoleAssignment.objects.get_or_create(
            user=user,
            role=invitation.role,
            company=invitation.company,
            project=invitation.project
        )
        if invitation.secondary_role:
            RoleAssignment.objects.get_or_create(
                user=user,
                role=invitation.secondary_role,
                company=invitation.company,
                project=invitation.project
            )
        
        # Mark invitation as accepted
        invitation.status = Invitation.Status.ACCEPTED
        invitation.save()

        if is_employee:
            message = "Application submitted. Your account is pending review by the Document Controller."
        else:
            message = "Account activated successfully. You can now log in."
        
        RecentActivity.objects.create(activity_name=f"User {user.first_name} {user.last_name} accepted the {user.get_role_display()} invitation.")
        
        return Response({"success": True, "message": message, "pending_approval": is_employee})


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
            
            # OTP generation
            otp = f"{random.randint(0, 9999):04d}"
            cache.set(f"password_reset_otp_{user.email}", otp, timeout=900)
            
            frontend_url = get_frontend_url(request)
            reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"
            
            subject = "Reset Your Password - Tresta"
            message = (
                f"Hello {user.first_name},\n\n"
                f"You requested to reset your password. Please use the following 4-digit code in the app:\n"
                f"{otp}\n\n"
                f"Or, click the link below to set a new password:\n"
                f"{reset_link}\n\n"
                f"If you did not request this, please ignore this email.\n\n"
                f"Thank you."
            )
            
            html_message = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f4f5; padding: 40px 20px; margin: 0; color: #3f3f46;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                    <div style="background-color: #2563eb; padding: 30px; text-align: center;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 1px;">PASSWORD RESET</h1>
                    </div>
                    <div style="padding: 40px 30px;">
                        <p style="margin-top: 0; font-size: 16px; line-height: 24px;">Hello <strong>{user.first_name}</strong>,</p>
                        <p style="font-size: 16px; line-height: 24px;">We received a request to reset the password for your account.</p>
                        
                        <p style="font-size: 16px; line-height: 24px; margin-top: 20px;">If you are using the app, enter this 4-digit verification code:</p>
                        <div style="text-align: center; margin: 20px 0;">
                            <span style="background-color: #f1f5f9; color: #0f172a; padding: 12px 24px; border-radius: 6px; font-size: 28px; font-weight: 700; letter-spacing: 8px;">{otp}</span>
                        </div>
                        
                        <p style="font-size: 16px; line-height: 24px; margin-top: 30px;">Or, click the button below to set a new password:</p>
                        <div style="text-align: center; margin: 20px 0 25px 0;">
                            <a href="{reset_link}" style="background-color: #2563eb; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block; font-size: 16px;">Reset Password</a>
                        </div>
                        
                        <p style="font-size: 13px; color: #94a3b8; word-break: break-all; text-align: center; margin-bottom: 25px;">
                            If the button above does not work, visit:<br>
                            <a href="{reset_link}" style="color: #2563eb;">{reset_link}</a>
                        </p>
                        
                        <p style="font-size: 14px; line-height: 22px; color: #71717a; margin-bottom: 0;">If you did not request a password reset, you can safely ignore this email. Your account is secure.</p>
                    </div>
                    <div style="background-color: #f8fafc; padding: 20px; text-align: center; border-top: 1px solid #e2e8f0;">
                        <p style="margin: 0; font-size: 12px; color: #94a3b8;">&copy; 2026 Tresta. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            send_mail(
                subject,
                message,
                get_default_from_email(),
                [user.email],
                fail_silently=True,
                html_message=html_message,
            )

        return Response({"success": True, "message": "If an account with that email exists, a reset link has been sent."})


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=VerifyOTPSerializer, responses={200: dict})
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]
        
        cached_otp = cache.get(f"password_reset_otp_{email}")
        
        if not cached_otp or cached_otp != otp:
            return Response({"error": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)
            
        return Response({"success": True, "message": "OTP verified successfully."})


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=ResetPasswordSerializer, responses={200: dict})
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": _first_error(serializer)}, status=status.HTTP_400_BAD_REQUEST)

        uid_b64 = serializer.validated_data.get("uid")
        token = serializer.validated_data.get("token")
        email = serializer.validated_data.get("email")
        otp = serializer.validated_data.get("otp")
        new_password = serializer.validated_data["new_password"]
        
        user = None

        if email and otp:
            # OTP based verification
            cached_otp = cache.get(f"password_reset_otp_{email}")
            if not cached_otp or cached_otp != otp:
                return Response({"error": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)
            
            user = UserAccount.objects.filter(email=email).first()
            if not user:
                return Response({"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST)
                
            # Clear the OTP after successful use
            cache.delete(f"password_reset_otp_{email}")
            
        elif uid_b64 and token:
            # URL Token based verification
            try:
                uid = force_str(urlsafe_base64_decode(uid_b64))
                user = UserAccount.objects.get(pk=uid)
            except (TypeError, ValueError, OverflowError, UserAccount.DoesNotExist):
                return Response({"error": "Invalid reset link."}, status=status.HTTP_400_BAD_REQUEST)

            if not default_token_generator.check_token(user, token):
                return Response({"error": "Invalid or expired reset link."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": "Must provide either uid/token or email/otp."}, status=status.HTTP_400_BAD_REQUEST)

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
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: dict})
    def get(self, request):
        users = UserAccount.objects.all().select_related('profile', 'company')
        caller_role = request.user.role

        if caller_role == UserAccount.Role.SUPER_ADMIN:
            pass  # Super admin sees everyone across all companies
        elif caller_role == UserAccount.Role.ADMIN:
            if request.user.company and request.user.company.company_name:
                users = users.filter(company__company_name__iexact=request.user.company.company_name).exclude(role=UserAccount.Role.SUPER_ADMIN)
            else:
                users = users.filter(company=request.user.company).exclude(role=UserAccount.Role.SUPER_ADMIN)
        elif caller_role == UserAccount.Role.DOCUMENT_CONTROLLER:
            # Document controllers only manage employee (mobile app) users — scoped to their company
            if request.user.company and request.user.company.company_name:
                users = users.filter(
                    company__company_name__iexact=request.user.company.company_name,
                    role=UserAccount.Role.EMPLOYEE
                )
            else:
                users = users.filter(
                    company=request.user.company,
                    role=UserAccount.Role.EMPLOYEE
                )
        else:
            # All other management roles see their company users (excluding super admin and admin)
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
                "secondaryRole": getattr(u, 'secondary_role', None),
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

    @extend_schema(request=dict, responses={200: dict})
    def post(self, request):
        """Used to toggle user approval.
        
        Rules:
        - Only document_controller can approve/unapprove employee (mobile app) users.
        - Only super_admin or admin can approve admin-level invitation users.
        - No one else can use this endpoint.
        """
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        user_id = request.data.get("user_id")
        approved = request.data.get("approved")

        try:
            user = UserAccount.objects.get(id=user_id)

            # ── Enforce who can approve whom ─────────────────────────────────
            caller_role = request.user.role

            if user.role == UserAccount.Role.EMPLOYEE:
                # Only document controllers can approve mobile app users
                if caller_role != UserAccount.Role.DOCUMENT_CONTROLLER:
                    return Response(
                        {"error": "Only Document Controllers can approve employee (mobile app) users."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            elif user.role in [UserAccount.Role.ADMIN, UserAccount.Role.PROJECT_ADMIN]:
                # Only super_admin or admin can approve admin-level users
                if caller_role not in [UserAccount.Role.SUPER_ADMIN, UserAccount.Role.ADMIN]:
                    return Response(
                        {"error": "Only Super Admins or Admins can approve admin-level users."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            else:
                # For all other roles, only admin or super_admin can approve
                if caller_role not in [UserAccount.Role.SUPER_ADMIN, UserAccount.Role.ADMIN]:
                    return Response(
                        {"error": "You do not have permission to approve this user."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

            # Get or create UserProfile
            try:
                profile = user.profile
            except UserAccount.profile.RelatedObjectDoesNotExist:
                profile = UserProfile.objects.create(
                    user=user,
                    profession=user.role
                )

            profile.is_approved = approved
            if approved:
                profile.approved_by = request.user
            else:
                profile.approved_by = None
            profile.save()

            # When approving an employee, also activate their account
            if user.role == UserAccount.Role.EMPLOYEE:
                user.is_active = approved
                user.save()
            elif approved and user.company:
                user.company.activate = True
                user.company.save()
            elif not approved and user.company:
                user.company.activate = False
                user.company.save()

            action = "approved" if approved else "unapproved"
            RecentActivity.objects.create(
                activity_name=f"User {user.email} was {action} by {request.user.get_role_display()}."
            )

            return Response({"success": True})
        except UserAccount.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: dict})
    def get(self, request):
        from .models import Notification
        from .serializers import NotificationSerializer
        notifications = Notification.objects.filter(user=request.user)
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=dict, responses={200: dict})
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

    @extend_schema(request=dict, responses={200: dict})
    def post(self, request):
        from .models import Notification
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"success": True})

class RequestAdminView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=dict, responses={200: dict})
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
