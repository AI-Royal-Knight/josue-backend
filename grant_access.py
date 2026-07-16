import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.account.models import UserAccount
from app.project_admin.models import Project, LoadingClearingAccess, VariationsAccess, ProformaAccess

employees = UserAccount.objects.filter(role='employee')
projects = Project.objects.all()

for emp in employees:
    for proj in projects:
        LoadingClearingAccess.objects.get_or_create(project=proj, user=emp)
        VariationsAccess.objects.get_or_create(project=proj, user=emp)
        ProformaAccess.objects.get_or_create(project=proj, user=emp)

print("Granted access to all employees for all projects.")
