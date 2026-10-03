from django.core.management.base import BaseCommand
from seed_demo_data import seed_demo_data


class Command(BaseCommand):
    help = "Seeds comprehensive demo data across all 15 roles and platform modules for testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset/cleanup demo data before seeding",
        )

    def handle(self, *args, **options):
        reset = options.get("reset", False)
        self.stdout.write(self.style.SUCCESS("Starting demo data seeder..."))
        seed_demo_data(reset=reset)
        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully!"))
