import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.commercial_department.models import Variation
from app.account.models import UserAccount
from app.commercial_department.serializers import VariationSerializer

try:
    user = UserAccount.objects.first()
    print("User company:", user.company)
    variations = Variation.objects.filter(
        project__company=user.company
    ).select_related("project", "created_by", "approved_by").prefetch_related("lines")
    serializer = VariationSerializer(variations, many=True)
    print(serializer.data)
except Exception as e:
    import traceback
    traceback.print_exc()
