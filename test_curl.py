import os
import django
import json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.account.models import UserAccount
from rest_framework_simplejwt.tokens import RefreshToken

user = UserAccount.objects.first()
refresh = RefreshToken.for_user(user)
access_token = str(refresh.access_token)

import urllib.request
import urllib.error

url = "http://localhost:8000/api/v1/commercial/variations/"

# Need to send JSON body with nulls
data = {
    "project_id": str(user.company.company_projects.first().id),
    "site_instruction_no": "TEST-123-NULL",
    "attention_of": "Bob",
    "description_of_works": "Test Works with null",
    "comments": "Test comments",
    "lines": [{
        "siteInstruction": "",
        "workArea": "",
        "workSection": "",
        "labour": None,
        "labourTarget": None,
        "material": None,
        "qty": None
    }]
}

req = urllib.request.Request(
    url, 
    data=json.dumps(data).encode('utf-8'),
    headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(req) as response:
        print("Status:", response.status)
        print("Body:", response.read().decode())
except urllib.error.HTTPError as e:
    print("Status:", e.code)
    print(e.read().decode())

