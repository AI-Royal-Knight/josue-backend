import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.commercial_department.models import Variation
from app.commercial_department.serializers import VariationSerializer

try:
    variations = Variation.objects.all()
    serializer = VariationSerializer(variations, many=True)
    print(serializer.data)
except Exception as e:
    import traceback
    traceback.print_exc()
