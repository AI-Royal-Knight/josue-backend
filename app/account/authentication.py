from rest_framework_simplejwt.authentication import JWTAuthentication

class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, token = result
            active_role = request.headers.get("X-Active-Role")
            
            # If an active role is provided and it matches one of the user's roles
            if active_role and active_role in [user.role, user.secondary_role]:
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
