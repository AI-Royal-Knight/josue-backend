import os
import django
import json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.commercial_department.models import Variation
print("Variation objects:", Variation.objects.count())

from app.commercial_department.views import VariationListCreateView
from django.test import RequestFactory
from rest_framework.test import force_authenticate
from app.account.models import UserAccount

user = UserAccount.objects.first()
factory = RequestFactory()

request = factory.post('/api/v1/commercial/variations/', {
    "project_id": str(user.company.company_projects.first().id),
    "site_instruction_no": "TEST-123-NULL",
    "attention_of": "Bob",
    "description_of_works": "Test Works with null",
    "comments": "Test comments",
    "lines": [{
        "siteInstruction": "",
        "workArea": "",
        "workSection": "",
        "labour": "abc",  # What if it's not convertable?
        "labourTarget": 0,
        "material": 0,
        "qty": 1
    }]
}, content_type='application/json')
force_authenticate(request, user=user)

try:
    response = VariationListCreateView.as_view()(request)
    print("Status:", response.status_code)
except Exception as e:
    import traceback
    traceback.print_exc()

