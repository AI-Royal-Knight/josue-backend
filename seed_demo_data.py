"""
Seed Comprehensive Demo Data for Tresta Construction Management System.

This script populates realistic, end-to-end connected test data for all 15 roles
and all modules across the application, allowing thorough testing of:
- Super Admin (Company oversight, subscriptions, invoices, activity)
- Admin & Project Admin (Project management, WBS folders/subfolders, role assignments, approvals)
- Commercial Department (Variations, line items, multi-stage approvals, monthly applications, white card)
- Procurement Department (RFQs, quotations, multi-role signatures, call-offs, PO generation)
- Finance Department (Supplier invoices, user invoices payment, proforma NR)
- Contracts Manager & Department Heads (Project oversight, approval workflows, subfolders)
- Employees (Attendance, check-in, task submissions, bucket list, operations, RFIs)
- Suppliers (Supplier portal, quotation pricing, call-offs, supplier invoices)
- Technical Department (RFI query resolution, drawings, specifications)

Usage:
    python backend/seed_demo_data.py
    python manage.py seed_demo_data
    make seed
"""

import os
import sys
import uuid
import random
from decimal import Decimal
from datetime import date, timedelta
from pathlib import Path

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import environ
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

current_env = env('ENVIRONMENT', default='dev')
if current_env == 'prod':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

import django
django.setup()

from django.utils import timezone
from django.db import transaction

# Model Imports
from app.account.models import (
    Company, UserAccount, UserProfile, SupplierProfile,
    CompanySupplier, RoleAssignment, Invitation, Notification
)
from app.super_admin.models import MonthlyInvoice, RecentActivity, CompanyInvitation
from app.project_admin.models import (
    Project, ProjectFolder, ProjectSubfolder, FolderAssignment,
    ApprovalConfiguration, LabourBooking, ProjectValueBooking,
    PlantHireBooking, LoadingClearingBooking, ManagementPrelimBooking,
    ProformaAccess, LoadingClearingAccess, VariationsAccess, UserInvoice
)
from app.commercial_department.models import Variation, VariationLine, MonthlyApplication
from app.procurement_department.models import (
    PurchaseOrder, POCallOff, Quotation, QuotationLineItem,
    QuotationHistory, OrderLineCallOff
)
from app.finance_department.models import ProformaNR
from app.supplier.models import SupplierInvitation, SupplierInvoice
from app.employee.models import (
    AttendanceLog, RFI, RFIMessage, RAMS, DailyBriefing,
    ToolboxTalk, ToDoList
)

# Demo User Definitions
DEMO_PASSWORD_STANDARD = "1fjw0676"
DEMO_PASSWORD_ADMIN = "admin"

USER_CONFIGS = [
    {
        "email": "admin@gmail.com",
        "password": DEMO_PASSWORD_ADMIN,
        "role": UserAccount.Role.SUPER_ADMIN,
        "first_name": "Super",
        "last_name": "Admin",
        "description": "Full platform administration, company management & billing",
    },
    {
        "email": "ashiqulislamayon28@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.ADMIN,
        "first_name": "Alexander",
        "last_name": "Admin",
        "description": "Company administration, executive dashboard & project setup",
    },
    {
        "email": "libro.bangla@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.PROJECT_ADMIN,
        "first_name": "Peter",
        "last_name": "ProjectAdmin",
        "description": "WBS management, folder assignments, approval chains & financial tracking",
    },
    {
        "email": "midgeneration.com@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.MANAGING_DIRECTOR,
        "first_name": "Michael",
        "last_name": "Director",
        "description": "Final executive sign-offs for high-value variations and invoices",
    },
    {
        "email": "project.director@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.PROJECT_DIRECTOR,
        "first_name": "David",
        "last_name": "Director",
        "description": "Senior project governance, high-level approvals & operations oversight",
    },
    {
        "email": "procurement@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.PROCUREMENT_DEPARTMENT,
        "first_name": "Patricia",
        "last_name": "Procurement",
        "description": "Supplier invites, RFQs, purchase orders & call-off management",
    },
    {
        "email": "commercial.department@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.COMMERCIAL_DEPARTMENT,
        "first_name": "Charles",
        "last_name": "Commercial",
        "description": "Client variations, monthly applications, valuations & white card",
    },
    {
        "email": "document.controller@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.DOCUMENT_CONTROLLER,
        "first_name": "Donna",
        "last_name": "Controller",
        "description": "Employee onboarding, certification reviews & document management",
    },
    {
        "email": "financial@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.FINANCE_DEPARTMENT,
        "first_name": "Fiona",
        "last_name": "Finance",
        "description": "Invoice payouts, BACS scheduling & Proforma NR audits",
    },
    {
        "email": "contract.manager@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.CONTRACTS_MANAGER,
        "first_name": "Connor",
        "last_name": "Contracts",
        "description": "Contract administration, subfolder target reviews & approvals",
    },
    {
        "email": "manager@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.MANAGERS,
        "first_name": "Marcus",
        "last_name": "Manager",
        "description": "Site operations, daily briefings, RAMS & task management",
    },
    {
        "email": "supervisor@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.SUPERVISOR,
        "first_name": "Sam",
        "last_name": "Supervisor",
        "description": "First-line review of employee daily tasks, variations & check-ins",
    },
    {
        "email": "soper17343@homephit.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.EMPLOYEE,
        "first_name": "Edward",
        "last_name": "Employee",
        "description": "Mobile app user: live clock-in, task claims, bucket list, RAMS, RFIs",
    },
    {
        "email": "supplier@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.SUPPLIER,
        "first_name": "Stanley",
        "last_name": "Supplier",
        "description": "Supplier portal: quotation pricing, call-offs & invoice submissions",
    },
    {
        "email": "technical.department@gmail.com",
        "password": DEMO_PASSWORD_STANDARD,
        "role": UserAccount.Role.TECHNICAL_DEPARTMENT,
        "first_name": "Thomas",
        "last_name": "Technical",
        "description": "RFI reviews, technical clash resolution & BIM drawings",
    },
]


def print_step(title):
    print(f"\n[+] {title}...")


