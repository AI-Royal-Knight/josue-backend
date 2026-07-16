import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.project_admin.models import LoadingClearingAccess, VariationsAccess, ProformaAccess

LoadingClearingAccess.objects.update(is_active=True)
VariationsAccess.objects.update(is_active=True)
ProformaAccess.objects.update(is_active=True)

print("Updated all accesses to is_active=True")
