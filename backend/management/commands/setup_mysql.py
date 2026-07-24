"""راه‌اندازی اولیه دیتابیس MySQL — تنظیمات، طرح حساب، ادمین و داده نمونه."""

import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from auth import roles
from logic.role_definitions import seed_builtin_roles
from logic.seed_defaults import seed_demo_materials, seed_system_defaults

User = get_user_model()
DEFAULT_ADMIN_PASSWORD = "admin1234"


class Command(BaseCommand):
    help = "Seed system defaults, admin user, executives and demo data for MySQL"

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_ADMIN_PASSWORD,
            help="رمز کاربر admin (پیش‌فرض: admin1234)",
        )
        parser.add_argument(
            "--no-demo",
            action="store_true",
            help="فقط تنظیمات و admin — بدون داده نمونه",
        )

    def handle(self, *args, **options):
        password = options["password"]
        skip_demo = options["no_demo"]

        seed_system_defaults()
        seed_builtin_roles()
        self.stdout.write("System defaults ready (config, roles, chart of accounts, loyalty levels).")

        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "first_name": "Admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin.first_name = admin.first_name or "Admin"
        admin.is_staff = True
        admin.is_superuser = True
        admin.set_password(password)
        admin.save()
        roles.assign_role(admin, roles.ADMIN)
        self.stdout.write(
            self.style.SUCCESS(
                f"User admin {'created' if created else 'updated'} — password: {password}"
            )
        )

        if skip_demo:
            self.stdout.write(self.style.SUCCESS("Setup complete (no demo data)."))
            return

        call_command("seed_executives", stdout=io.StringIO())
        call_command("seed_branch_supervisors", stdout=io.StringIO())
        call_command("seed_ranking_demo", stdout=io.StringIO())

        from logic.sellers import sync_seller_profiles

        sync_seller_profiles()
        seed_demo_materials(user=admin, link_products=True)
        self.stdout.write("Demo materials seeded (with inventory accounting in Rial).")

        self.stdout.write(self.style.SUCCESS("MySQL sample data loaded."))
