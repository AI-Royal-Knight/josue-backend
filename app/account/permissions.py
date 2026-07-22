from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_super_admin


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return(
            request.user.is_authenticated
            and request.user.role in ["admin"]
        )

class IsAdminOrProjectAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in [
                "admin",
                "project_admin"
            ]
        )
class IsAdminOrSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in [
                "super_admin",
                "admin"
            ]
        )

class CanManageProjectFolders(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.role in ["admin", "project_admin"]:
            return True
            
        pk = view.kwargs.get('pk')
        if not pk:
            return False
            
        from app.account.models import RoleAssignment
        return RoleAssignment.objects.filter(
            user=request.user,
            project_id=pk,
            role__in=["contracts_manager", "managers", "supervisor", "managing_director", "project_director"]
        ).exists()

class CanManageProjectRoles(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.role in ["admin", "project_admin"]:
            return True
            
        pk = view.kwargs.get('pk')
        if not pk:
            return False
            
        from app.account.models import RoleAssignment
        return RoleAssignment.objects.filter(
            user=request.user,
            project_id=pk,
            role__in=["contracts_manager", "managers", "supervisor", "managing_director", "project_director"]
        ).exists()

class IsAdminOrProjectAdminOrCompanyManager(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.role in ["admin", "project_admin", "managing_director", "project_director", "contracts_manager", "managers", "supervisor"]:
            return True
        return False
