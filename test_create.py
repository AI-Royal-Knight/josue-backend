import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.procurement_department.models import Quotation
from app.project_admin.models import Project, CompanySupplier

project = Project.objects.first()
supplier = CompanySupplier.objects.first()

q = Quotation.objects.create(
    project=project,
    supplier=supplier,
    supplier_email="test@contact.com",
    quote_total=100
)
print("Created quote ID:", q.id, "Email:", q.supplier_email)
