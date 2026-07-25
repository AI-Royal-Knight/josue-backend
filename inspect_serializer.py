import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from app.project_admin.models import ApprovalConfiguration
from app.project_admin.serializers import ApprovalConfigurationSerializer

configs = ApprovalConfiguration.objects.all()
data = ApprovalConfigurationSerializer(configs, many=True).data
for d in data:
    print(d)
