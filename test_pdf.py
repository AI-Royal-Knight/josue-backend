import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()
from django.template.loader import render_to_string
from app.super_admin.models import MonthlyInvoice
import io
from xhtml2pdf import pisa
from django.utils import timezone

invoice = MonthlyInvoice.objects.first()
now = timezone.now()
company = invoice.company
monthly_sub = company.monthly_subscription
per_user = company.per_user_rate
users = 1

html_string = render_to_string("super_admin/invoice_pdf.html", {
    "company": company,
    "invoice": invoice,
    "subtotal": 100,
    "vat_amount": 20,
    "total_amount": 120,
    "monthly_sub": monthly_sub,
    "per_user": per_user,
    "users": users,
    "user_licenses_total": 50,
    "date": now.strftime("%B %d, %Y"),
    "due_date": now.strftime("%B %d, %Y"),
})
pdf_file = open('test.pdf', 'wb')
pisa_status = pisa.CreatePDF(io.StringIO(html_string), dest=pdf_file)
if pisa_status.err:
    print("Error generating PDF")
else:
    print("PDF generated successfully")
