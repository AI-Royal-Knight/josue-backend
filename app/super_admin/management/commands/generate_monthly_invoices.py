from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from app.account.models import Company
from app.super_admin.models import MonthlyInvoice
import uuid

class Command(BaseCommand):
    help = 'Automatically generate monthly invoices for companies with auto_monthly_inv=True'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        year = now.year
        month = now.month

        # Find companies with auto_monthly_inv=True and active status
        companies = Company.objects.filter(activate=True, auto_monthly_inv=True)

        count = 0
        for company in companies:
            # Calculate amount (monthly subscription + per_user_rate * users)
            monthly_sub = company.monthly_subscription or Decimal("0.00")
            per_user = company.per_user_rate or Decimal("0.00")
            users = company.user or 0

            # Guard: do not invoice for months before the company was created
            company_created = company.created_at
            if (year, month) < (company_created.year, company_created.month):
                self.stdout.write(self.style.WARNING(
                    f'Skipping {company.company_name}: invoice month {month}/{year} is before company creation {company_created.month}/{company_created.year}'
                ))
                continue

            total_amount = monthly_sub + (per_user * users)

            invoice_number = f"INV-{year}{month:02d}-{str(company.id)[:4].upper()}"

            # Create or get the invoice
            invoice, created = MonthlyInvoice.objects.get_or_create(
                company=company,
                year=year,
                month=month,
                defaults={
                    "amount": total_amount,
                    "is_sent": True,
                    "is_paid": False,
                    "invoice_number": invoice_number
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'Created invoice {invoice_number} for {company.company_name}'))
                count += 1
            else:
                self.stdout.write(self.style.WARNING(f'Invoice already exists for {company.company_name} for {month}/{year}'))

        self.stdout.write(self.style.SUCCESS(f'Successfully generated {count} invoices.'))
