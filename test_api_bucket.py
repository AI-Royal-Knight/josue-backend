import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from rest_framework.test import APIClient
from app.account.models import UserAccount
from app.project_admin.models import FolderAssignment
user = UserAccount.objects.filter(role='employee').first()
assignment = FolderAssignment.objects.filter(user=user).first()
if not assignment:
    print("No assignment found for employee")
else:
    assignment.hide_labour_target = True
    assignment.save()
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(f"/api/v1/employee/labour-target/submit/{assignment.id}/", {"employee_labour_value": 100})
    print("Response status:", response.status_code)
    print("Response data:", response.data)
