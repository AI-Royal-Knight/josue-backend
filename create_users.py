import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from app.account.models import UserAccount

users = [
    {"email": "contract.manager@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.CONTRACTS_MANAGER},
    {"email": "manager@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.MANAGERS},
    {"email": "supervisor@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.SUPERVISOR},
]

for u in users:
    user, created = UserAccount.objects.get_or_create(email=u["email"])
    user.set_password(u["password"])
    user.role = u["role"]
    user.save()
    action = "Created" if created else "Updated"
    print(f"{action} {u['email']} with role {u['role']}")
