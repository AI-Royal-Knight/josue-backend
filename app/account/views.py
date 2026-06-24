from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from django.contrib.auth import authenticate

from drf_spectacular.utils import extend_schema

from app.account.service import ProfileService

from .serializers import (
    LoginSerializer,
)
from .tokens import get_tokens_for_user

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
