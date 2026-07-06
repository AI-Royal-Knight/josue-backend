import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.commercial_department.models import Variation
from django.db.models import Sum, F

variations = Variation.objects.all()
var_agg = variations.aggregate(
    val=Sum('total_amount'),
    lab=Sum('lines__labour_target'),
    mat=Sum('lines__material')
)
print(var_agg)
