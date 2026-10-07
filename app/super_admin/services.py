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
        Falls back to company.user if no direct accounts/invites exist yet.
        """
        from app.account.models import UserAccount, Invitation
        users_count = UserAccount.objects.filter(company=company).exclude(
            role=UserAccount.Role.SUPER_ADMIN
        ).count()
        if company.company_name:
            name_users = UserAccount.objects.filter(
                company__company_name__iexact=company.company_name.strip()
            ).exclude(role=UserAccount.Role.SUPER_ADMIN).count()
            users_count = max(users_count, name_users)

        invites_count = Invitation.objects.filter(
            company=company, status=Invitation.Status.PENDING
        ).count()
        if company.company_name:
            name_invites = Invitation.objects.filter(
                company__company_name__iexact=company.company_name.strip(),
                status=Invitation.Status.PENDING
            ).count()
            invites_count = max(invites_count, name_invites)

        total = users_count + invites_count
        if total == 0 and company.user:
            total = company.user
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
    def get_super_admin_billing_details():
        """
        Retrieves the billing / bank details from the super admin's profile.
        Falls back to default Tresta / Estrada values if fields are unset.
        """
        from app.account.models import UserAccount, UserProfile
        super_admin = UserAccount.objects.filter(role=UserAccount.Role.SUPER_ADMIN).first()
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

