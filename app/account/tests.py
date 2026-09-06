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

