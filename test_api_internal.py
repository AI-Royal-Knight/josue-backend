import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from app.account.models import UserAccount

u = UserAccount.objects.get(email="contract.manager@gmail.com")
c = Client()
c.force_login(u)

response = c.get('/api/v1/contracts-manager/projects/')
print("Status:", response.status_code)
print("Response:", response.json())
