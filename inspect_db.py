from app.project_admin.models import ApprovalConfiguration
configs = ApprovalConfiguration.objects.all()
for c in configs:
    print(f"Project: {c.project.project_name}, Action: '{c.action_type}', Roles: '{c.required_roles}'")
