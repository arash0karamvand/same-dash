"""راه‌اندازی اولیه دیتابیس MySQL — نقش‌ها، ادمین و داده نمونه."""

import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from auth import roles
from logic.role_definitions import seed_builtin_roles

User = get_user_model()
DEFAULT_ADMIN_PASSWORD = "admin1234"


class Command(BaseCommand):
    help = "Seed roles, admin user, executives and ranking demo data for MySQL"

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_ADMIN_PASSWORD,
            help="رمز کاربر admin (پیش‌فرض: admin1234)",
        )

    def handle(self, *args, **options):
        password = options["password"]

        seed_builtin_roles()
        self.stdout.write("Builtin roles ready.")

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

        call_command("seed_executives", stdout=io.StringIO())
        call_command("seed_ranking_demo", stdout=io.StringIO())
        from logic.sellers import sync_seller_profiles

        sync_seller_profiles()

        self.stdout.write(self.style.SUCCESS("MySQL sample data loaded."))
