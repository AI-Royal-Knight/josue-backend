from app.project_admin.models import Project
projects = Project.objects.all()
for p in projects:
    print(f"ID: {p.id}, Name: {p.project_name}")
