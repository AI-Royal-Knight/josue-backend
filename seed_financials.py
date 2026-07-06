import os
import django
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from app.project_admin.models import Project, LabourBooking, PlantHireBooking, LoadingClearingBooking, ManagementPrelimBooking
from app.procurement_department.models import PurchaseOrder, POCallOff
from app.commercial_department.models import Variation
from app.finance_department.models import ProformaNR
from app.account.models import UserAccount

def seed_financials():
    if not Project.objects.exists():
        print("No projects exist. Please create a project first.")
        return
        
    project = Project.objects.first()
    print(f"Seeding financials for project: {project.project_name}")
    
    user = UserAccount.objects.first()
    
    start_date = project.start_date or date.today() - relativedelta(months=3)
    project.start_date = start_date
    project.save()
    
    # 1. Purchase Orders
    po = PurchaseOrder.objects.create(project=project, total_value=50000)
    POCallOff.objects.create(po=po, amount=5000, date=start_date + timedelta(days=5), is_approved=True)
    POCallOff.objects.create(po=po, amount=3000, date=start_date + relativedelta(months=1, days=10), is_approved=True)
    
    # 2. Variations
    Variation.objects.create(
        project=project, 
        variation_value=10000, 
        labour_target=2000, 
        material_target=1000, 
        claimed_amount=8000,
        date_raised=start_date + timedelta(days=15)
    )
    
    # 3. Proforma NR
    ProformaNR.objects.create(
        project=project,
        amount=1500,
        material_estimate=500,
        date=start_date + relativedelta(months=1, days=5)
    )
    
    # 4. Bookings
    LabourBooking.objects.create(project=project, user=user, amount=4000, date=start_date + timedelta(days=20), is_approved=True)
    PlantHireBooking.objects.create(project=project, amount=1200, date=start_date + timedelta(days=10), is_approved=True)
    LoadingClearingBooking.objects.create(project=project, amount=800, date=start_date + relativedelta(months=1, days=2), is_approved=True)
    ManagementPrelimBooking.objects.create(project=project, amount=2000, date=start_date + timedelta(days=1), is_approved=True)

    print("Seed complete! You can now test the API endpoint.")
    
if __name__ == "__main__":
    seed_financials()
