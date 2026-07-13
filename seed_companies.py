import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from app.account.models import Company, UserAccount

companies_data = [
    {
        "company_name": "Acme Corp",
        "monthly_subscription": Decimal("500.00"),
        "per_user_rate": Decimal("25.00"),
        "auto_monthly_inv": False,
        "user": 10,
    },
    {
        "company_name": "Globex Inc",
        "monthly_subscription": Decimal("750.00"),
        "per_user_rate": Decimal("30.00"),
        "auto_monthly_inv": False,
        "user": 15,
    },
    {
        "company_name": "Soylent Corp",
        "monthly_subscription": Decimal("1000.00"),
        "per_user_rate": Decimal("20.00"),
        "auto_monthly_inv": False,
        "user": 50,
    },
    {
        "company_name": "Initech",
        "monthly_subscription": Decimal("250.00"),
        "per_user_rate": Decimal("15.00"),
        "auto_monthly_inv": False,
        "user": 5,
    },
    {
        "company_name": "Umbrella Corp",
        "monthly_subscription": Decimal("2000.00"),
        "per_user_rate": Decimal("50.00"),
        "auto_monthly_inv": False,
        "user": 100,
    }
]

def seed():
    for data in companies_data:
        company, created = Company.objects.get_or_create(
            company_name=data["company_name"],
            defaults={
                "status": Company.Status.ACTIVE,
                "activate": True,
                "monthly_subscription": data["monthly_subscription"],
                "per_user_rate": data["per_user_rate"],
                "auto_monthly_inv": data["auto_monthly_inv"],
                "user": data["user"]
            }
        )
        if created:
            print(f"Created company: {company.company_name}")
            
            # Create a mock admin user for the company so the API doesn't fail if it expects one
            UserAccount.objects.create_user(
                email=f"admin@{company.company_name.lower().replace(' ', '')}.com",
                first_name="Admin",
                last_name=company.company_name,
                role=UserAccount.Role.ADMIN,
                company=company,
                password="password123",
                is_active=True
            )
        else:
            print(f"Company {company.company_name} already exists. Updating...")
            company.status = Company.Status.ACTIVE
            company.activate = True
            company.monthly_subscription = data["monthly_subscription"]
            company.per_user_rate = data["per_user_rate"]
            company.auto_monthly_inv = data["auto_monthly_inv"]
            company.user = data["user"]
            company.save()
            print(f"Updated company: {company.company_name}")

if __name__ == "__main__":
    seed()
