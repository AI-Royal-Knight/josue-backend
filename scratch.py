import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from app.account.models import UserAccount, UserProfile

try:
    user = UserAccount.objects.create(email="testdc@example.com", first_name="Test", last_name="DC")
    try:
        profile = user.profile
    except Exception as e:
        print(f"Exception type: {type(e)}")
        print(f"Exception: {e}")
except Exception as e:
    pass
