import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from django.test import RequestFactory
from rest_framework.test import force_authenticate
from app.commercial_department.views import VariationListCreateView
from app.account.models import UserAccount

user = UserAccount.objects.first()
factory = RequestFactory()

request = factory.post('/api/v1/commercial/variations/', {
    "project_id": str(user.company.company_projects.first().id),
    "site_instruction_no": "TEST-123",
    "attention_of": "Bob",
    "description_of_works": "Test Works",
    "comments": "Test comments",
    "lines": []
}, content_type='application/json')
force_authenticate(request, user=user)

view = VariationListCreateView.as_view()
try:
    response = view(request)
    print("Response status:", response.status_code)
    print("Response data:", response.data)
except Exception as e:
    import traceback
    traceback.print_exc()
