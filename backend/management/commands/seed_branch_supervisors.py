"""ایجاد سرپرستان شعبه — بی‌طرف (کمرد) و جوادی (پاسداران)."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from auth import roles
from auth.branch_supervisors import BRANCH_SUPERVISORS, DEFAULT_PASSWORD
from auth.views import apply_user_access, ensure_staff_profile
from backend.models import OrgRank
from logic.role_definitions import seed_builtin_roles
from logic.sellers import ensure_seller_for_user

User = get_user_model()


class Command(BaseCommand):
    help = "Seed branch supervisors: bitaraf (Kamard), javadi (Pasdaran)"

    def handle(self, *args, **options):
        seed_builtin_roles()
        org_rank = OrgRank.objects.filter(name="سرپرست شعبه", is_active=True).first()
        co_ceo = User.objects.filter(username="sina", is_active=True).first()

        for spec in BRANCH_SUPERVISORS:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={"email": f"{spec['username']}@local"},
            )
            parts = spec["full_name"].split(" ", 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
            if created:
                user.set_password(DEFAULT_PASSWORD)
            user.is_active = True
            user.save()

            apply_user_access(user, roles.BRANCH_SUPERVISOR, spec["branch"])
            profile = ensure_staff_profile(user, spec["branch"])
            profile.job_title = spec["job_title"]
            if org_rank:
                profile.org_rank = org_rank
            if co_ceo:
                profile.manager = co_ceo
            profile.save()

            ensure_seller_for_user(user, branch=spec["branch"])

            action = "ساخته شد" if created else "به‌روز شد"
            self.stdout.write(
                f"{spec['username']} branch={spec['branch']} {'created' if created else 'updated'}"
            )

        self.stdout.write(self.style.SUCCESS(f"Default password for new accounts: {DEFAULT_PASSWORD}"))
