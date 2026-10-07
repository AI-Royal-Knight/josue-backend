from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from app.account.models import Company, UserAccount, Invitation
from app.super_admin.models import MonthlyInvoice
from app.super_admin.services import InvoiceService
from app.super_admin.tasks import generate_and_send_monthly_invoices


class MonthlyInvoiceCalculationTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            company_name="Test Engineering Ltd",
            monthly_subscription=Decimal("100.00"),
            per_user_rate=Decimal("5.00"),
            activate=True,
            auto_monthly_inv=True,
            auto_monthly_inv_date=1,
        )

    def test_invoice_calculation_with_five_users(self):
        # Create 5 users for the company
        for i in range(5):
            UserAccount.objects.create(
                email=f"user{i}@testengineering.com",
                first_name=f"User{i}",
                last_name="Test",
                company=self.company,
                role=UserAccount.Role.EMPLOYEE if i > 0 else UserAccount.Role.ADMIN,
            )

        breakdown = InvoiceService.calculate_monthly_invoice_breakdown(self.company)
        self.assertEqual(breakdown["monthly_sub"], Decimal("100.00"))
        self.assertEqual(breakdown["per_user"], Decimal("5.00"))
        self.assertEqual(breakdown["users_count"], 5)
        self.assertEqual(breakdown["user_licenses_total"], Decimal("25.00"))
        self.assertEqual(breakdown["total_amount"], Decimal("125.00"))

        # Test generating invoice via task
        generate_and_send_monthly_invoices(
            company_id=self.company.id,
            force=True,
            target_year=2026,
            target_month=10,
        )
        invoice = MonthlyInvoice.objects.get(company=self.company, year=2026, month=10)
        self.assertEqual(invoice.amount, Decimal("125.00"))

    def test_invoice_calculation_when_users_increase_to_ten_next_month(self):
        # Month 1: 5 users
        for i in range(5):
            UserAccount.objects.create(
                email=f"user{i}@testengineering.com",
                first_name=f"User{i}",
                last_name="Test",
                company=self.company,
                role=UserAccount.Role.EMPLOYEE if i > 0 else UserAccount.Role.ADMIN,
            )

        generate_and_send_monthly_invoices(
            company_id=self.company.id,
            force=True,
            target_year=2026,
            target_month=10,
        )
        inv_oct = MonthlyInvoice.objects.get(company=self.company, year=2026, month=10)
        self.assertEqual(inv_oct.amount, Decimal("125.00"))

        # Month 2: add 5 more users (total 10)
        for i in range(5, 10):
            UserAccount.objects.create(
                email=f"user{i}@testengineering.com",
                first_name=f"User{i}",
                last_name="Test",
                company=self.company,
                role=UserAccount.Role.EMPLOYEE,
            )

        breakdown = InvoiceService.calculate_monthly_invoice_breakdown(self.company)
        self.assertEqual(breakdown["users_count"], 10)
        self.assertEqual(breakdown["user_licenses_total"], Decimal("50.00"))
        self.assertEqual(breakdown["total_amount"], Decimal("150.00"))

        generate_and_send_monthly_invoices(
            company_id=self.company.id,
            force=True,
            target_year=2026,
            target_month=11,
        )
        inv_nov = MonthlyInvoice.objects.get(company=self.company, year=2026, month=11)
        self.assertEqual(inv_nov.amount, Decimal("150.00"))

