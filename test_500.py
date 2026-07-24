import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from app.commercial_department.views import MonthlyApplicationListCreateView
from django.test import RequestFactory
from app.account.models import UserAccount

factory = RequestFactory()
request = factory.get('/?project_id=60bd25ad-d54b-4886-af33-8557b77ab684') # just any string or UUID

# let's just pick the first project in db for the test
from app.project_admin.models import Project
project = Project.objects.first()
if project:
    request = factory.get(f'/?project_id={project.id}')

request.user = UserAccount.objects.first()

view = MonthlyApplicationListCreateView()
try:
    response = view.get(request)
    print(response.data)
except Exception as e:
    import traceback
    traceback.print_exc()

