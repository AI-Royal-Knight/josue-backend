from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_spectacular.utils import extend_schema

from app.account.permissions import IsAdmin
from .models import Project
from .serializers import (
    ProjectListSerializer,
    ProjectCreateSerializer,
    ProjectUpdateSerializer,
)


class ProjectListCreateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses={200: ProjectListSerializer(many=True)})
    def get(self, request):
        if not request.user.company:
            return Response(
                {"error": "Admin has no associated company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        projects = Project.objects.filter(company=request.user.company)

        serializer = ProjectListSerializer(projects, many=True)
        return Response(
            {
                "projects": serializer.data,
                "total_count": projects.count(),
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=ProjectCreateSerializer,
        responses={201: ProjectListSerializer},
    )
    def post(self, request):
        if not request.user.company:
            return Response(
                {"error": "Admin has no associated company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProjectCreateSerializer(data=request.data)
        if serializer.is_valid():
            project = serializer.save(company=request.user.company)
            return Response(
                ProjectListSerializer(project).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProjectDetailView(APIView):
    permission_classes = [IsAdmin]

    def get_object(self, pk, company):
        try:
            return Project.objects.get(pk=pk, company=company)
        except Project.DoesNotExist:
            return None

    @extend_schema(responses={200: ProjectListSerializer})
    def get(self, request, pk):
        if not request.user.company:
            return Response(
                {"error": "Admin has no associated company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = self.get_object(pk, request.user.company)
        if not project:
            return Response(
                {"error": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProjectListSerializer(project)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=ProjectUpdateSerializer,
        responses={200: ProjectListSerializer},
    )
    def put(self, request, pk):
        if not request.user.company:
            return Response(
                {"error": "Admin has no associated company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = self.get_object(pk, request.user.company)
        if not project:
            return Response(
                {"error": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProjectUpdateSerializer(project, data=request.data, partial=True)
        if serializer.is_valid():
            project = serializer.save()
            return Response(
                ProjectListSerializer(project).data,
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not request.user.company:
            return Response(
                {"error": "Admin has no associated company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = self.get_object(pk, request.user.company)
        if not project:
            return Response(
                {"error": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        project.delete()
        return Response(
            {"message": "Project deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )
