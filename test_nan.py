import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.commercial_department.models import Variation
from app.account.models import UserAccount
import math

user = UserAccount.objects.first()
try:
    Variation.objects.create(
        project_id=user.company.company_projects.first().id,
        total_amount=float('nan')
    )
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
