"""داده نمونه برای تست رده‌بندی کارکنان — فروشنده، فروش و حضور چندشعبه."""

from decimal import Decimal

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from auth import roles
from auth.branches import BRANCH_1, BRANCH_2
from backend.models import Customer, RoleDefinition, Seller, StaffAttendance, StaffProfile
from logic.jalali import date_to_jalali
from logic.role_definitions import seed_builtin_roles, sync_group_for_role
from logic.sales import record_sale

User = get_user_model()

DEMO_SELLERS = [
    {"username": "rank_ali", "full_name": "علی رضایی", "home_branch": BRANCH_1},
    {"username": "rank_sara", "full_name": "سارا محمدی", "home_branch": BRANCH_2},
    {"username": "rank_reza", "full_name": "رضا کریمی", "home_branch": BRANCH_1},
]

SELLER_ROLE = "demo_seller"
SELLER_PERMISSIONS = sorted(
    [
        "view_dashboard",
        "view_customers",
        "create_customer",
        "create_sale",
        "view_own_sales",
        "view_products",
        "self_check_in",
    ]
)

RANKING_VIEWER = "demo_ranking_viewer"
RANKING_PERMISSIONS = sorted(["view_dashboard", "view_sales", "view_employee_ranking"])


class Command(BaseCommand):
    help = "Seed demo sellers, sales and attendance for employee ranking"

    def handle(self, *args, **options):
        seed_builtin_roles()
        self._ensure_role(SELLER_ROLE, "فروشنده نمونه", SELLER_PERMISSIONS, needs_branch=True)
        self._ensure_role(RANKING_VIEWER, "ناظر رده‌بندی", RANKING_PERMISSIONS)

        from logic.membership import generate_membership_code

        customer, _ = Customer.objects.get_or_create(
            phone="09120001111",
            defaults={
                "full_name": "مشتری نمونه رده‌بندی",
                "membership_code": generate_membership_code(),
            },
        )

        today = timezone.localdate()
        jy, jm, jd = date_to_jalali(today)

        for idx, spec in enumerate(DEMO_SELLERS):
            user = self._ensure_user(spec["username"], spec["full_name"], SELLER_ROLE)
            profile, _ = StaffProfile.objects.get_or_create(
                user=user, defaults={"branch_id": spec["home_branch"]}
            )
            profile.branch_id = spec["home_branch"]
            profile.job_title = "فروشنده"
            profile.save()

            seller, _ = Seller.objects.get_or_create(
                user=user,
                defaults={"full_name": spec["full_name"], "branch_id": spec["home_branch"]},
            )
            seller.branch_id = spec["home_branch"]
            seller.full_name = spec["full_name"]
            seller.is_active = True
            seller.save()

            StaffAttendance.objects.update_or_create(
                seller=seller,
                date=today,
                defaults={
                    "status": "present",
                    "approval_status": "approved",
                    "work_branch_id": spec["home_branch"],
                    "check_in_at": timezone.now(),
                },
            )

            if idx == 0:
                yesterday = today - timedelta(days=1)
                StaffAttendance.objects.update_or_create(
                    seller=seller,
                    date=yesterday,
                    defaults={
                        "status": "present",
                        "approval_status": "approved",
                        "work_branch_id": BRANCH_2,
                        "check_in_at": timezone.now(),
                    },
                )

            record_sale(
                customer,
                Decimal(2_000_000 + idx * 500_000),
                payment_status="paid",
                recorded_by=user,
                branch=spec["home_branch"],
                description=f"فروش نمونه {spec['full_name']} — شعبه اصلی",
            )
            record_sale(
                customer,
                Decimal(1_200_000),
                payment_status="paid",
                recorded_by=user,
                branch=BRANCH_2 if spec["home_branch"] == BRANCH_1 else BRANCH_1,
                description=f"فروش نمونه {spec['full_name']} — شعبه دیگر",
            )

        viewer = self._ensure_user("rank_viewer", "ناظر رده‌بندی", RANKING_VIEWER)
        roles.assign_role(viewer, RANKING_VIEWER)

        self.stdout.write(self.style.SUCCESS("Demo ranking data ready."))
        self.stdout.write(f"  Jalali today: {jy}/{jm}/{jd}")
        self.stdout.write("  Login as rank_viewer / demo1234 to see ranking")
        self.stdout.write("  Sellers: rank_ali, rank_sara, rank_reza / demo1234")

    def _ensure_role(self, slug, label, permissions, needs_branch=False):
        RoleDefinition.objects.update_or_create(
            slug=slug,
            defaults={
                "label": label,
                "permissions": permissions,
                "is_builtin": False,
                "needs_branch": needs_branch,
                "color": "#6366f1",
                "sort_order": 50,
            },
        )
        sync_group_for_role(slug)

    def _ensure_user(self, username, full_name, role_slug):
        user, created = User.objects.get_or_create(username=username, defaults={"email": f"{username}@demo.local"})
        parts = full_name.split(" ", 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
        if created:
            user.set_password("demo1234")
        user.is_active = True
        user.save()
        roles.assign_role(user, role_slug)
        return user
