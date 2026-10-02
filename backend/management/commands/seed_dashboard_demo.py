"""داده نمونه برای تست داشبورد — ویجت‌ها و فروش چندروزه."""

from decimal import Decimal
from datetime import datetime, timedelta
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from auth import roles
from auth.executives import EXECUTIVE_MANAGERS
from auth.permissions import has_permission, VIEW_DASHBOARD
from backend.models import Customer, DashboardWidget, Sale
from logic.membership import generate_membership_code
User = get_user_model()

DEMO_WIDGETS = [
    {
        "widget_type": DashboardWidget.WIDGET_STAT_CARD,
        "title": "فروش امروز",
        "size": DashboardWidget.SIZE_SMALL,
        "position": 0,
        "config": {"metric": "sales_today", "time_range": "month"},
    },
    {
        "widget_type": DashboardWidget.WIDGET_STAT_CARD,
        "title": "فروش هفتگی",
        "size": DashboardWidget.SIZE_SMALL,
        "position": 1,
        "config": {"metric": "sales_week", "time_range": "week"},
    },
    {
        "widget_type": DashboardWidget.WIDGET_STAT_CARD,
        "title": "فروش ماهانه",
        "size": DashboardWidget.SIZE_SMALL,
        "position": 2,
        "config": {"metric": "sales_month", "time_range": "month"},
    },
    {
        "widget_type": DashboardWidget.WIDGET_CHART_LINE,
        "title": "روند درآمد ۳۰ روز",
        "size": DashboardWidget.SIZE_WIDE,
        "position": 3,
        "config": {"metric": "revenue_trend", "time_range": "month"},
    },
    {
        "widget_type": DashboardWidget.WIDGET_CHART_BAR,
        "title": "مشتریان برتر",
        "size": DashboardWidget.SIZE_LARGE,
        "position": 4,
        "config": {"metric": "top_customers", "time_range": "month"},
    },
    {
        "widget_type": DashboardWidget.WIDGET_CHART_PIE,
        "title": "وضعیت موجودی",
        "size": DashboardWidget.SIZE_MEDIUM,
        "position": 5,
        "config": {"metric": "inventory_status"},
    },
]

DEMO_CUSTOMERS = [
    ("09121000001", "مشتری نمونه — آریا"),
    ("09121000002", "مشتری نمونه — نگین"),
    ("09121000003", "مشتری نمونه — پارسا"),
    ("09121000004", "مشتری نمونه — مهسا"),
    ("09121000005", "مشتری نمونه — کیان"),
]


class Command(BaseCommand):
    help = "Seed dashboard widgets and sample sales for dashboard testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            help="کاربری که ویجت‌ها برای او ساخته می‌شود (پیش‌فرض: اولین مدیر با view_dashboard)",
        )
        parser.add_argument(
            "--reset-widgets",
            action="store_true",
            help="حذف ویجت‌های قبلی همان کاربر قبل از seed",
        )
        parser.add_argument(
            "--sales-only",
            action="store_true",
            help="فقط فروش نمونه؛ بدون ساخت ویجت",
        )
        parser.add_argument(
            "--widgets-only",
            action="store_true",
            help="فقط ویجت؛ بدون فروش نمونه",
        )

    def handle(self, *args, **options):
        user = self._resolve_user(options.get("username"))
        if not user:
            self.stderr.write(
                self.style.ERROR(
                    "کاربری با دسترسی داشبورد پیدا نشد. --username بدهید یا seed_executives را اجرا کنید."
                )
            )
            return

        sales_count = 0
        widgets_count = 0

        if not options["widgets_only"]:
            sales_count = self._seed_sales(user)

        if not options["sales_only"]:
            if options["reset_widgets"]:
                deleted, _ = DashboardWidget.objects.filter(user=user).delete()
                self.stdout.write(f"  Removed {deleted} existing widget(s) for {user.username}")
            widgets_count = self._seed_widgets(user)

        self.stdout.write(self.style.SUCCESS("Dashboard demo data ready."))
        self.stdout.write(f"  User: {user.username} ({user.get_full_name() or user.username})")
        self.stdout.write(f"  Widgets: {widgets_count}")
        self.stdout.write(f"  Sample sales created/updated: {sales_count}")
        self.stdout.write("  Open the dashboard page while logged in as this user.")

    def _resolve_user(self, username):
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"User not found: {username}"))
                return None
            if not has_permission(user, VIEW_DASHBOARD) and not user.is_superuser:
                self.stderr.write(
                    self.style.WARNING(
                        f"User {username} may not see the dashboard (no view_dashboard)."
                    )
                )
            return user

        for uname in ("sepehr", "gholamreza", "sina"):
            user = User.objects.filter(username=uname).first()
            if user and (has_permission(user, VIEW_DASHBOARD) or user.is_superuser):
                return user

        for uname in EXECUTIVE_MANAGERS:
            user = User.objects.filter(username=uname).first()
            if user:
                return user

        user = User.objects.filter(is_superuser=True).first()
        if user:
            return user

        return (
            User.objects.filter(is_active=True)
            .order_by("id")
            .first()
        )

    def _seed_widgets(self, user):
        created = 0
        for spec in DEMO_WIDGETS:
            _, was_created = DashboardWidget.objects.update_or_create(
                user=user,
                title=spec["title"],
                defaults={
                    "widget_type": spec["widget_type"],
                    "config": spec["config"],
                    "position": spec["position"],
                    "size": spec["size"],
                },
            )
            if was_created:
                created += 1
        return len(DEMO_WIDGETS)

    def _seed_sales(self, user):
        tz = timezone.get_current_timezone()
        today = timezone.localdate()
        customers = []
        for phone, name in DEMO_CUSTOMERS:
            customer, _ = Customer.objects.get_or_create(
                phone=phone,
                defaults={
                    "full_name": name,
                    "membership_code": generate_membership_code(),
                },
            )
            if customer.full_name != name:
                customer.full_name = name
                customer.save(update_fields=["full_name"])
            customers.append(customer)

        amounts = [
            Decimal("4500000"),
            Decimal("8200000"),
            Decimal("1250000"),
            Decimal("15600000"),
            Decimal("3100000"),
            Decimal("9800000"),
        ]
        created = 0

        for day_offset in range(0, 35):
            sale_date = today - timedelta(days=day_offset)
            if day_offset > 0 and day_offset % 3 != 0 and day_offset != 7:
                continue
            per_day = 1 if day_offset > 14 else random.randint(1, 2)
            for n in range(per_day):
                customer = customers[(day_offset + n) % len(customers)]
                amount = amounts[(day_offset + n) % len(amounts)]
                sold_at = timezone.make_aware(
                    datetime(sale_date.year, sale_date.month, sale_date.day, 10 + n, 30, 0),
                    tz,
                )
                tag = f"dashboard-demo-{sale_date.isoformat()}-{n}"
                if Sale.objects.filter(description=tag).exists():
                    continue
                sale = Sale.objects.create(
                    customer=customer,
                    amount=amount,
                    final_amount=amount,
                    paid_amount=amount,
                    sold_at=sold_at,
                    description=tag,
                    recorded_by=user,
                    accounting_mode_ref_id=Sale.ACCOUNTING_MODE_MANUAL,
                )
                Sale.objects.filter(pk=sale.pk).update(created_at=sold_at)
                created += 1

        return created
