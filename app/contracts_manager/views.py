from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from app.account.models import RoleAssignment, UserAccount
from app.project_admin.models import Project, ProjectSubfolder
from .serializers import CMProjectSerializer

class CMProjectListView(APIView):
    """
    List all projects explicitly assigned to the user as a CONTRACTS_MANAGER, MANAGERS, or SUPERVISOR.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role_assignment = RoleAssignment.objects.filter(
            user=request.user, 
            role__in=[UserAccount.Role.CONTRACTS_MANAGER, UserAccount.Role.MANAGERS, UserAccount.Role.SUPERVISOR]
        ).first()
        
        if not role_assignment or not role_assignment.company:
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
            
        projects = request.user.assigned_projects.all()
        serializer = CMProjectSerializer(projects, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CMSubfolderUpdateView(APIView):
    """
    Update the rows (and targets) for a specific subfolder.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            subfolder = ProjectSubfolder.objects.get(pk=pk)
        except ProjectSubfolder.DoesNotExist:
            return Response({"error": "Subfolder not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check if the user is authorized to this project
        if not request.user.assigned_projects.filter(id=subfolder.folder.project.id).exists():
            return Response({"detail": "Not authorized to access this project's folders."}, status=status.HTTP_403_FORBIDDEN)

        rows = request.data.get('rows')
        if rows is not None:
            if not isinstance(rows, list):
                return Response({"error": "Rows must be a list."}, status=status.HTTP_400_BAD_REQUEST)
            subfolder.rows = rows
        
        if 'project_value' in request.data:
            subfolder.project_value = request.data['project_value']
            
        if 'labour_target' in request.data:
            subfolder.labour_target = request.data['labour_target']

        if 'assignments' in request.data:
            from app.project_admin.models import FolderAssignment
            assignments_data = request.data['assignments']
            
            # Delete existing non-management assignments for this subfolder
            FolderAssignment.objects.filter(subfolder=subfolder, is_management_assignment=False).delete()
            
            for asn in assignments_data:
                user_data = asn.get('user')
                if not user_data:
                    continue
                user_id = user_data.get('id')
                hide_labour = asn.get('hide_labour_target', False)
                FolderAssignment.objects.create(
                    subfolder=subfolder,
                    user_id=user_id,
                    hide_labour_target=hide_labour,
                    is_management_assignment=False
                )

        subfolder.save()
        return Response({"message": "Subfolder updated successfully."}, status=status.HTTP_200_OK)
