import os
import django
from app.procurement_department.models import Quotation
from django.db.models import Sum

qs = Quotation.objects.all()
print("All quotations:")
for q in qs:
    print(f"ID: {q.id}, Project: {q.project.project_name}, Status: {q.status}, Quote Total: {q.quote_total}, Var Ref: '{q.variation_ref}'")
