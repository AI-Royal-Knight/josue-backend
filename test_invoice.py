import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from app.project_admin.models import UserInvoice, Project
from app.account.models import UserAccount
project = Project.objects.first()
user = UserAccount.objects.first()
try:
    inv = UserInvoice.objects.create(
        project=project,
        created_by=user,
        source_type=UserInvoice.SourceType.LABOUR_TARGET,
        source_id="test",
        work_area="test",
        description="test",
        total=1.0,
        status=UserInvoice.Status.BUCKET,
    )
    print("Success:", inv.invoice_number)
except Exception as e:
    import traceback
    traceback.print_exc()
