from app.account.models import UserAccount
from app.super_admin.models import RecentActivity


class DashboardService:

    @staticmethod
    def get_super_admin_dashboard():

        return {
            "statistics": {
                "admin_users": UserAccount.objects.filter(
                    role=UserAccount.Role.ADMIN
                ).count(),

                "users": UserAccount.objects.count(),
            },

            "recent_activities": [
                {
                    "id": activity.id,
                    "message": activity.activity_name,
                    "created_at": activity.created_at,
                }
                for activity in RecentActivity.objects
                .order_by("-created_at")[:10]
            ],
        }


class InvoiceService:

    @staticmethod
    def get_company_registered_users_count(company):
        """
        Count all users registered for the company plus pending invitations.
        Excludes super admins.
        Calculates the maximum of:
        - Actually registered/assigned users (UserAccount direct, RoleAssignment, name match)
        - Pending invitations (both Invitation and CompanyInvitation)
        - company.user allocated seats
        Keeps company.user updated in the database so all views stay in sync.
        """
        from app.account.models import UserAccount, Invitation, RoleAssignment
        from app.super_admin.models import CompanyInvitation

        user_ids = set(
            UserAccount.objects.filter(company=company)
            .exclude(role=UserAccount.Role.SUPER_ADMIN)
            .values_list('id', flat=True)
        )
        if company.company_name:
            user_ids.update(
                UserAccount.objects.filter(
                    company__company_name__iexact=company.company_name.strip()
                )
                .exclude(role=UserAccount.Role.SUPER_ADMIN)
                .values_list('id', flat=True)
            )

        # Include users associated via RoleAssignment
        role_user_ids = RoleAssignment.objects.filter(company=company).exclude(
            user__role=UserAccount.Role.SUPER_ADMIN
        ).values_list('user_id', flat=True)
        user_ids.update(role_user_ids)

        # Include pending invitations
        invites_count = Invitation.objects.filter(
            company=company, status=Invitation.Status.PENDING
        ).count()
        if company.company_name:
            name_invites = Invitation.objects.filter(
                company__company_name__iexact=company.company_name.strip(),
                status=Invitation.Status.PENDING
            ).count()
            invites_count = max(invites_count, name_invites)

        company_invites = CompanyInvitation.objects.filter(
            company=company, accepted=False
        ).count()

        actual_active = len(user_ids) + invites_count + company_invites
        allocated_seats = company.user or 0

        total = max(actual_active, allocated_seats)
        if company.user != total:
            company.user = total
            company.save(update_fields=['user'])

        return total

    @staticmethod
    def calculate_monthly_invoice_breakdown(company):
        """
        Calculates the breakdown for a company's monthly invoice:
        - monthly_sub: Decimal (subscription fee, e.g. £100.00)
        - per_user: Decimal (per user rate, e.g. £5.00)
        - users_count: int (number of registered users, e.g. 5)
        - user_licenses_total: Decimal (e.g. 5 * £5.00 = £25.00)
        - total_amount: Decimal (monthly_sub + user_licenses_total = £125.00)
        """
        from decimal import Decimal
        monthly_sub = company.monthly_subscription or Decimal("0.00")
        per_user = company.per_user_rate or Decimal("0.00")
        users_count = InvoiceService.get_company_registered_users_count(company)
        user_licenses_total = per_user * users_count
        total_amount = monthly_sub + user_licenses_total

        return {
            "monthly_sub": monthly_sub,
            "per_user": per_user,
            "users_count": users_count,
            "user_licenses_total": user_licenses_total,
            "total_amount": total_amount,
        }

    @staticmethod
    def get_super_admin_billing_details(user=None):
        """
        Retrieves the billing / bank details from the super admin's profile.
        Falls back to default Tresta / Estrada values if fields are unset.
        If a user object is provided and is a super admin, prioritizes their profile.
        Otherwise, selects the super admin with the most recently updated profile.
        """
        from app.account.models import UserAccount, UserProfile
        defaults = {
            "company_name": "Tresta",
            "account_name": "Estrada building services",
            "bank_name": "Santander",
            "sort_code": "09-01-28",
            "account_number": "82051171",
            "vat_number": "237 5409 01",
            "address": "84 Alers Road\nBexleyheath, DA6 8HT",
            "email": "info@tresta.cloud",
            "iban": "",
            "swift_bic": "",
        }

        super_admin = None
        if user and (getattr(user, 'is_super_admin', False) or getattr(user, 'role', None) == UserAccount.Role.SUPER_ADMIN):
            super_admin = user

        if not super_admin:
            # Pick the super admin whose profile was most recently updated
            super_admin = (
                UserAccount.objects.filter(role=UserAccount.Role.SUPER_ADMIN)
                .order_by('-profile__updated_at', '-date_joined')
                .first()
            )

        if not super_admin:
            return defaults

        try:
            profile = super_admin.profile
        except Exception:
            profile, _ = UserProfile.objects.get_or_create(
                user=super_admin,
                defaults={
                    "company_name": defaults["company_name"],
                    "account_name": defaults["account_name"],
                    "bank_name": defaults["bank_name"],
                    "sort_code": defaults["sort_code"],
                    "account_number": defaults["account_number"],
                    "vat_number": defaults["vat_number"],
                    "address": defaults["address"],
                    "bank_address": defaults["address"],
                }
            )

        return {
            "company_name": profile.company_name or defaults["company_name"],
            "account_name": profile.account_name or defaults["account_name"],
            "bank_name": profile.bank_name or defaults["bank_name"],
            "sort_code": profile.sort_code or defaults["sort_code"],
            "account_number": profile.account_number or defaults["account_number"],
            "vat_number": profile.vat_number or defaults["vat_number"],
            "address": profile.address or profile.bank_address or defaults["address"],
            "email": super_admin.email or defaults["email"],
            "iban": profile.iban or "",
            "swift_bic": profile.swift_bic or "",
        }

