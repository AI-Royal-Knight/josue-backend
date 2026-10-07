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
            # Calculate amount (monthly subscription + per_user_rate * registered users)
            from app.super_admin.services import InvoiceService
            breakdown = InvoiceService.calculate_monthly_invoice_breakdown(company)
            total_amount = breakdown["total_amount"]


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
