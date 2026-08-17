import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.core.mail import send_mail

try:
    res = send_mail(
        "Anymail Test",
        "Testing anymail via brevo",
        "no-reply@payparo.tech",
        ["thatsariful@gmail.com"],
        fail_silently=False,
    )
    print(f"send_mail returned: {res}")
except Exception as e:
    print(f"Error: {e}")
