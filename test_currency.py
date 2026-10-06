import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from app.project_admin.models import Project

print([(p.project_name, p.currency) for p in Project.objects.all()])
