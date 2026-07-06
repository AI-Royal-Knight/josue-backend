import os
import django
import json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from django.test import RequestFactory
from rest_framework.test import force_authenticate
from app.employee.views import DailyBriefingCreateView
from app.account.models import UserAccount

user = UserAccount.objects.first()
factory = RequestFactory()

request = factory.post('/api/v1/employee/operations/briefings/create/', {
    "project_id": str(user.company.company_projects.first().id),
    "title": "Daily briefing",
    "date": "2026-07-04"
    # No document provided
})
force_authenticate(request, user=user)

view = DailyBriefingCreateView.as_view()
try:
    response = view(request)
    print("Response status:", response.status_code)
    print("Response data:", response.data)
except Exception as e:
    import traceback
    traceback.print_exc()
