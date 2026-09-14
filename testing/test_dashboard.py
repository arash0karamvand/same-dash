"""تست خلاصه داشبورد — فروش روز، هفته و ماه شمسی."""

from datetime import datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from auth import roles
from backend.models import Customer, Sale
from logic.dashboard import build_dashboard_summary
from logic.jalali import date_to_jalali
from logic.sales_day import jalali_week_bounds
from testing.role_helpers import ensure_legacy_test_roles
from django.contrib.auth import get_user_model

User = get_user_model()


class DashboardSummaryTest(TestCase):
    def setUp(self):
        ensure_legacy_test_roles()
        self.user = User.objects.create_user(username="dash", password="secret123")
        roles.assign_role(self.user, roles.SALES_MANAGER)
        self.customer = Customer.objects.create(full_name="Ali", phone="09120000111")

    def _aware(self, date, hh=12):
        tz = timezone.get_current_timezone()
        return timezone.make_aware(datetime(date.year, date.month, date.day, hh, 0), tz)

    def _sale(self, date, amount):
        return Sale.objects.create(
            customer=self.customer,
            amount=amount,
            final_amount=amount,
            sold_at=self._aware(date),
        )

    def test_day_week_month_sales_amounts(self):
        today = timezone.localdate()
        week_start, week_end = jalali_week_bounds(today)
        jy, jm, jd = date_to_jalali(today)
        days_since_saturday = (today.weekday() + 2) % 7
        saturday = today - timedelta(days=days_since_saturday)

        self._sale(today, 123_456_789)
        if days_since_saturday > 0:
            self._sale(saturday, 1_000)
        older = today - timedelta(days=40)
        self._sale(older, 50_000)

        data = build_dashboard_summary(self.user)
        self.assertEqual(data["sales_today"]["total"], 123_456_789)
        self.assertEqual(data["sales_today"]["count"], 1)
        self.assertGreaterEqual(data["sales_this_week"]["total"], 123_456_789)
        self.assertEqual(data["sales_this_week"]["start_jalali_year"], week_start[0])
        self.assertEqual(data["sales_this_week"]["end_jalali_day"], week_end[2])
        self.assertGreaterEqual(data["sales_this_month"]["total"], 123_456_789)
        self.assertEqual(data["sales_this_month"]["jalali_year"], jy)
        self.assertEqual(data["sales_this_month"]["jalali_month"], jm)
        self.assertEqual(data["total_sales_amount"], 123_456_789 + (1_000 if days_since_saturday > 0 else 0) + 50_000)
