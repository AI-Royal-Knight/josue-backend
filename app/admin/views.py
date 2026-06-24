from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from app.account.permissions import IsAdmin

class HomeView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response({
            "total_users": 12,
            "active_projects": 23
        }, status=status.HTTP_200_OK)



