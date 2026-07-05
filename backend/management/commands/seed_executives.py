"""ایجاد سه مدیر ارشد."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from auth import roles
from auth.executives import EXECUTIVE_MANAGERS

User = get_user_model()
DEFAULT_PASSWORD = "Manager@1404"


class Command(BaseCommand):
    help = "Seed executive managers (sina, gholamreza, sepehr)"

    def handle(self, *args, **options):
        roles.ensure_roles()
        for username, full_name in EXECUTIVE_MANAGERS.items():
            user, created = User.objects.get_or_create(username=username, defaults={"email": f"{username}@local"})
            parts = full_name.split(" ", 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
            if created:
                user.set_password(DEFAULT_PASSWORD)
            user.is_staff = True
            user.save()
            roles.assign_role(user, roles.ADMIN)
            self.stdout.write(f"{'Created' if created else 'Updated'} {full_name} ({username})")

        self.stdout.write(self.style.SUCCESS(f"Default password for new accounts: {DEFAULT_PASSWORD}"))
