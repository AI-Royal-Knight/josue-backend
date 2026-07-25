import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.account.models import UserAccount, Company

users = [
    {"email": "admin@gmail.com", "password": "admin", "role": UserAccount.Role.SUPER_ADMIN, "first_name": "Super", "last_name": "Admin"},
    {"email": "ashiqulislamayon28@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.ADMIN, "first_name": "Admin", "last_name": "User"},
    {"email": "libro.bangla@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.PROJECT_ADMIN, "first_name": "Project", "last_name": "Admin"},
    {"email": "midgeneration.com@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.MANAGING_DIRECTOR, "first_name": "Managing", "last_name": "Director"},
    {"email": "project.director@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.PROJECT_DIRECTOR, "first_name": "Project", "last_name": "Director"},
    {"email": "procurement@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.PROCUREMENT_DEPARTMENT, "first_name": "Procurement", "last_name": "Department"},
    {"email": "commercial.department@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.COMMERCIAL_DEPARTMENT, "first_name": "Commercial", "last_name": "Department"},
    {"email": "document.controller@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.DOCUMENT_CONTROLLER, "first_name": "Document", "last_name": "Controller"},
    {"email": "financial@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.FINANCE_DEPARTMENT, "first_name": "Finance", "last_name": "Department"},
    {"email": "contract.manager@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.CONTRACTS_MANAGER, "first_name": "Contract", "last_name": "Manager"},
    {"email": "manager@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.MANAGERS, "first_name": "Manager", "last_name": "User"},
    {"email": "supervisor@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.SUPERVISOR, "first_name": "Supervisor", "last_name": "User"},
    {"email": "soper17343@homephit.com", "password": "1fjw0676", "role": UserAccount.Role.EMPLOYEE, "first_name": "Employee", "last_name": "User"},
    {"email": "supplier@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.SUPPLIER, "first_name": "Supplier", "last_name": "User"},
    {"email": "technical.department@gmail.com", "password": "1fjw0676", "role": UserAccount.Role.TECHNICAL_DEPARTMENT, "first_name": "Technical", "last_name": "Department"},
]

# Create a mock company for these users so they are visible in the super admin dashboard
company, _ = Company.objects.get_or_create(
    company_name="Tresta Test Company",
    defaults={
        "status": Company.Status.ACTIVE,
        "activate": True,
        "phone": "+44 7700 900077"
    }
)

for u in users:
    # Ensure they have first and last names if creating
    user, created = UserAccount.objects.get_or_create(
        email=u["email"],
        defaults={
            "first_name": u["first_name"],
            "last_name": u["last_name"],
        }
    )
    user.set_password(u["password"])
    user.role = u["role"]
    
    # Super admins don't typically belong to a company
    if u["role"] == UserAccount.Role.SUPER_ADMIN:
        user.is_staff = True
        user.is_superuser = True
        user.company = None
    else:
        user.company = company
    
    user.save()
    action = "Created" if created else "Updated"
    print(f"{action} {u['email']} with role {u['role']}")
