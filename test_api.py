import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from app.account.models import UserAccount

# Create a test client and force login
c = Client()
user = UserAccount.objects.get(email='ashiqulislamayon28@gmail.com')
c.force_login(user)

response = c.get('/api/v1/project-admin/users/?role=employee')
print("Status Code:", response.status_code)
print("Response JSON:", response.json())
