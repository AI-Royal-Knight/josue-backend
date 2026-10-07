import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()
from django.template.loader import render_to_string
from app.super_admin.models import MonthlyInvoice
import io
from xhtml2pdf import pisa
from django.utils import timezone

from app.super_admin.services import InvoiceService

invoice = MonthlyInvoice.objects.first()
now = timezone.now()
company = invoice.company
admin_user = company.users.filter(role="admin").first()

breakdown = InvoiceService.calculate_monthly_invoice_breakdown(company)
monthly_sub = breakdown["monthly_sub"]
per_user = breakdown["per_user"]
users = breakdown["users_count"]
user_licenses_total = breakdown["user_licenses_total"]
total_amount = breakdown["total_amount"]

html_string = render_to_string("super_admin/invoice_pdf.html", {
    "company": company,
    "admin_user": admin_user,
    "invoice": invoice,
    "total_amount": total_amount,
    "monthly_sub": monthly_sub,
    "per_user": per_user,
    "users": users,
    "user_licenses_total": user_licenses_total,
    "date": now.strftime("%B %d, %Y"),
    "due_date": (now + timezone.timedelta(days=10)).strftime("%B %d, %Y"),
})
pdf_file = open('test.pdf', 'wb')

pisa_status = pisa.CreatePDF(io.StringIO(html_string), dest=pdf_file)
if pisa_status.err:
    print("Error generating PDF")
else:
    print("PDF generated successfully")