def seed_demo_data(reset=False):
    """Seed comprehensive, interconnected demo data across all modules."""
    print("=" * 80)
    print(" TRESTA CONSTRUCTION MANAGEMENT PLATFORM - DEMO DATA SEEDER")
    print("=" * 80)

    with transaction.atomic():
        # -------------------------------------------------------------
        # 1. Companies
        # -------------------------------------------------------------
        print_step("1. Seeding Companies")
        primary_company, _ = Company.objects.get_or_create(
            company_name="Tresta Test Company",
            defaults={
                "status": Company.Status.ACTIVE,
                "activate": True,
                "company_number": 12894510,
                "building_number": 100,
                "street": "Bishopsgate",
                "town": "City of London",
                "city": "London",
                "postcode": "EC2N 4AG",
                "vat_number": "GB 849 2011 45",
                "phone": "+44 20 7946 0912",
                "utr": "4819204918",
                "public_liability_policy": "PL-2026-UK-9921",
                "public_liability_expiry": date.today() + timedelta(days=365),
                "employers_liability_policy": "EL-2026-UK-4412",
                "employers_liability_expiry": date.today() + timedelta(days=365),
                "bank_name": "Barclays Commercial Bank",
                "bank_address": "1 Churchill Place, London E14 5HP",
                "sort_code": "20-00-00",
                "account_number": "83749201",
                "iban": "GB82BARC20000083749201",
                "swift_bic": "BARCGB22",
                "monthly_subscription": Decimal("1200.00"),
                "per_user_rate": Decimal("35.00"),
                "auto_monthly_inv": True,
                "auto_monthly_inv_date": 1,
            }
        )
        primary_company.status = Company.Status.ACTIVE
        primary_company.activate = True
        primary_company.monthly_subscription = Decimal("1200.00")
        primary_company.per_user_rate = Decimal("35.00")
        primary_company.auto_monthly_inv = True
        primary_company.auto_monthly_inv_date = 1
        primary_company.save()

        # Additional companies for Super Admin dashboard testing
        Company.objects.get_or_create(
            company_name="Acme Infrastructure Ltd",
            defaults={
                "status": Company.Status.ACTIVE,
                "activate": True,
                "city": "Manchester",
                "monthly_subscription": Decimal("850.00"),
                "per_user_rate": Decimal("30.00"),
                "user": 18,
                "projects": 3,
            }
        )
        Company.objects.get_or_create(
            company_name="Apex Prime Developments",
            defaults={
                "status": Company.Status.SUSPENDED,
                "activate": False,
                "city": "Birmingham",
                "monthly_subscription": Decimal("1500.00"),
                "per_user_rate": Decimal("40.00"),
                "user": 25,
                "projects": 4,
            }
        )
        print("    -> 3 companies active/suspended in database.")

        # -------------------------------------------------------------
        # 2. Users and Profiles
        # -------------------------------------------------------------
        print_step("2. Seeding Users and Role Profiles")
        users_by_role = {}
        for u in USER_CONFIGS:
            user, created = UserAccount.objects.get_or_create(
                email=u["email"],
                defaults={
                    "first_name": u["first_name"],
                    "last_name": u["last_name"],
                }
            )
            user.first_name = u["first_name"]
            user.last_name = u["last_name"]
            user.role = u["role"]
            user.set_password(u["password"])
            user.is_active = True

            if u["role"] == UserAccount.Role.SUPER_ADMIN:
                user.is_staff = True
                user.is_superuser = True
                user.company = None
            else:
                user.company = primary_company

            user.save()
            users_by_role[u["role"]] = user

        # Seed comprehensive UserProfile for Employee
        emp_user = users_by_role[UserAccount.Role.EMPLOYEE]
        UserProfile.objects.update_or_create(
            user=emp_user,
            defaults={
                "employee_id": "EMP-2026-088",
                "cscs_card_no": "CSCS-9847291",
                "cscs_expiry_date": date.today() + timedelta(days=500),
                "ipaf_certification": "IPAF 3a/3b Mobile Boom & Scissor",
                "pasma_certification": "PASMA Towers for Users Standard",
                "sssts_smsts": "SSSTS Site Supervisor Safety Training",
                "profession": "Lead Installation Electrician",
                "emergency_contact_name": "Sarah Jenkins",
                "emergency_contact_number": "+44 7700 900456",
                "ni_number": "QQ 12 34 56 A",
                "utr": "8920192837",
                "passport_number": "GBR582910482",
                "passport_expiry_date": date.today() + timedelta(days=1200),
                "bank_name": "HSBC UK Bank",
                "bank_address": "8 Canada Square, London E14 5HQ",
                "sort_code": "40-02-17",
                "account_number": "71625344",
                "iban": "GB29HBUK40021771625344",
                "swift_bic": "HBUKGB4B",
                "is_approved": True,
                "approved_by": users_by_role[UserAccount.Role.DOCUMENT_CONTROLLER],
                "categories": "Commercial Electrical, High Voltage Containment, Sub-Mains",
                "terms_accepted": True,
                "digital_signature": "Edward Employee (Verified)",
            }
        )

        # Seed SupplierProfile and CompanySupplier relationship
        supp_user = users_by_role[UserAccount.Role.SUPPLIER]
        supp_profile, _ = SupplierProfile.objects.update_or_create(
            user=supp_user,
            defaults={
                "company_name": "BuildMax Building Supplies Ltd",
                "sort_code": "40-05-15",
                "account_number": "91827364",
            }
        )
        company_supplier, _ = CompanySupplier.objects.update_or_create(
            company=primary_company,
            supplier=supp_profile,
            defaults={
                "status": CompanySupplier.Status.ACTIVE,
                "eom_payment_terms": 30,
                "credit_limit": Decimal("100000.00"),
                "invited_by": users_by_role[UserAccount.Role.PROCUREMENT_DEPARTMENT],
                "invited_at": timezone.now() - timedelta(days=90),
                "accepted_at": timezone.now() - timedelta(days=85),
                "notes": "Primary supplier for electrical switchgear, cable trays, containment, and cables.",
            }
        )
        print("    -> 15 role users, profiles & supplier relationships configured.")

        # -------------------------------------------------------------
        # 3. Projects
        # -------------------------------------------------------------
        print_step("3. Seeding Construction Projects")
        project_shard, _ = Project.objects.update_or_create(
            company=primary_company,
            job_code="JOB-2026-001",
            defaults={
                "project_name": "The Shard - Commercial Fit-Out",
                "vat_rate": "20%",
                "address": "32 London Bridge St, London SE1 9SG",
                "project_value": Decimal("1850000.00"),
                "material_estimate": Decimal("450000.00"),
                "labour_estimate": Decimal("620000.00"),
                "prelims_estimate": Decimal("180000.00"),
                "start_date": date.today() - timedelta(days=120),
                "completion_date": date.today() + timedelta(days=240),
                "monthly_application_date": 15,
                "is_completed": False,
            }
        )

        project_canary, _ = Project.objects.update_or_create(
            company=primary_company,
            job_code="JOB-2026-002",
            defaults={
                "project_name": "Canary Wharf Substation Upgrade",
                "vat_rate": "20%",
                "address": "1 Canada Square, Canary Wharf, London E14 5AA",
                "project_value": Decimal("920000.00"),
                "material_estimate": Decimal("310000.00"),
                "labour_estimate": Decimal("280000.00"),
                "prelims_estimate": Decimal("75000.00"),
                "start_date": date.today() - timedelta(days=60),
                "completion_date": date.today() + timedelta(days=120),
                "monthly_application_date": 1,
                "is_completed": False,
            }
        )

        project_battersea, _ = Project.objects.update_or_create(
            company=primary_company,
            job_code="JOB-2026-003",
            defaults={
                "project_name": "Battersea Power Station Lofts",
                "vat_rate": "20%",
                "address": "Circus Rd W, Nine Elms, London SW11 8AL",
                "project_value": Decimal("2400000.00"),
                "material_estimate": Decimal("650000.00"),
                "labour_estimate": Decimal("780000.00"),
                "prelims_estimate": Decimal("220000.00"),
                "start_date": date.today() - timedelta(days=365),
                "completion_date": date.today() - timedelta(days=30),
                "monthly_application_date": 20,
                "is_completed": True,
            }
        )
        projects = [project_shard, project_canary, project_battersea]

        # Assign all project users and role assignments
        for project in projects:
            for role_name, user in users_by_role.items():
                if role_name == UserAccount.Role.SUPER_ADMIN:
                    continue
                user.assigned_projects.add(project)
                RoleAssignment.objects.get_or_create(
                    user=user,
                    role=user.role,
                    company=primary_company,
                    project=project,
                )

        # Update cached statistics on company
        primary_company.user = primary_company.users.count()
        primary_company.projects = primary_company.company_projects.count()
        primary_company.save(update_fields=['user', 'projects'])
        print(f"    -> 3 projects created (2 active, 1 completed) and linked to all company users.")

        # -------------------------------------------------------------
        # 4. Folders, Subfolders, Datagrid Tasks & Assignments
        # -------------------------------------------------------------
        print_step("4. Seeding Work Breakdown Structure (Folders, Subfolders & Tasks)")
        # Main Folders
        folder_elec, _ = ProjectFolder.objects.get_or_create(
            project=project_shard,
            name="Electrical & MEP Services",
            defaults={"is_management": False}
        )
        folder_part, _ = ProjectFolder.objects.get_or_create(
            project=project_shard,
            name="Partitions & Suspended Ceilings",
            defaults={"is_management": False}
        )
        folder_prelims, _ = ProjectFolder.objects.get_or_create(
            project=project_shard,
            name="Management Prelims",
            defaults={"is_management": True}
        )

        # Subfolders with Datagrid Rows
        subfolder_l14, _ = ProjectSubfolder.objects.update_or_create(
            folder=folder_elec,
            name="Level 14 Open Office Grid",
            defaults={
                "project_value": Decimal("145000.00"),
                "labour_target": Decimal("52000.00"),
                "rows": [
                    {
                        "workSection": "First Fix Containment & Cable Trays",
                        "workArea": "Core A & B",
                        "labourTarget": 12000.00,
                        "projectValue": 28000.00,
                    },
                    {
                        "workSection": "Sub-Main Cabling & Distribution Boards",
                        "workArea": "Electrical Cupboard 14.1",
                        "labourTarget": 14000.00,
                        "projectValue": 35000.00,
                    },
                    {
                        "workSection": "Second Fix Lighting & Power Outlets",
                        "workArea": "North & East Wings",
                        "labourTarget": 16000.00,
                        "projectValue": 48000.00,
                    },
                    {
                        "workSection": "Emergency Lighting & Commissioning",
                        "workArea": "Escape Routes & Risers",
                        "labourTarget": 10000.00,
                        "projectValue": 34000.00,
                    },
                ]
            }
        )

        subfolder_l15, _ = ProjectSubfolder.objects.update_or_create(
            folder=folder_elec,
            name="Level 15 Executive Suites",
            defaults={
                "project_value": Decimal("98000.00"),
                "labour_target": Decimal("36000.00"),
                "rows": [
                    {
                        "workSection": "Feature Architectural Lighting",
                        "workArea": "Boardroom Suite",
                        "labourTarget": 18000.00,
                        "projectValue": 45000.00,
                    },
                    {
                        "workSection": "Smart Automation Controls",
                        "workArea": "Meeting Pods",
                        "labourTarget": 18000.00,
                        "projectValue": 53000.00,
                    },
                ]
            }
        )

        subfolder_part_l14, _ = ProjectSubfolder.objects.update_or_create(
            folder=folder_part,
            name="Acoustic Glazed Partitions",
            defaults={
                "project_value": Decimal("120000.00"),
                "labour_target": Decimal("42000.00"),
                "rows": [
                    {
                        "workSection": "Acoustic Partition Framing",
                        "workArea": "Offices 1-8",
                        "labourTarget": 22000.00,
                        "projectValue": 65000.00,
                    },
                    {
                        "workSection": "Double Glazed Infill & Ironmongery",
                        "workArea": "Offices 1-8",
                        "labourTarget": 20000.00,
                        "projectValue": 55000.00,
                    },
                ]
            }
        )

        subfolder_mgmt, _ = ProjectSubfolder.objects.update_or_create(
            folder=folder_prelims,
            name="Site Logistics & Supervision",
            defaults={
                "project_value": Decimal("65000.00"),
                "labour_target": Decimal("25000.00"),
                "rows": [
                    {
                        "workSection": "Site Supervision & Safety Audits",
                        "workArea": "Whole Site",
                        "labourTarget": 15000.00,
                        "projectValue": 40000.00,
                    },
                    {
                        "workSection": "Waste Management & Storage Logistics",
                        "workArea": "Loading Bay",
                        "labourTarget": 10000.00,
                        "projectValue": 25000.00,
                    },
                ]
            }
        )

        # Folder Assignments for Employee
        assignment_l14, _ = FolderAssignment.objects.update_or_create(
            subfolder=subfolder_l14,
            user=emp_user,
            defaults={
                "hide_labour_target": False,
                "is_management_assignment": False,
                "employee_labour_value": Decimal("52000.00"),
            }
        )
        assignment_l15, _ = FolderAssignment.objects.update_or_create(
            subfolder=subfolder_l15,
            user=emp_user,
            defaults={
                "hide_labour_target": True,
                "is_management_assignment": False,
                "employee_labour_value": Decimal("35000.00"),
            }
        )
        assignment_part, _ = FolderAssignment.objects.update_or_create(
            subfolder=subfolder_part_l14,
            user=emp_user,
            defaults={
                "hide_labour_target": False,
                "is_management_assignment": False,
            }
        )
        assignment_mgmt, _ = FolderAssignment.objects.update_or_create(
            subfolder=subfolder_mgmt,
            user=emp_user,
            defaults={
                "hide_labour_target": False,
                "is_management_assignment": True,
            }
        )
        print("    -> WBS folders, datagrids and employee assignments established.")

        # -------------------------------------------------------------
        # 5. Approval Configurations
        # -------------------------------------------------------------
        print_step("5. Seeding Project Approval Configurations")
        approval_types = [
            (ApprovalConfiguration.ActionType.USER_INVOICE, "supervisor,manager,contracts_manager,project_director,managing_director", {
                "supervisor": 0, "manager": 500, "contracts_manager": 2000, "project_director": 5000, "managing_director": 10000
            }),
            (ApprovalConfiguration.ActionType.SUPPLIER_INVOICE, "procurement_department,finance_department,managing_director", {
                "procurement_department": 0, "finance_department": 1000, "managing_director": 5000
            }),
            (ApprovalConfiguration.ActionType.VARIATIONS, "supervisor,manager,contracts_manager,project_director,managing_director,commercial_department", {
                "supervisor": 0, "manager": 1000, "contracts_manager": 5000, "project_director": 10000, "managing_director": 20000
            }),
            (ApprovalConfiguration.ActionType.PURCHASE_ORDER, "procurement_department,contracts_manager,project_director,managing_director,commercial_department", {
                "procurement_department": 0, "contracts_manager": 2000, "project_director": 10000, "managing_director": 25000
            }),
            (ApprovalConfiguration.ActionType.PROFORMA, "supervisor,contracts_manager,finance_department", {
                "supervisor": 0, "contracts_manager": 1500, "finance_department": 3000
            }),
            (ApprovalConfiguration.ActionType.USER_VARIATIONS_INVOICE, "supervisor,manager,contracts_manager", {
                "supervisor": 0, "manager": 1000, "contracts_manager": 5000
            }),
            (ApprovalConfiguration.ActionType.USER_CLOCK_IN, "supervisor", {
                "supervisor": 0
            }),
        ]

        for proj in [project_shard, project_canary]:
            for action_type, req_roles, thresholds in approval_types:
                ApprovalConfiguration.objects.update_or_create(
                    project=proj,
                    action_type=action_type,
                    defaults={
                        "condition_value": "ALL",
                        "required_roles": req_roles,
                        "role_thresholds": thresholds,
                        "toggle_states": [{"role": r, "enabled": True} for r in req_roles.split(',')],
                        "is_active": True,
                    }
                )
        print("    -> Approval workflows configured for all action types.")

        # -------------------------------------------------------------
        # 6. Feature Access Grants
        # -------------------------------------------------------------
        print_step("6. Seeding Feature Access Grants")
        for proj in [project_shard, project_canary]:
            ProformaAccess.objects.get_or_create(project=proj, user=emp_user, defaults={"is_active": True})
            LoadingClearingAccess.objects.get_or_create(project=proj, user=emp_user, defaults={"is_active": True})
            VariationsAccess.objects.get_or_create(project=proj, user=emp_user, defaults={"is_active": True})
        print("    -> Proforma, Loading & Clearing, and Variations access granted to employee.")

        # -------------------------------------------------------------
        # 7. Procurement (POs, Quotations, Line Items & Call-Offs)
        # -------------------------------------------------------------
        print_step("7. Seeding Procurement & Purchase Orders")
        po_shard, _ = PurchaseOrder.objects.get_or_create(
            project=project_shard,
            total_value=Decimal("120000.00"),
        )
        POCallOff.objects.get_or_create(
            po=po_shard,
            amount=Decimal("15000.00"),
            date=date.today() - timedelta(days=60),
            defaults={"is_approved": True}
        )
        POCallOff.objects.get_or_create(
            po=po_shard,
            amount=Decimal("22000.00"),
            date=date.today() - timedelta(days=30),
            defaults={"is_approved": True}
        )

        # Quotation 1: Fully approved PO with active call-offs
        quote_1, _ = Quotation.objects.update_or_create(
            quote_ref="QR-2026-001",
            defaults={
                "project": project_shard,
                "main_folder": folder_elec,
                "sub_folder": subfolder_l14,
                "supplier": company_supplier,
                "supplier_email": "supplier@gmail.com",
                "quote_total": Decimal("34500.00"),
                "status": Quotation.Status.APPROVED,
                "po_created": True,
                "date_po_created": date.today() - timedelta(days=45),
                "sig_procurement_department": True,
                "sig_procurement_department_date": date.today() - timedelta(days=50),
                "sig_contracts_manager": True,
                "sig_contracts_manager_date": date.today() - timedelta(days=48),
                "sig_project_director": True,
                "sig_project_director_date": date.today() - timedelta(days=47),
                "sig_managing_director": True,
                "sig_managing_director_date": date.today() - timedelta(days=46),
                "sig_commercial_department": True,
                "sig_commercial_department_date": date.today() - timedelta(days=45),
                "fully_approved": True,
                "paid": True,
                "paid_by": users_by_role[UserAccount.Role.FINANCE_DEPARTMENT],
                "created_by": users_by_role[UserAccount.Role.PROCUREMENT_DEPARTMENT],
            }
        )

        item_1, _ = QuotationLineItem.objects.update_or_create(
            quotation=quote_1,
            description="Distribution Board 12-Way 3-Phase 400A TP&N",
            defaults={
                "qty": Decimal("4.00"),
                "discount": Decimal("5.00"),
                "per": "Nr",
                "each": Decimal("1250.00"),
                "supplier_price": Decimal("1250.00"),
                "management_approved": True,
                "management_approved_date": date.today() - timedelta(days=45),
            }
        )
        item_2, _ = QuotationLineItem.objects.update_or_create(
            quotation=quote_1,
            description="SWA 4-Core 95mm² Armoured Low Smoke Zero Halogen Drum (100m)",
            defaults={
                "qty": Decimal("6.00"),
                "discount": Decimal("0.00"),
                "per": "Drum",
                "each": Decimal("1850.00"),
                "supplier_price": Decimal("1850.00"),
                "management_approved": True,
                "management_approved_date": date.today() - timedelta(days=45),
            }
        )
        item_3, _ = QuotationLineItem.objects.update_or_create(
            quotation=quote_1,
            description="Galvanised Cable Tray 300mm Heavy Duty (3m lengths)",
            defaults={
                "qty": Decimal("60.00"),
                "discount": Decimal("0.00"),
                "per": "Length",
                "each": Decimal("45.00"),
                "supplier_price": Decimal("45.00"),
                "management_approved": True,
                "management_approved_date": date.today() - timedelta(days=45),
            }
        )

        call_off_1, _ = OrderLineCallOff.objects.update_or_create(
            call_off_ref="CO-2026-001",
            defaults={
                "line_item": item_1,
                "qty": Decimal("2.00"),
                "price": Decimal("2500.00"),
                "expected_delivery_date": date.today() - timedelta(days=20),
                "called_off_by": users_by_role[UserAccount.Role.PROCUREMENT_DEPARTMENT],
                "approved_by": users_by_role[UserAccount.Role.CONTRACTS_MANAGER],
            }
        )
        call_off_2, _ = OrderLineCallOff.objects.update_or_create(
            call_off_ref="CO-2026-002",
            defaults={
                "line_item": item_2,
                "qty": Decimal("3.00"),
                "price": Decimal("5550.00"),
                "expected_delivery_date": date.today() - timedelta(days=10),
                "called_off_by": users_by_role[UserAccount.Role.MANAGERS],
                "approved_by": users_by_role[UserAccount.Role.CONTRACTS_MANAGER],
            }
        )

        # Quotation 2: Pending Approval
        Quotation.objects.update_or_create(
            quote_ref="QR-2026-002",
            defaults={
                "project": project_shard,
                "supplier": company_supplier,
                "quote_total": Decimal("7000.00"),
                "status": Quotation.Status.PENDING,
                "sig_procurement_department": True,
                "sig_procurement_department_date": date.today() - timedelta(days=2),
                "created_by": users_by_role[UserAccount.Role.PROCUREMENT_DEPARTMENT],
            }
        )
        print("    -> Quotations, line items, call-offs, and approval signatures seeded.")

        # -------------------------------------------------------------
        # 8. Commercial Department (Variations & Monthly Applications)
        # -------------------------------------------------------------
        print_step("8. Seeding Variations & Monthly Applications")
        var_1, _ = Variation.objects.update_or_create(
            vo_number="VO-001",
            defaults={
                "project": project_shard,
                "created_by": users_by_role[UserAccount.Role.COMMERCIAL_DEPARTMENT],
                "variation_sheet_number": "VS-01",
                "site_instruction_no": "SI-2026-089",
                "attention_of": "David Smith (Client PM)",
                "description_of_works": "Relocation of sub-distribution boards and cable tray re-routing on Level 14 due to structural beam clash.",
                "comments": "Architectural change notification issued on 14 Jan.",
                "evidence_url": "https://images.unsplash.com/photo-1541888946425-d0fbb186c5f8?w=800",
                "total_amount": Decimal("24500.00"),
                "valuation_amount": Decimal("24500.00"),
                "percent_claimed": Decimal("90.00"),
                "amount_claimed": Decimal("22000.00"),
                "client_certified_amount": Decimal("20000.00"),
                "approval_status": Variation.ApprovalStatus.APPROVED,
                "supervisor_approved": True,
                "supervisor_approved_date": date.today() - timedelta(days=35),
                "manager_approved": True,
                "manager_approved_date": date.today() - timedelta(days=34),
                "contracts_manager_approved": True,
                "contracts_manager_approved_date": date.today() - timedelta(days=33),
                "project_director_approved": True,
                "project_director_approved_date": date.today() - timedelta(days=32),
                "managing_director_approved": True,
                "managing_director_approved_date": date.today() - timedelta(days=31),
                "commercial_department_approved": True,
                "commercial_department_approved_date": date.today() - timedelta(days=30),
                "fully_approved": True,
                "submitted_to_client": True,
                "signed_by_client": True,
            }
        )
        var_1.assigned_users.set([emp_user])

        VariationLine.objects.update_or_create(
            variation=var_1,
            work_section="Cable Tray Diversion & Re-pull",
            defaults={
                "site_instruction": "SI-2026-089",
                "work_area": "Level 14 Core",
                "labour": Decimal("6500.00"),
                "labour_target": Decimal("5500.00"),
                "material": Decimal("4000.00"),
                "qty": Decimal("1.00"),
            }
        )
        VariationLine.objects.update_or_create(
            variation=var_1,
            work_section="Sub-board Relocation & Re-termination",
            defaults={
                "site_instruction": "SI-2026-089",
                "work_area": "Level 14 West",
                "labour": Decimal("8000.00"),
                "labour_target": Decimal("7000.00"),
                "material": Decimal("6000.00"),
                "qty": Decimal("1.00"),
            }
        )

        var_2, _ = Variation.objects.update_or_create(
            vo_number="VO-002",
            defaults={
                "project": project_shard,
                "created_by": users_by_role[UserAccount.Role.COMMERCIAL_DEPARTMENT],
                "variation_sheet_number": "VS-02",
                "site_instruction_no": "SI-2026-112",
                "description_of_works": "Additional acoustic ceiling baffles in executive conference room.",
                "total_amount": Decimal("12800.00"),
                "approval_status": Variation.ApprovalStatus.PENDING,
                "supervisor_approved": True,
                "supervisor_approved_date": date.today() - timedelta(days=5),
                "manager_approved": True,
                "manager_approved_date": date.today() - timedelta(days=4),
            }
        )
        var_2.assigned_users.set([emp_user])

        # Monthly Applications across 3 consecutive months
        MonthlyApplication.objects.update_or_create(
            project=project_shard,
            application_number=1,
            defaults={
                "date": date.today() - timedelta(days=60),
                "ref_no": "APP-VAL-001",
                "retention_percentage": Decimal("2.50"),
                "contract_works_total": Decimal("250000.00"),
                "variations_total": Decimal("0.00"),
                "amount_claimed": Decimal("243750.00"),
                "client_certified_amount": Decimal("243750.00"),
                "certified_amount": Decimal("243750.00"),
                "works_valued_to_date": date.today() - timedelta(days=60),
                "payment_notice_date": date.today() - timedelta(days=45),
                "final_date_for_payment": date.today() - timedelta(days=30),
            }
        )
        MonthlyApplication.objects.update_or_create(
            project=project_shard,
            application_number=2,
            defaults={
                "date": date.today() - timedelta(days=30),
                "ref_no": "APP-VAL-002",
                "retention_percentage": Decimal("2.50"),
                "contract_works_total": Decimal("320000.00"),
                "variations_total": Decimal("22000.00"),
                "amount_claimed": Decimal("333450.00"),
                "client_certified_amount": Decimal("325000.00"),
                "certified_amount": Decimal("325000.00"),
                "works_valued_to_date": date.today() - timedelta(days=30),
                "payment_notice_date": date.today() - timedelta(days=15),
                "final_date_for_payment": date.today() - timedelta(days=1),
            }
        )
        MonthlyApplication.objects.update_or_create(
            project=project_shard,
            application_number=3,
            defaults={
                "date": date.today(),
                "ref_no": "APP-VAL-003",
                "retention_percentage": Decimal("2.50"),
                "contract_works_total": Decimal("210000.00"),
                "variations_total": Decimal("24500.00"),
                "amount_claimed": Decimal("228637.50"),
                "works_valued_to_date": date.today(),
                "payment_notice_date": date.today() + timedelta(days=7),
                "final_date_for_payment": date.today() + timedelta(days=21),
            }
        )
        print("    -> Variations (approved & pending) and 3 monthly applications configured.")

        # -------------------------------------------------------------
        # 9. User Invoices (Employee Submissions & Multi-Stage Approvals)
        # -------------------------------------------------------------
        print_step("9. Seeding User Invoices (Labour, Variation, Proforma, Loading & Clearing)")
        # 1. Fully approved & paid Labour Target invoice
        UserInvoice.objects.update_or_create(
            invoice_number="INV-2026-0001",
            defaults={
                "project": project_shard,
                "created_by": emp_user,
                "status": UserInvoice.Status.SUBMITTED,
                "source_type": UserInvoice.SourceType.LABOUR_TARGET,
                "source_id": f"{assignment_l14.id}:0",
                "work_area": "Core A & B",
                "work_section": "First Fix Containment & Cable Trays",
                "description": "Completed first fix containment installation on Level 14 Core A & B",
                "total": Decimal("12000.00"),
                "supervisor_approved": True,
                "supervisor_approved_date": date.today() - timedelta(days=18),
                "supervisor_approved_by": users_by_role[UserAccount.Role.SUPERVISOR],
                "manager_approved": True,
                "manager_approved_date": date.today() - timedelta(days=16),
                "manager_approved_by": users_by_role[UserAccount.Role.MANAGERS],
                "contracts_manager_approved": True,
                "contracts_manager_approved_date": date.today() - timedelta(days=14),
                "contracts_manager_approved_by": users_by_role[UserAccount.Role.CONTRACTS_MANAGER],
                "project_director_approved": True,
                "project_director_approved_date": date.today() - timedelta(days=12),
                "project_director_approved_by": users_by_role[UserAccount.Role.PROJECT_DIRECTOR],
                "managing_director_approved": True,
                "managing_director_approved_date": date.today() - timedelta(days=10),
                "managing_director_approved_by": users_by_role[UserAccount.Role.MANAGING_DIRECTOR],
                "finance_paid": True,
                "finance_paid_date": date.today() - timedelta(days=8),
                "finance_paid_by": users_by_role[UserAccount.Role.FINANCE_DEPARTMENT],
                "finance_comments": "Payment batched and released via BACS.",
            }
        )

        # 2. Partially approved Labour Target invoice
        UserInvoice.objects.update_or_create(
            invoice_number="INV-2026-0002",
            defaults={
                "project": project_shard,
                "created_by": emp_user,
                "status": UserInvoice.Status.SUBMITTED,
                "source_type": UserInvoice.SourceType.LABOUR_TARGET,
                "source_id": f"{assignment_l14.id}:1",
                "work_area": "Electrical Cupboard 14.1",
                "work_section": "Sub-Main Cabling & Distribution Boards",
                "description": "Sub-main cable pulling and distribution board mounting completed",
                "total": Decimal("14000.00"),
                "supervisor_approved": True,
                "supervisor_approved_date": date.today() - timedelta(days=4),
                "supervisor_approved_by": users_by_role[UserAccount.Role.SUPERVISOR],
                "manager_approved": True,
                "manager_approved_date": date.today() - timedelta(days=2),
                "manager_approved_by": users_by_role[UserAccount.Role.MANAGERS],
            }
        )

        # 3. Fully approved Variation invoice (awaiting finance payment)
        UserInvoice.objects.update_or_create(
            invoice_number="INV-2026-0003",
            defaults={
                "project": project_shard,
                "created_by": emp_user,
                "status": UserInvoice.Status.SUBMITTED,
                "source_type": UserInvoice.SourceType.VARIATION,
                "source_id": str(var_1.id),
                "variation_sheet_no": var_1.vo_number,
                "work_area": "Level 14 Core",
                "work_section": "Cable Tray Diversion",
                "description": "Works executed per Site Instruction SI-2026-089",
                "total": Decimal("24500.00"),
                "supervisor_approved": True,
                "supervisor_approved_date": date.today() - timedelta(days=5),
                "manager_approved": True,
                "manager_approved_date": date.today() - timedelta(days=4),
                "contracts_manager_approved": True,
                "contracts_manager_approved_date": date.today() - timedelta(days=3),
                "project_director_approved": True,
                "project_director_approved_date": date.today() - timedelta(days=2),
                "managing_director_approved": True,
                "managing_director_approved_date": date.today() - timedelta(days=1),
                "commercial_comments": "Verified against client signed site instruction.",
            }
        )

        # 4. Proforma NR invoice
        UserInvoice.objects.update_or_create(
            invoice_number="INV-2026-0004",
            defaults={
                "project": project_shard,
                "created_by": emp_user,
                "status": UserInvoice.Status.SUBMITTED,
                "source_type": UserInvoice.SourceType.PROFORMA,
                "source_id": "PF-2026-001",
                "proforma_no": "PF-2026-001",
                "description": "Specialist atrium high-access boom platform hire",
                "total": Decimal("3500.00"),
                "supervisor_approved": True,
                "supervisor_approved_date": date.today() - timedelta(days=1),
            }
        )

        # 5. Loading & Clearing invoice
        UserInvoice.objects.update_or_create(
            invoice_number="INV-2026-0005",
            defaults={
                "project": project_shard,
                "created_by": emp_user,
                "status": UserInvoice.Status.SUBMITTED,
                "source_type": UserInvoice.SourceType.LOADING_CLEARING,
                "source_id": "LC-2026-001",
                "description": "Night delivery offloading and material distribution to Level 14 via hoist",
                "total": Decimal("850.00"),
            }
        )

        # 6. Draft Bucket Item
        UserInvoice.objects.update_or_create(
            invoice_number="BKT-A92B4F10",
            defaults={
                "project": project_shard,
                "created_by": emp_user,
                "status": UserInvoice.Status.BUCKET,
                "source_type": UserInvoice.SourceType.LABOUR_TARGET,
                "source_id": f"{assignment_l14.id}:2",
                "work_area": "North & East Wings",
                "work_section": "Second Fix Lighting & Power Outlets",
                "description": "Draft unsubmitted task in bucket",
                "total": Decimal("16000.00"),
            }
        )
        print("    -> 6 user invoices created across all 4 source types with varied approval/payment states.")

        # -------------------------------------------------------------
        # 10. Supplier Invoices
        # -------------------------------------------------------------
        print_step("10. Seeding Supplier Invoices")
        SupplierInvoice.objects.update_or_create(
            invoice_number="SUP-INV-2026-0089",
            defaults={
                "company": primary_company,
                "company_supplier": company_supplier,
                "submitted_by": supp_user,
                "invoice_date": date.today() - timedelta(days=20),
                "amount": Decimal("2500.00"),
                "description": "Distribution boards delivery under call-off CO-2026-001",
                "po_reference": "QR-2026-001",
                "call_off": call_off_1,
                "call_off_reference": "CO-2026-001",
                "status": SupplierInvoice.Status.PAID,
                "processed_by": users_by_role[UserAccount.Role.PROCUREMENT_DEPARTMENT],
                "processed_at": timezone.now() - timedelta(days=15),
            }
        )

        SupplierInvoice.objects.update_or_create(
            invoice_number="SUP-INV-2026-0104",
            defaults={
                "company": primary_company,
                "company_supplier": company_supplier,
                "submitted_by": supp_user,
                "invoice_date": date.today() - timedelta(days=10),
                "amount": Decimal("5550.00"),
                "description": "SWA Armoured cable drums delivery under call-off CO-2026-002",
                "po_reference": "QR-2026-001",
                "call_off": call_off_2,
                "call_off_reference": "CO-2026-002",
                "status": SupplierInvoice.Status.APPROVED,
                "procurement_comments": "Delivery ticket #DT-9821 verified on site by supervisor.",
                "processed_by": users_by_role[UserAccount.Role.PROCUREMENT_DEPARTMENT],
                "processed_at": timezone.now() - timedelta(days=5),
            }
        )

        SupplierInvoice.objects.update_or_create(
            invoice_number="SUP-INV-2026-0118",
            defaults={
                "company": primary_company,
                "company_supplier": company_supplier,
                "submitted_by": supp_user,
                "invoice_date": date.today() - timedelta(days=2),
                "amount": Decimal("2700.00"),
                "description": "Cable tray lengths supply",
                "po_reference": "QR-2026-001",
                "status": SupplierInvoice.Status.PROCESSING,
            }
        )
        print("    -> Supplier invoices linked to PO call-offs with PAID, APPROVED, and PROCESSING states.")

        # -------------------------------------------------------------
        # 11. Project Financial Breakdown Bookings
        # -------------------------------------------------------------
        print_step("11. Seeding Financial Bookings")
        LabourBooking.objects.get_or_create(
            project=project_shard,
            user=emp_user,
            amount=Decimal("18500.00"),
            date=date.today() - timedelta(days=45),
            defaults={"is_approved": True}
        )
        ProjectValueBooking.objects.get_or_create(
            project=project_shard,
            user=emp_user,
            amount=Decimal("65000.00"),
            date=date.today() - timedelta(days=45),
            defaults={"is_approved": True}
        )
        PlantHireBooking.objects.get_or_create(
            project=project_shard,
            amount=Decimal("4200.00"),
            date=date.today() - timedelta(days=40),
            defaults={"is_approved": True}
        )
        LoadingClearingBooking.objects.get_or_create(
            project=project_shard,
            user=emp_user,
            amount=Decimal("2800.00"),
            date=date.today() - timedelta(days=35),
            defaults={
                "description": "Skips waste removal and mobile crane setup",
                "attachment_urls": ["https://images.unsplash.com/photo-1541888946425-d0fbb186c5f8?w=800"],
                "is_approved": True
            }
        )
        ManagementPrelimBooking.objects.get_or_create(
            project=project_shard,
            amount=Decimal("7500.00"),
            date=date.today() - timedelta(days=45),
            defaults={"is_approved": True}
        )
        ProformaNR.objects.get_or_create(
            project=project_shard,
            amount=Decimal("3500.00"),
            date=date.today() - timedelta(days=30),
            defaults={"material_estimate": Decimal("1200.00")}
        )
        print("    -> Financial breakdown bookings active for project breakdown view.")

        # -------------------------------------------------------------
        # 12. RFIs and Messages
        # -------------------------------------------------------------
        print_step("12. Seeding RFIs & Communication Threads")
        rfi_1, _ = RFI.objects.update_or_create(
            project=project_shard,
            rfi_number="#001",
            defaults={
                "created_by": emp_user,
                "trade": "Electrical",
                "description": "Drawing E-104 shows 400A busbar trunking intersecting with 600mm HVAC ductwork on Grid Line 4. Request clarification on priority routing.",
                "status": "OPEN",
                "assigned_to_technical_department": True,
            }
        )
        RFIMessage.objects.get_or_create(
            rfi=rfi_1,
            author=emp_user,
            text="Raised during site containment walkaround. Photo attached showing physical obstruction at riser entry.",
        )
        RFIMessage.objects.get_or_create(
            rfi=rfi_1,
            author=users_by_role[UserAccount.Role.TECHNICAL_DEPARTMENT],
            text="Reviewed architectural BIM coordinate model. Busbar trunking can drop 200mm below ductwork. Issuing revised detail sketch SK-E-02.",
        )
        RFIMessage.objects.get_or_create(
            rfi=rfi_1,
            author=users_by_role[UserAccount.Role.PROJECT_ADMIN],
            text="Agreed. Approved for site execution according to sketch SK-E-02.",
        )

        rfi_2, _ = RFI.objects.update_or_create(
            project=project_shard,
            rfi_number="#002",
            defaults={
                "created_by": emp_user,
                "trade": "Mechanical & Plumbing",
                "description": "Confirmation of mains water connection pressure test certification requirement before trench backfill.",
                "status": "CLOSED",
                "closed_at": timezone.now() - timedelta(days=5),
            }
        )
        RFIMessage.objects.get_or_create(
            rfi=rfi_2,
            author=emp_user,
            text="Pressure test completed at 10 bar for 2 hours with zero pressure drop. Inspector witnessed test.",
        )
        RFIMessage.objects.get_or_create(
            rfi=rfi_2,
            author=users_by_role[UserAccount.Role.CONTRACTS_MANAGER],
            text="Test certificate received and logged into document register. Backfill approved.",
        )
        print("    -> RFIs and multi-user message threads configured.")

        # -------------------------------------------------------------
        # 13. Operations (RAMS, Daily Briefing, Toolbox Talks, To-Dos)
        # -------------------------------------------------------------
        print_step("13. Seeding Operations & Health & Safety Records")
        RAMS.objects.update_or_create(
            project=project_shard,
            title="RAMS-001: LV Switchgear Installation & Sub-Main Cable Pulling",
            defaults={
                "created_by": users_by_role[UserAccount.Role.MANAGERS],
                "description": "Detailed risk assessment and method statement for delivery, rigging, positioning, and terminating 400A switchboard units.",
                "date": date.today() - timedelta(days=30),
                "review_date": date.today() + timedelta(days=180),
                "completed_at": timezone.now() - timedelta(days=28),
            }
        )
        DailyBriefing.objects.update_or_create(
            project=project_shard,
            title="Daily Briefing: Core 2 Crane Lift & Exclusion Zone Protocols",
            defaults={
                "created_by": users_by_role[UserAccount.Role.SUPERVISOR],
                "description": "Major crane lift of rooftop chiller units between 09:00 - 13:00. Exclusion zone active on East service yard.",
                "date": date.today(),
            }
        )
        ToolboxTalk.objects.update_or_create(
            project=project_shard,
            title="TBT-12: Working at Heights & MEWP Safety Procedures",
            defaults={
                "created_by": users_by_role[UserAccount.Role.SUPERVISOR],
                "description": "Safety briefing covering harness anchor points, pre-use daily vehicle checks, and exclusion zone barricades.",
                "date": date.today() - timedelta(days=3),
            }
        )
        ToDoList.objects.update_or_create(
            project=project_shard,
            title="Install secondary earthing tape in main substation",
            defaults={
                "created_by": users_by_role[UserAccount.Role.MANAGERS],
                "description": "Ensure copper tape is bonded to earth bar with double set screws.",
                "date": date.today(),
                "completion_date": date.today() + timedelta(days=2),
                "assign_user": emp_user.full_name,
            }
        )
        ToDoList.objects.update_or_create(
            project=project_shard,
            title="Verify torque marks on 400A busbar joint connections",
            defaults={
                "created_by": users_by_role[UserAccount.Role.PROJECT_DIRECTOR],
                "description": "All joints marked with yellow torque indicator paint.",
                "date": date.today() - timedelta(days=7),
                "completed_at": timezone.now() - timedelta(days=5),
                "assign_user": users_by_role[UserAccount.Role.SUPERVISOR].full_name,
            }
        )
        print("    -> Operations (RAMS, briefings, toolbox talks, todos) active.")

        # -------------------------------------------------------------
        # 14. Attendance & Live Clock-In
        # -------------------------------------------------------------
        print_step("14. Seeding Attendance Logs (Active Live Check-In)")
        today = date.today()
        # Today's active check-in so employee dashboard is immediately active
        now_time = timezone.now()
        checkin_time = now_time.replace(hour=7, minute=45, second=0, microsecond=0)
        AttendanceLog.objects.update_or_create(
            user=emp_user,
            date=today,
            defaults={
                "project": project_shard,
                "company": primary_company,
                "check_in_time": checkin_time,
                "check_out_time": None,
                "check_in_lat": 51.5045,
                "check_in_long": -0.0865,
                "status": "checked_in",
            }
        )

        # Historical attendance records
        for days_ago in range(1, 5):
            past_date = today - timedelta(days=days_ago)
            past_in = (now_time - timedelta(days=days_ago)).replace(hour=7, minute=30, second=0)
            past_out = (now_time - timedelta(days=days_ago)).replace(hour=16, minute=30, second=0)
            AttendanceLog.objects.get_or_create(
                user=emp_user,
                date=past_date,
                defaults={
                    "project": project_shard,
                    "company": primary_company,
                    "check_in_time": past_in,
                    "check_out_time": past_out,
                    "check_in_lat": 51.5045,
                    "check_in_long": -0.0865,
                    "check_out_lat": 51.5045,
                    "check_out_long": -0.0865,
                    "status": "checked_out",
                }
            )
        print("    -> Live check-in and historical attendance registered for employee.")

        # -------------------------------------------------------------
        # 15. Super Admin Dashboard (Monthly Invoices & Activity)
        # -------------------------------------------------------------
        print_step("15. Seeding Super Admin Monthly Invoices & Activities")
        current_year = date.today().year
        seeded_amount = Decimal("1690.00")
        MonthlyInvoice.objects.update_or_create(
            company=primary_company,
            year=current_year,
            month=1,
            defaults={
                "amount": seeded_amount,
                "is_sent": True,
                "is_paid": True,
                "payment_date": timezone.now() - timedelta(days=60),
                "invoice_number": f"TRESTA-INV-{current_year}-01",
            }
        )
        MonthlyInvoice.objects.update_or_create(
            company=primary_company,
            year=current_year,
            month=2,
            defaults={
                "amount": seeded_amount,
                "is_sent": True,
                "is_paid": True,
                "payment_date": timezone.now() - timedelta(days=30),
                "invoice_number": f"TRESTA-INV-{current_year}-02",
            }
        )
        MonthlyInvoice.objects.update_or_create(
            company=primary_company,
            year=current_year,
            month=3,
            defaults={
                "amount": seeded_amount,
                "is_sent": True,
                "is_paid": False,
                "invoice_number": f"TRESTA-INV-{current_year}-03",
            }
        )

        activities = [
            "Company 'Tresta Test Company' subscription renewed",
            "Project 'The Shard - Commercial Fit-Out' created with value £1.85m",
            "User 'soper17343@homephit.com' submitted task invoice INV-2026-0001",
            "Quotation QR-2026-001 approved and PO created",
            "Monthly application APP-VAL-002 client certified for £325,000",
        ]
        for act in activities:
            RecentActivity.objects.get_or_create(activity_name=act)
        print("    -> Monthly subscription invoices and audit trail generated.")

        # -------------------------------------------------------------
        # 16. Notifications
        # -------------------------------------------------------------
        print_step("16. Seeding User Notifications")
        notification_templates = [
            (
                emp_user,
                "Project Assigned",
                "You have been assigned to The Shard - Commercial Fit-Out.",
                Notification.Type.PROJECT_ASSIGNED,
                True,
            ),
            (
                emp_user,
                "Work Approved",
                "Your labour invoice INV-2026-0001 has been approved and paid by Finance.",
                Notification.Type.WORK_APPROVED,
                True,
            ),
            (
                emp_user,
                "Task Assigned",
                "New To-Do task assigned: Install secondary earthing tape in main substation.",
                Notification.Type.TASK_ASSIGNED,
                False,
            ),
            (
                users_by_role[UserAccount.Role.SUPERVISOR],
                "Invoice Review Required",
                "Employee Edward submitted invoice INV-2026-0002 for your review.",
                Notification.Type.INFO,
                False,
            ),
            (
                users_by_role[UserAccount.Role.COMMERCIAL_DEPARTMENT],
                "Variation Update",
                "Variation VO-001 was approved and certified by the client for £20,000.",
                Notification.Type.INFO,
                False,
            ),
            (
                users_by_role[UserAccount.Role.FINANCE_DEPARTMENT],
                "Payment Ready",
                "User invoice INV-2026-0003 is fully signed off and ready for disbursement.",
                Notification.Type.INFO,
                False,
            ),
            (
                users_by_role[UserAccount.Role.PROCUREMENT_DEPARTMENT],
                "Quotation Received",
                "BuildMax Building Supplies submitted updated pricing on quotation QR-2026-002.",
                Notification.Type.INFO,
                False,
            ),
        ]

        for user, title, body, ntype, is_read in notification_templates:
            Notification.objects.get_or_create(
                user=user,
                title=title,
                defaults={
                    "body": body,
                    "type": ntype,
                    "is_read": is_read,
                }
            )
        print("    -> Role-specific notification queues populated.")

    print_summary(primary_company, projects)


