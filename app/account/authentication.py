from rest_framework_simplejwt.authentication import JWTAuthentication

class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, token = result
            active_role = request.headers.get("X-Active-Role")
            
            # Check if active role is valid for this user
            from app.account.models import UserAccount
            has_role = False
            if active_role:
                if active_role == "manager":
                    active_role = UserAccount.Role.MANAGERS

                if user.role in [UserAccount.Role.ADMIN, UserAccount.Role.SUPER_ADMIN]:
                    has_role = True
                elif active_role in [user.role, user.secondary_role]:
                    has_role = True
                elif hasattr(user, 'role_assignments') and user.role_assignments.filter(role=active_role).exists():
                    has_role = True

            if has_role:
                user.active_role = active_role
            else:
                user.active_role = user.role
                
            # Temporarily overwrite the `role` property for this request lifecycle
            # so that all existing permissions classes (e.g. `request.user.role == 'admin'`)
            # work identically with the selected role.
            user.role = user.active_role
            
        return result


try:
    from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme

    class CustomJWTScheme(SimpleJWTScheme):
        target_class = 'app.account.authentication.CustomJWTAuthentication'
except ImportError:
    pass
