from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from app.account.models import UserAccount, Company, RoleAssignment, CompanySupplier, SupplierProfile
from app.supplier.models import SupplierInvitation, SupplierInvoice


class SupplierWorkflowTests(APITestCase):

    def setUp(self):
        # Create companies
        self.company_a = Company.objects.create(company_name="Company Alpha Ltd")
        self.company_b = Company.objects.create(company_name="Company Beta Ltd")
        self.company_c = Company.objects.create(company_name="Company Gamma Ltd")

        # Create Procurement user for Company A
        self.procurement_user = UserAccount.objects.create_user(
            email="procurement@companya.com",
            password="Password123!",
            role=UserAccount.Role.PROCUREMENT_DEPARTMENT,
            company=self.company_a
        )
        RoleAssignment.objects.create(
            user=self.procurement_user,
            role=UserAccount.Role.PROCUREMENT_DEPARTMENT,
            company=self.company_a
        )

        # Create Project Admin (who must NOT be able to invite suppliers)
        self.project_admin = UserAccount.objects.create_user(
            email="admin@companya.com",
            password="Password123!",
            role=UserAccount.Role.PROJECT_ADMIN,
            company=self.company_a
        )

        # Create Procurement user for Company B
        self.procurement_user_b = UserAccount.objects.create_user(
            email="procurement@companyb.com",
            password="Password123!",
            role=UserAccount.Role.PROCUREMENT_DEPARTMENT,
            company=self.company_b
        )
        RoleAssignment.objects.create(
            user=self.procurement_user_b,
            role=UserAccount.Role.PROCUREMENT_DEPARTMENT,
            company=self.company_b
        )

    def test_only_procurement_can_invite_suppliers(self):
        """Verify only procurement department can invite suppliers."""
        # 1. Project Admin tries to invite a supplier -> forbidden
        self.client.force_authenticate(user=self.project_admin)
        res = self.client.post("/api/v1/procurement/suppliers/invite/", {
            "email": "supplier1@example.com",
            "company_name": "Fast Supplies Ltd"
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Procurement user invites a supplier -> success
        self.client.force_authenticate(user=self.procurement_user)
        res = self.client.post("/api/v1/procurement/suppliers/invite/", {
            "email": "supplier1@example.com",
            "company_name": "Fast Supplies Ltd"
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("invitation_token", res.data)
        self.assertIn("/supplier/invitation/", res.data["invitation_link"])

        # Check CompanySupplier was created with PENDING status
        cs = CompanySupplier.objects.get(company=self.company_a, supplier__user__email="supplier1@example.com")
        self.assertEqual(cs.status, CompanySupplier.Status.PENDING)

    def test_supplier_invitation_lifecycle_new_supplier(self):
        """Test the full invitation flow for a brand new supplier."""
        # 1. Invite supplier
        self.client.force_authenticate(user=self.procurement_user)
        invite_res = self.client.post("/api/v1/procurement/suppliers/invite/", {
            "email": "new_supplier@example.com",
            "company_name": "Modern Hardware Ltd"
        })
        token = invite_res.data["invitation_token"]

        # 2. Public checks invitation details
        self.client.force_authenticate(user=None)
        detail_res = self.client.get(f"/api/v1/supplier/invitations/{token}/")
        self.assertEqual(detail_res.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_res.data["company_name"], "Company Alpha Ltd")
        self.assertEqual(detail_res.data["email"], "new_supplier@example.com")
        self.assertFalse(detail_res.data["is_existing_user"])

        # 3. Accept invitation with credentials
        accept_res = self.client.post(f"/api/v1/supplier/invitations/{token}/accept/", {
            "first_name": "John",
            "last_name": "Supplier",
            "company_name": "Modern Hardware Ltd",
            "password": "SecureSupplierPass123!"
        })
        self.assertEqual(accept_res.status_code, status.HTTP_200_OK)
        self.assertTrue(accept_res.data["success"])
        self.assertIn("access_token", accept_res.data)

        # Verify relationship is ACTIVE
        cs = CompanySupplier.objects.get(company=self.company_a, supplier__user__email="new_supplier@example.com")
        self.assertEqual(cs.status, CompanySupplier.Status.ACTIVE)

        # 4. Try to re-accept -> should fail
        re_accept = self.client.post(f"/api/v1/supplier/invitations/{token}/accept/", {
            "password": "SecureSupplierPass123!"
        })
        self.assertEqual(re_accept.status_code, status.HTTP_400_BAD_REQUEST)

    def test_decline_invitation(self):
        """Test declining an invitation marks both relationship and invitation as declined."""
        self.client.force_authenticate(user=self.procurement_user)
        invite_res = self.client.post("/api/v1/procurement/suppliers/invite/", {
            "email": "decline_me@example.com",
            "company_name": "Declining Co"
        })
        token = invite_res.data["invitation_token"]

        self.client.force_authenticate(user=None)
        decline_res = self.client.post(f"/api/v1/supplier/invitations/{token}/decline/")
        self.assertEqual(decline_res.status_code, status.HTTP_200_OK)

        cs = CompanySupplier.objects.get(company=self.company_a, supplier__user__email="decline_me@example.com")
        self.assertEqual(cs.status, CompanySupplier.Status.DECLINED)

        inv = SupplierInvitation.objects.get(token=token)
        self.assertEqual(inv.status, SupplierInvitation.Status.DECLINED)

    def test_multi_company_supplier_workflow(self):
        """
        Critical requirement: One supplier account can belong to multiple companies.
        Company A invites supplier -> supplier accepts.
        Company B invites same supplier -> relationship is pending -> supplier accepts -> both are active.
        """
        # Step 1: Company A invites supplier
        self.client.force_authenticate(user=self.procurement_user)
        res_a = self.client.post("/api/v1/procurement/suppliers/invite/", {
            "email": "shared_supplier@example.com",
            "company_name": "Multi Supplies Group"
        })
        token_a = res_a.data["invitation_token"]

        # Supplier accepts Company A
        self.client.force_authenticate(user=None)
        self.client.post(f"/api/v1/supplier/invitations/{token_a}/accept/", {
            "first_name": "Alex",
            "last_name": "Merchant",
            "company_name": "Multi Supplies Group",
            "password": "SharedPassword123!"
        })

        # Step 2: Company B invites the SAME supplier email
        self.client.force_authenticate(user=self.procurement_user_b)
        res_b = self.client.post("/api/v1/procurement/suppliers/invite/", {
            "email": "shared_supplier@example.com",
            "company_name": "Multi Supplies Group"
        })
        self.assertEqual(res_b.status_code, status.HTTP_201_CREATED)
        token_b = res_b.data["invitation_token"]

        # Verify only ONE UserAccount exists
        self.assertEqual(UserAccount.objects.filter(email="shared_supplier@example.com").count(), 1)

        # Verify Company A is ACTIVE, Company B is PENDING
        cs_a = CompanySupplier.objects.get(company=self.company_a, supplier__user__email="shared_supplier@example.com")
        cs_b = CompanySupplier.objects.get(company=self.company_b, supplier__user__email="shared_supplier@example.com")
        self.assertEqual(cs_a.status, CompanySupplier.Status.ACTIVE)
        self.assertEqual(cs_b.status, CompanySupplier.Status.PENDING)

        # Step 3: Supplier inspects token B -> recognizes existing user
        self.client.force_authenticate(user=None)
        detail_b = self.client.get(f"/api/v1/supplier/invitations/{token_b}/")
        self.assertTrue(detail_b.data["is_existing_user"])

        # Step 4: Supplier accepts Company B invitation
        accept_b = self.client.post(f"/api/v1/supplier/invitations/{token_b}/accept/", {})
        self.assertEqual(accept_b.status_code, status.HTTP_200_OK)

        # Verify BOTH relationships are now ACTIVE
        cs_a.refresh_from_db()
        cs_b.refresh_from_db()
        self.assertEqual(cs_a.status, CompanySupplier.Status.ACTIVE)
        self.assertEqual(cs_b.status, CompanySupplier.Status.ACTIVE)

        # Step 5: Supplier lists their companies
        supplier_user = UserAccount.objects.get(email="shared_supplier@example.com")
        self.client.force_authenticate(user=supplier_user)
        companies_res = self.client.get("/api/v1/supplier/companies/")
        self.assertEqual(companies_res.status_code, status.HTTP_200_OK)
        company_names = [c["company_name"] for c in companies_res.data]
        self.assertIn("Company Alpha Ltd", company_names)
        self.assertIn("Company Beta Ltd", company_names)

    def test_company_authorization_and_invoice_submission(self):
        """Test that supplier can submit invoices only for active companies and procurement sees them."""
        # Setup active supplier for Company A
        supplier_user = UserAccount.objects.create_user(
            email="authorized_supplier@example.com",
            password="Password123!",
            role=UserAccount.Role.SUPPLIER
        )
        profile = SupplierProfile.objects.create(user=supplier_user, company_name="Auth Supplies")
        CompanySupplier.objects.create(
            company=self.company_a,
            supplier=profile,
            status=CompanySupplier.Status.ACTIVE
        )

        self.client.force_authenticate(user=supplier_user)

        # 1. Attempt to submit invoice for Company C (unlinked / unauthorized) -> 403 Forbidden
        denied_res = self.client.post(
            "/api/v1/supplier/invoices/",
            {
                "invoice_number": "INV-001",
                "invoice_date": "2026-09-01",
                "amount": "1500.00",
                "description": "Materials"
            },
            HTTP_X_COMPANY_ID=str(self.company_c.id)
        )
        self.assertEqual(denied_res.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Submit invoice for Company A (active relationship) -> 201 Created
        allowed_res = self.client.post(
            "/api/v1/supplier/invoices/",
            {
                "invoice_number": "INV-1001",
                "invoice_date": "2026-09-01",
                "amount": "2500.00",
                "description": "Concrete blocks and mortar"
            },
            HTTP_X_COMPANY_ID=str(self.company_a.id)
        )
        self.assertEqual(allowed_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(allowed_res.data["invoice_number"], "INV-1001")
        self.assertEqual(allowed_res.data["status"], "submitted")

        # 3. Procurement for Company A checks invoices -> sees the invoice
        self.client.force_authenticate(user=self.procurement_user)
        proc_res = self.client.get("/api/v1/procurement/supplier-invoices/")
        self.assertEqual(proc_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(proc_res.data), 1)
        self.assertEqual(proc_res.data[0]["invoice_number"], "INV-1001")
        self.assertEqual(proc_res.data[0]["supplier_email"], "authorized_supplier@example.com")

        # 4. Procurement for Company B checks invoices -> does NOT see Company A invoice
        self.client.force_authenticate(user=self.procurement_user_b)
        proc_b_res = self.client.get("/api/v1/procurement/supplier-invoices/")
        self.assertEqual(proc_b_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(proc_b_res.data), 0)

        # 5. Procurement updates status
        self.client.force_authenticate(user=self.procurement_user)
        inv_id = allowed_res.data["id"]
        patch_res = self.client.patch(f"/api/v1/procurement/supplier-invoices/{inv_id}/", {
            "status": "processing",
            "procurement_comments": "Under review by team"
        })
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["status"], "processing")
        self.assertEqual(patch_res.data["procurement_comments"], "Under review by team")

    def test_expired_token(self):
        """Test expired invitation token handling."""
        self.client.force_authenticate(user=self.procurement_user)
        res = self.client.post("/api/v1/procurement/suppliers/invite/", {
            "email": "expired_supplier@example.com",
            "company_name": "Old Supplies"
        })
        token = res.data["invitation_token"]

        # Manually expire the invitation
        inv = SupplierInvitation.objects.get(token=token)
        inv.expires_at = timezone.now() - timedelta(days=1)
        inv.save()

        self.client.force_authenticate(user=None)
        detail_res = self.client.get(f"/api/v1/supplier/invitations/{token}/")
        self.assertEqual(detail_res.status_code, status.HTTP_200_OK)
        self.assertTrue(detail_res.data["is_expired"])

        # Attempt to accept -> should return 400
        accept_res = self.client.post(f"/api/v1/supplier/invitations/{token}/accept/", {
            "password": "ValidPassword123!"
        })
        self.assertEqual(accept_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(accept_res.data["code"], "expired")

    def test_invite_existing_non_supplier_user_succeeds(self):
        """Test that inviting an existing non-supplier user email succeeds without error."""
        # Create an existing user with an employee role
        existing_user = UserAccount.objects.create_user(
            email="existing_employee@external.com",
            password="ExistingPassword123!",
            role=UserAccount.Role.EMPLOYEE,
        )

        # Procurement invites this existing user as a supplier
        self.client.force_authenticate(user=self.procurement_user)
        res = self.client.post("/api/v1/procurement/suppliers/invite/", {
            "email": "existing_employee@external.com",
            "company_name": "Partner Supplies Ltd"
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        token = res.data["invitation_token"]

        # Verify invitation details recognize the existing user
        self.client.force_authenticate(user=None)
        detail_res = self.client.get(f"/api/v1/supplier/invitations/{token}/")
        self.assertEqual(detail_res.status_code, status.HTTP_200_OK)
        self.assertTrue(detail_res.data["is_existing_user"])

        # User accepts invitation
        accept_res = self.client.post(f"/api/v1/supplier/invitations/{token}/accept/", {})
        self.assertEqual(accept_res.status_code, status.HTTP_200_OK)

        # Verify user has SupplierProfile and active CompanySupplier
        self.assertTrue(SupplierProfile.objects.filter(user=existing_user).exists())
        cs = CompanySupplier.objects.get(company=self.company_a, supplier__user=existing_user)
        self.assertEqual(cs.status, CompanySupplier.Status.ACTIVE)

        # Verify user can access supplier company list
        self.client.force_authenticate(user=existing_user)
        comp_res = self.client.get("/api/v1/supplier/companies/")
        self.assertEqual(comp_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(comp_res.data), 1)
        self.assertEqual(comp_res.data[0]["company_name"], "Company Alpha Ltd")
