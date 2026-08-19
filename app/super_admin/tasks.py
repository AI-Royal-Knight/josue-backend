from celery import shared_task
from django.utils import timezone
from decimal import Decimal
import calendar
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from xhtml2pdf import pisa
import io

from app.account.models import Company
from app.super_admin.models import MonthlyInvoice

def get_last_day_of_month(year, month):
    return calendar.monthrange(year, month)[1]

@shared_task
def generate_and_send_monthly_invoices(company_id=None, force=False, target_year=None, target_month=None):
    now = timezone.now()
    year = target_year if target_year else now.year
    month = target_month if target_month else now.month
    today_day = now.day

    last_day = get_last_day_of_month(year, month)

    if company_id:
        companies = Company.objects.filter(id=company_id)
    else:
        companies = Company.objects.filter(activate=True, auto_monthly_inv=True)

    for company in companies:
        target_date = company.auto_monthly_inv_date or 1

        # If target date is greater than the last day of this month, we execute on the last day
        if target_date > last_day:
            target_date = last_day

        if force or target_date == today_day:
            # Guard: do not invoice for months before the company was created
            company_created = company.created_at
            if (year, month) < (company_created.year, company_created.month):
                continue

            # Generate invoice
            monthly_sub = company.monthly_subscription or Decimal("0.00")
            per_user = company.per_user_rate or Decimal("0.00")
            users = company.user or 0

            total_amount = monthly_sub + (per_user * users)
            invoice_number = f"INV-{year}{month:02d}-{str(company.id)[:4].upper()}"

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
                # Generate PDF
                html_string = render_to_string("super_admin/invoice_pdf.html", {
                    "company": company,
                    "invoice": invoice,
                    "total_amount": total_amount,
                    "monthly_sub": monthly_sub,
                    "per_user": per_user,
                    "users": users,
                    "user_licenses_total": per_user * users,
                    "date": now.strftime("%B %d, %Y"),
                })
                
                pdf_file = io.BytesIO()
                pisa_status = pisa.CreatePDF(
                    io.StringIO(html_string), dest=pdf_file
                )

                if not pisa_status.err:
                    file_name = f"invoice_{invoice_number}.pdf"
                    
                    try:
                        import cloudinary.uploader
                        upload_result = cloudinary.uploader.upload(
                            pdf_file.getvalue(),
                            resource_type='auto',
                            public_id=f"invoice_{invoice_number}",
                            folder="josue_invoices"
                        )
                        invoice.pdf_file = upload_result.get('secure_url')
                        invoice.save()
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Failed to upload invoice to Cloudinary: {e}")

                    # Send Email
                    # Get the admin or first user of the company to send the invoice to
                    admin_user = company.users.filter(role="admin").first()
                    recipient = admin_user.email if admin_user else None
                    
                    if not recipient:
                        # Fallback to any user in the company
                        any_user = company.users.first()
                        recipient = any_user.email if any_user else None

                    if recipient:
                        email_html = render_to_string("super_admin/invoice_email.html", {
                            "company": company,
                            "month_name": now.strftime("%B"),
                            "year": year
                        })
                        
                        email = EmailMessage(
                            subject=f"Your Monthly Invoice - {now.strftime('%B %Y')}",
                            body=email_html,
                            from_email=None,
                            to=[recipient],
                        )
                        email.content_subtype = "html"
                        email.attach(file_name, pdf_file.getvalue(), 'application/pdf')
                        email.send(fail_silently=True)
