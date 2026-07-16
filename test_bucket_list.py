import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from rest_framework.test import APIClient
from app.account.models import UserAccount
user = UserAccount.objects.filter(role='employee').first()
client = APIClient()
client.force_authenticate(user=user)
response = client.get("/api/v1/project-admin/bucket/")
print("Response status:", response.status_code)
print("Response data:", response.data)
