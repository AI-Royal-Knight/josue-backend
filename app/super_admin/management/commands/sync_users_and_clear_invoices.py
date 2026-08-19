from django.core.management.base import BaseCommand
from app.account.models import Company, UserAccount
from app.super_admin.models import MonthlyInvoice

class Command(BaseCommand):
    help = 'Sync actual user counts into Company models and delete old zero-amount invoices.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Starting sync process...'))
        
        # 1. Sync actual user counts for all companies
        companies = Company.objects.all()
        for company in companies:
            # Count users excluding SUPER_ADMIN
            actual_user_count = UserAccount.objects.filter(
                company=company
            ).exclude(
                role=UserAccount.Role.SUPER_ADMIN
            ).count()
            
            if company.user != actual_user_count:
                company.user = actual_user_count
                company.save(update_fields=['user'])
                self.stdout.write(f"Updated {company.company_name} - User count set to {actual_user_count}")

        # 2. Delete all existing monthly invoices
        # (This will wipe all existing invoices to give you a clean slate)
        deleted_count, _ = MonthlyInvoice.objects.all().delete()
        
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {deleted_count} old invoices.'))
        self.stdout.write(self.style.SUCCESS('Database synced successfully!'))
