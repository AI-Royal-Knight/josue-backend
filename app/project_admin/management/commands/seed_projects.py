import random
from django.core.management.base import BaseCommand
from app.project_admin.models import Project
from app.account.models import Company, UserAccount, RoleAssignment

class Command(BaseCommand):
    help = 'Seeds sample projects and assigns them to all users'

    def handle(self, *args, **kwargs):
        # 1. Get or create a default company
        company = Company.objects.first()
        if not company:
            company = Company.objects.create(company_name="Default Seed Company", status=Company.Status.ACTIVE)
            self.stdout.write(self.style.SUCCESS(f'Created default company: {company.company_name}'))

        # 2. Create sample projects
        project_names = [
            "Alpha Construction Site",
            "Beta Refurbishment",
            "Gamma Civil Works",
            "Delta Tower Extension"
        ]

        created_projects = []
        for name in project_names:
            project, created = Project.objects.get_or_create(
                project_name=name,
                defaults={
                    'company': company,
                    'job_code': f"JOB-{random.randint(1000, 9999)}",
                    'address': "123 Seed Street, London, UK",
                    'project_value': 1500000.00,
                    'material_estimate': 400000.00,
                    'labour_estimate': 300000.00,
                    'prelims_estimate': 100000.00,
                }
            )
            created_projects.append(project)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created project: {project.project_name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Project already exists: {project.project_name}'))

        # 3. Assign projects to everyone
        users = UserAccount.objects.all()
        for project in created_projects:
            for user in users:
                # Add to ManyToMany assigned_projects
                user.assigned_projects.add(project)
                
                # Create a RoleAssignment to ensure they show up correctly in the management list
                RoleAssignment.objects.get_or_create(
                    user=user,
                    role=user.role,
                    project=project,
                    defaults={'company': company}
                )

        self.stdout.write(self.style.SUCCESS(f'Successfully assigned {len(created_projects)} projects to {users.count()} users.'))
