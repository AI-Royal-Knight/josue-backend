import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from app.employee.models import RFI
from app.employee.serializers import DashboardRFISerializer
try:
    rfi = RFI.objects.first()
    if rfi:
        serializer = DashboardRFISerializer(rfi)
        print(serializer.data)
    else:
        print("No RFI found")
except Exception as e:
    import traceback
    traceback.print_exc()
