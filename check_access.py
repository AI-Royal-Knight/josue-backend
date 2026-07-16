import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.project_admin.models import LoadingClearingAccess
from app.account.models import UserAccount

users = UserAccount.objects.filter(role='employee')
print(f"Employees found: {users.count()}")

accesses = LoadingClearingAccess.objects.all()
print(f"LoadingClearingAccess records found: {accesses.count()}")
for l in accesses:
    print(f"User: {l.user.email}, Project: {l.project.project_name}, Active: {l.is_active}")
