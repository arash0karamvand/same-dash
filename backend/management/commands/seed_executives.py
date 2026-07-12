"""ایجاد مدیران ارشد با نقش سازمانی صحیح."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from auth import roles
from auth.executives import EXECUTIVE_MANAGERS
from auth.views import apply_user_access, ensure_staff_profile
from backend.models import OrgRank
from logic.role_definitions import seed_builtin_roles

User = get_user_model()
DEFAULT_PASSWORD = "Manager@1404"

EXECUTIVE_ROLE_MAP = {
    "gholamreza": roles.CEO,
    "sepehr": roles.ADMIN,
    "sina": roles.CO_CEO,
}

EXECUTIVE_ORG_RANKS = {
    "gholamreza": "مدیرعامل",
    "sepehr": "مدیر سیستم",
    "sina": "معاون مدیرعامل",
}


class Command(BaseCommand):
    help = "Seed executive managers with org roles (CEO, admin, co-CEO)"

    def handle(self, *args, **options):
        seed_builtin_roles()
        ceo_user = None

        for username, full_name in EXECUTIVE_MANAGERS.items():
            role_slug = EXECUTIVE_ROLE_MAP.get(username, roles.ADMIN)
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@local"},
            )
            parts = full_name.split(" ", 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
            if created:
                user.set_password(DEFAULT_PASSWORD)
            user.is_staff = role_slug in (roles.ADMIN, roles.CEO)
            user.save()

            apply_user_access(user, role_slug)
            rank_name = EXECUTIVE_ORG_RANKS.get(username)
            if rank_name:
                org_rank = OrgRank.objects.filter(name=rank_name, is_active=True).first()
                if org_rank:
                    profile = ensure_staff_profile(user)
                    profile.org_rank = org_rank
                    if username == "sepehr" and ceo_user:
                        profile.manager = ceo_user
                    elif username == "sina" and ceo_user:
                        profile.manager = ceo_user
                    profile.job_title = rank_name
                    profile.save()

            if username == "gholamreza":
                ceo_user = user

            self.stdout.write(
                f"{'Created' if created else 'Updated'} {username} role={role_slug}"
            )

        self.stdout.write(self.style.SUCCESS(f"Default password for new accounts: {DEFAULT_PASSWORD}"))
