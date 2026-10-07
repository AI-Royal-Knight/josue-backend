from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from app.account.models import UserAccount, Company, Invitation
from app.project_admin.models import Project
from app.project_admin.views import ProjectRoleAssignmentsView
from app.procurement_department.views import SupplierInviteView
from app.account.views import AcceptInvitationView, AllowedInviteRolesView, LoginView


class SnagListFixesTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.company = Company.objects.create(
            company_name="Acme Construction Ltd",
            activate=True
        )
        self.admin = UserAccount.objects.create_user(
            email="admin@acme.com",
            password="AdminPassword123!",
            role=UserAccount.Role.ADMIN,
            company=self.company
        )
        self.project_admin = UserAccount.objects.create_user(
            email="projectadmin@acme.com",
            password="PAPassword123!",
            role=UserAccount.Role.PROJECT_ADMIN,
            company=self.company
        )
        self.procurement = UserAccount.objects.create_user(
            email="proc@acme.com",
            password="ProcPassword123!",
            role=UserAccount.Role.PROCUREMENT_DEPARTMENT,
            company=self.company
        )
        self.project = Project.objects.create(
            project_name="Bridge Overhaul",
            company=self.company,
            project_value=500000
        )

    def test_item1_managing_director_not_assigned_by_project_admin(self):
        """Managing Director must not be listed as a project-assignable role or accepted via POST."""
        req = self.factory.get(f'/api/v1/project-admin/projects/{self.project.pk}/roles/')
        force_authenticate(req, user=self.project_admin)
        res = ProjectRoleAssignmentsView.as_view()(req, pk=self.project.pk)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        role_keys = [r['role_key'] for r in res.data]
        self.assertNotIn(UserAccount.Role.MANAGING_DIRECTOR, role_keys)
        self.assertNotIn("managing_director", role_keys)

        # Attempt to assign Managing Director to project
        req_post = self.factory.post(
            f'/api/v1/project-admin/projects/{self.project.pk}/roles/',
            {'role_key': 'managing_director', 'user_ids': []},
            format='json'
        )
        force_authenticate(req_post, user=self.project_admin)
        res_post = ProjectRoleAssignmentsView.as_view()(req_post, pk=self.project.pk)
        self.assertEqual(res_post.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item2_supplier_invitation_acceptance_and_login(self):
        """Supplier account pre-created during invite must have credentials updated on accept and log in successfully."""
        # 1. Procurement invites supplier
        req_invite = self.factory.post(
            '/api/v1/procurement/suppliers/invite/',
            {'email': 'concrete@suppliers.com', 'company_name': 'Concrete Pro LLC'},
            format='json'
        )
        force_authenticate(req_invite, user=self.procurement)
        res_invite = SupplierInviteView.as_view()(req_invite)
        self.assertEqual(res_invite.status_code, status.HTTP_201_CREATED)

        inv = Invitation.objects.filter(email='concrete@suppliers.com').first()
        self.assertIsNotNone(inv)

        # 2. Supplier accepts invitation and chooses password
        req_accept = self.factory.post(
            '/api/v1/account/invitations/accept/',
            {
                'token': str(inv.token),
                'first_name': 'Bob',
                'last_name': 'Builder',
                'password': 'StrongPassword123!'
            },
            format='json'
        )
        res_accept = AcceptInvitationView.as_view()(req_accept)
        self.assertEqual(res_accept.status_code, status.HTTP_200_OK)

        # 3. Supplier logs in
        req_login = self.factory.post(
            '/api/v1/account/login/',
            {
                'email': 'concrete@suppliers.com',
                'password': 'StrongPassword123!'
            },
            format='json'
        )
        res_login = LoginView.as_view()(req_login)
        self.assertEqual(res_login.status_code, status.HTTP_200_OK)
        self.assertTrue(res_login.data.get('success'))
        self.assertIn('access_token', res_login.data)
        self.assertEqual(res_login.data['user']['role'], UserAccount.Role.SUPPLIER)

    def test_item3_management_roles_can_invite_app_users(self):
        """Project directors, contracts managers, managers, and supervisors must have employee in allowed invite roles."""
        roles_to_test = [
            UserAccount.Role.PROJECT_DIRECTOR,
            UserAccount.Role.CONTRACTS_MANAGER,
            UserAccount.Role.MANAGERS,
            "manager",
            UserAccount.Role.SUPERVISOR,
        ]

        for r in roles_to_test:
            user = UserAccount.objects.create_user(
                email=f"{r.replace(' ', '_')}@acme.com",
                password="TestPassword123!",
                role=r if r != "manager" else UserAccount.Role.MANAGERS,
                company=self.company
            )
            req = self.factory.get('/api/v1/account/invitations/allowed-roles/')
            force_authenticate(req, user=user)
            res = AllowedInviteRolesView.as_view()(req)
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            allowed_values = [item['value'] for item in res.data.get('allowed_roles', [])]
            self.assertIn(
                UserAccount.Role.EMPLOYEE,
                allowed_values,
                f"Role {r} should be allowed to invite mobile app user (employee)"
            )

    def test_project_admin_cannot_invite_employee(self):
        """Project Admin must NOT have employee in allowed invite roles and must be rejected on sending employee invite."""
        from app.account.views import SendInvitationView
        req = self.factory.get('/api/v1/account/invitations/allowed-roles/')
        force_authenticate(req, user=self.project_admin)
        res = AllowedInviteRolesView.as_view()(req)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        allowed_values = [item['value'] for item in res.data.get('allowed_roles', [])]
        self.assertNotIn(UserAccount.Role.EMPLOYEE, allowed_values)

        # Attempt to invite employee
        req_invite = self.factory.post(
            '/api/v1/account/invitations/send/',
            {'email': 'emp@acme.com', 'role': UserAccount.Role.EMPLOYEE},
            format='json'
        )
        force_authenticate(req_invite, user=self.project_admin)
        res_invite = SendInvitationView.as_view()(req_invite)
        self.assertEqual(res_invite.status_code, status.HTTP_403_FORBIDDEN)

    def test_two_factor_auth_login_flow(self):
        """When two_factor_enabled is True, login requires OTP sent to user's email."""
        from django.core.cache import cache
        from app.account.views import Verify2FAView, Resend2FAView

        user_2fa = UserAccount.objects.create_user(
            email="twofa_user@tresta.cloud",
            password="StrongPassword123!",
            first_name="Secure",
            last_name="User",
            role=UserAccount.Role.SUPER_ADMIN,
            two_factor_enabled=True,
        )

        # 1. Login attempt without OTP
        req_login = self.factory.post(
            '/api/v1/account/login/',
            {
                'email': 'twofa_user@tresta.cloud',
                'password': 'StrongPassword123!',
            },
            format='json'
        )
        res_login = LoginView.as_view()(req_login)
        self.assertEqual(res_login.status_code, status.HTTP_200_OK)
        self.assertTrue(res_login.data.get('requires_2fa'))
        self.assertEqual(res_login.data.get('email'), 'twofa_user@tresta.cloud')

        # Check OTP exists in cache
        cached_otp = cache.get("2fa_otp_twofa_user@tresta.cloud")
        self.assertIsNotNone(cached_otp)
        self.assertEqual(len(cached_otp), 6)

        # 2. Verify with wrong OTP
        req_verify_bad = self.factory.post(
            '/api/v1/account/login/verify-2fa/',
            {
                'email': 'twofa_user@tresta.cloud',
                'otp': '000000',
            },
            format='json'
        )
        res_verify_bad = Verify2FAView.as_view()(req_verify_bad)
        self.assertEqual(res_verify_bad.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Verify with correct OTP even if cache was completely cleared (simulating different Gunicorn worker)
        cache.clear()
        req_verify_good = self.factory.post(
            '/api/v1/account/login/verify-2fa/',
            {
                'email': 'twofa_user@tresta.cloud',
                'otp': cached_otp,
            },
            format='json'
        )
        res_verify_good = Verify2FAView.as_view()(req_verify_good)
        self.assertEqual(res_verify_good.status_code, status.HTTP_200_OK)
        self.assertTrue(res_verify_good.data.get('success'))
        self.assertIn('access_token', res_verify_good.data)
        self.assertEqual(res_verify_good.data['user']['email'], 'twofa_user@tresta.cloud')

        # Check OTP was consumed from DB
        user_2fa.refresh_from_db()
        self.assertIsNone(user_2fa.two_factor_otp)

    def test_two_factor_backup_otp_handling(self):
        """If a user re-triggers OTP or resends, the previous OTP is still valid within 5 minutes."""
        from django.core.cache import cache
        from app.account.views import Verify2FAView, Resend2FAView

        user_2fa = UserAccount.objects.create_user(
            email="backup_otp_user@tresta.cloud",
            password="StrongPassword123!",
            first_name="Secure",
            last_name="User",
            role=UserAccount.Role.SUPER_ADMIN,
            two_factor_enabled=True,
        )

        # 1. Login attempt 1 -> generates OTP 1
        req1 = self.factory.post(
            '/api/v1/account/login/',
            {'email': 'backup_otp_user@tresta.cloud', 'password': 'StrongPassword123!'},
            format='json'
        )
        res1 = LoginView.as_view()(req1)
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        user_2fa.refresh_from_db()
        otp1 = user_2fa.two_factor_otp

        # 2. Resend code -> generates OTP 2
        req2 = self.factory.post(
            '/api/v1/account/login/resend-2fa/',
            {'email': 'backup_otp_user@tresta.cloud'},
            format='json'
        )
        res2 = Resend2FAView.as_view()(req2)
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        user_2fa.refresh_from_db()
        otp2 = user_2fa.two_factor_otp
        self.assertNotEqual(otp1, otp2)
        self.assertEqual(user_2fa.two_factor_otp_backup, otp1)

        # 3. Clear cache to simulate another worker
        cache.clear()

        # User enters OTP 1 (from the first email) -> MUST STILL WORK WITHOUT WAITING!
        req_verify_old = self.factory.post(
            '/api/v1/account/login/verify-2fa/',
            {'email': 'backup_otp_user@tresta.cloud', 'otp': otp1},
            format='json'
        )
        res_verify_old = Verify2FAView.as_view()(req_verify_old)
        self.assertEqual(res_verify_old.status_code, status.HTTP_200_OK)
        self.assertTrue(res_verify_old.data.get('success'))