def print_summary(company, projects):
    """Print an organized, easy-to-read summary of all created data and credentials."""
    print("\n" + "=" * 90)
    print(" DEMO DATA SEEDING COMPLETE! TEST ACCOUNTS & MODULE OVERVIEW")
    print("=" * 90)
    print(f"Company:  {company.company_name} (Status: {company.status.upper()})")
    print(f"Projects: {', '.join(p.project_name for p in projects)}")
    print("-" * 90)
    print(f"{'ROLE':<26} | {'EMAIL':<32} | {'PASSWORD':<10} | {'TEST FOCUS'}")
    print("-" * 90)

    for u in USER_CONFIGS:
        role_label = u["role"].replace("_", " ").title()
        print(f"{role_label:<26} | {u['email']:<32} | {u['password']:<10} | {u['description']}")

    print("-" * 90)
    print("QUICK START TESTING TIPS:")
    print(" 1. Super Admin Dashboard: Log in as admin@gmail.com (pw: admin)")
    print("    -> Test company metrics, subscriptions, monthly invoices, and overview.")
    print(" 2. Employee Mobile Flow:  Log in as soper17343@homephit.com (pw: 1fjw0676)")
    print("    -> User is currently checked into 'The Shard'. Test task completions, bucket list,")
    print("       submitting variations, proforma NR, operations (RAMS, briefings), and RFIs.")
    print(" 3. Management Approval Chain: Log in as supervisor / manager / contract.manager")
    print("    -> Test multi-stage invoice sign-offs on INV-2026-0002 and variation VO-002.")
    print(" 4. Commercial Department: Log in as commercial.department@gmail.com")
    print("    -> Test monthly application #3, client claim valuations, and White Card view.")
    print(" 5. Procurement & Supplier Portal: Log in as procurement@gmail.com or supplier@gmail.com")
    print("    -> Review quote QR-2026-001, manage call-offs CO-2026-001/002, and invoice match.")
    print(" 6. Finance Department: Log in as financial@gmail.com")
    print("    -> Test invoice list disbursement, mark user invoices or supplier invoices as paid.")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    seed_demo_data()
