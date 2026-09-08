from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied, NotAuthenticated
from app.account.models import UserAccount, CompanySupplier


class IsSupplier(BasePermission):
    message = "Only authenticated suppliers can access this resource."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == UserAccount.Role.SUPPLIER:
            return True
        from app.account.models import SupplierProfile, RoleAssignment
        return (
            SupplierProfile.objects.filter(user=request.user).exists()
            or RoleAssignment.objects.filter(user=request.user, role=UserAccount.Role.SUPPLIER).exists()
        )


class IsActiveSupplierForCompany(BasePermission):
    message = "You do not have an active supplier relationship with this company."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated("Authentication credentials were not provided.")

        from app.account.models import SupplierProfile, RoleAssignment
        is_supplier = (
            request.user.role == UserAccount.Role.SUPPLIER
            or SupplierProfile.objects.filter(user=request.user).exists()
            or RoleAssignment.objects.filter(user=request.user, role=UserAccount.Role.SUPPLIER).exists()
        )
        if not is_supplier:
            raise PermissionDenied("Only supplier accounts can perform this action.")

        company_id = (
            request.headers.get("X-Company-ID")
            or request.data.get("company_id")
            or request.query_params.get("company_id")
        )

        if not company_id:
            raise PermissionDenied("A company context (X-Company-ID header or company_id) is required.")

        company_supplier = CompanySupplier.objects.select_related("company", "supplier").filter(
            supplier__user=request.user,
            company_id=company_id,
            status=CompanySupplier.Status.ACTIVE
        ).first()

        if not company_supplier:
            raise PermissionDenied("You do not have an active supplier relationship with the specified company.")

        # Attach active company context to the request for convenient access in views
        request.active_company_supplier = company_supplier
        request.active_company = company_supplier.company
        return True
