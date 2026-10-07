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


class SuperAdminBillingAndProfileTest(TestCase):
    def setUp(self):
        self.super_admin = UserAccount.objects.create_user(
            email="superadmin@tresta.cloud",
            password="InitialPassword123!",
            first_name="Super",
            last_name="Admin",
            role=UserAccount.Role.SUPER_ADMIN,
        )
        self.company = Company.objects.create(
            company_name="Client Company Ltd",
            monthly_subscription=Decimal("100.00"),
            per_user_rate=Decimal("5.00"),
            activate=True,
        )

    def test_super_admin_billing_details_dynamic_reflection(self):
        from django.template.loader import render_to_string
        from app.account.models import UserProfile

        profile, _ = UserProfile.objects.get_or_create(user=self.super_admin)
        profile.company_name = "New Tresta Corp"
        profile.vat_number = "GB999123456"
        profile.address = "10 Downing Street, London"
        profile.account_name = "New Estrada Holdings"
        profile.bank_name = "Barclays"
        profile.sort_code = "20-00-00"
        profile.account_number = "99887766"
        profile.save()

        billing = InvoiceService.get_super_admin_billing_details()
        self.assertEqual(billing["company_name"], "New Tresta Corp")
        self.assertEqual(billing["vat_number"], "GB999123456")
        self.assertEqual(billing["address"], "10 Downing Street, London")
        self.assertEqual(billing["account_name"], "New Estrada Holdings")
        self.assertEqual(billing["bank_name"], "Barclays")
        self.assertEqual(billing["sort_code"], "20-00-00")
        self.assertEqual(billing["account_number"], "99887766")

        # Verify rendered HTML template reflects the updated details
        invoice = MonthlyInvoice.objects.create(
            company=self.company,
            year=2026,
            month=10,
            amount=Decimal("125.00"),
            invoice_number="INV-202610-001",
        )
        html = render_to_string("super_admin/invoice_pdf.html", {
            "company": self.company,
            "invoice": invoice,
            "billing": billing,
            "total_amount": Decimal("125.00"),
            "monthly_sub": Decimal("100.00"),
            "per_user": Decimal("5.00"),
            "users": 5,
            "user_licenses_total": Decimal("25.00"),
            "date": "October 07, 2026",
            "due_date": "October 17, 2026",
        })

        self.assertIn("GB999123456", html)
        self.assertIn("10 Downing Street, London", html)
        self.assertIn("New Estrada Holdings", html)
        self.assertIn("Barclays", html)
        self.assertIn("20-00-00", html)
        self.assertIn("99887766", html)

    def test_super_admin_profile_api_update_and_2fa(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.super_admin)

        response = client.put(
            "/api/v1/account/profile/",
            {
                "first_name": "UpdatedSuper",
                "last_name": "UpdatedAdmin",
                "two_factor_enabled": True,
                "profile": {
                    "company_name": "Updated Tresta",
                    "vat_number": "VAT-555-888",
                    "address": "42 Wallaby Way, Sydney",
                    "account_name": "Super Admin Beneficiary",
                    "bank_name": "HSBC",
                    "sort_code": "40-00-01",
                    "account_number": "11223344",
                    "two_factor_enabled": True,
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        self.super_admin.refresh_from_db()
        self.assertTrue(self.super_admin.two_factor_enabled)
        self.assertEqual(self.super_admin.first_name, "UpdatedSuper")

        profile = self.super_admin.profile
        self.assertTrue(profile.two_factor_enabled)
        self.assertEqual(profile.vat_number, "VAT-555-888")
        self.assertEqual(profile.address, "42 Wallaby Way, Sydney")
        self.assertEqual(profile.account_name, "Super Admin Beneficiary")
        self.assertEqual(profile.bank_name, "HSBC")
        self.assertEqual(profile.sort_code, "40-00-01")
        self.assertEqual(profile.account_number, "11223344")

        # Test change password endpoint
        pwd_response = client.post(
            "/api/v1/account/change-password/",
            {
                "old_password": "InitialPassword123!",
                "new_password": "NewSecurePassword456!",
            },
            format="json",
        )
        self.assertEqual(pwd_response.status_code, 200)
        self.super_admin.refresh_from_db()
        self.assertTrue(self.super_admin.check_password("NewSecurePassword456!"))

    def test_multi_super_admin_latest_profile_reflection(self):
        # Create a second super admin
        second_admin = UserAccount.objects.create_user(
            email="secondadmin@tresta.cloud",
            password="SecondPassword123!",
            first_name="Second",
            last_name="SuperAdmin",
            role=UserAccount.Role.SUPER_ADMIN,
        )
        from app.account.models import UserProfile
        profile2, _ = UserProfile.objects.get_or_create(user=second_admin)
        profile2.account_name = "Second Admin Bank Account"
        profile2.vat_number = "GB-SECOND-VAT"
        profile2.address = "100 Oxford Street, London"
        profile2.bank_name = "Lloyds"
        profile2.save()

        # InvoiceService should prioritize the most recently updated super admin profile
        billing = InvoiceService.get_super_admin_billing_details()
        self.assertEqual(billing["account_name"], "Second Admin Bank Account")
        self.assertEqual(billing["vat_number"], "GB-SECOND-VAT")
        self.assertEqual(billing["address"], "100 Oxford Street, London")
        self.assertEqual(billing["bank_name"], "Lloyds")

    def test_invoice_email_template_contains_line_items_breakdown(self):
        from django.template.loader import render_to_string
        html = render_to_string("super_admin/invoice_email.html", {
            "company": self.company,
            "month_name": "October",
            "year": 2026,
            "invoice_number": "INV-202610-TEST",
            "monthly_sub": Decimal("100.00"),
            "per_user": Decimal("5.00"),
            "users": 5,
            "user_licenses_total": Decimal("25.00"),
            "total_amount": Decimal("125.00"),
        })
        self.assertIn("Subscription per month", html)
        self.assertIn("100.00", html)
        self.assertIn("Users (registered seats)", html)
        self.assertIn("25.00", html)
        self.assertIn("125.00", html)
        self.assertIn("INV-202610-TEST", html)



