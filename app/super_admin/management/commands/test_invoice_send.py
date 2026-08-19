from django.core.management.base import BaseCommand
from app.super_admin.tasks import generate_and_send_monthly_invoices

class Command(BaseCommand):
    help = 'Test invoice generation and sending by triggering the celery task synchronously'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company_id',
            type=int,
            help='ID of the company to test',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force send bypassing date check',
        )

    def handle(self, *args, **kwargs):
        company_id = kwargs['company_id']
        force = kwargs['force']

        self.stdout.write(self.style.WARNING('Starting invoice generation and send task...'))
        
        try:
            # We call the task synchronously to see the execution immediately
            generate_and_send_monthly_invoices(company_id=company_id, force=force)
            self.stdout.write(self.style.SUCCESS('Successfully completed invoice generation and send task.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error occurred: {str(e)}'))
