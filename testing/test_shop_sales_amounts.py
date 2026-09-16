"""تست مخفی‌کردن مبلغ فروش از کارکنان فروشگاه."""

import json
from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from auth import roles
from auth.branches import BRANCH_1
from backend.models import Customer, Sale, StaffProfile
from logic.jalali import date_to_jalali
from logic.role_definitions import seed_builtin_roles
from logic.sales_day import jalali_week_bounds
from logic.sellers import ensure_seller_for_user
from testing.role_helpers import ensure_legacy_test_roles

User = get_user_model()


def parse(response):
    return json.loads(response.content)


class ShopSalesAmountsTest(TestCase):
    def setUp(self):
        seed_builtin_roles()
        ensure_legacy_test_roles()
        self.customer = Customer.objects.create(full_name="خریدار", phone="09121112233")

        self.expert = User.objects.create_user(username="expert1", password="secret123")
        roles.assign_role(self.expert, roles.SALES_EXPERT)
        StaffProfile.objects.create(user=self.expert, branch_id=BRANCH_1)
        ensure_seller_for_user(self.expert, branch=BRANCH_1)

        self.supervisor = User.objects.create_user(username="supervisor1", password="secret123")
        roles.assign_role(self.supervisor, roles.BRANCH_SUPERVISOR)
        StaffProfile.objects.create(user=self.supervisor, branch_id=BRANCH_1)
        ensure_seller_for_user(self.supervisor, branch=BRANCH_1)

        self.manager = User.objects.create_user(username="mgr1", password="secret123")
        roles.assign_role(self.manager, roles.SALES_MANAGER)

        self.sale = Sale.objects.create(
            customer=self.customer,
            amount=1_250_000,
            final_amount=1_250_000,
            paid_amount=1_250_000,
            recorded_by=self.expert,
            branch_id=BRANCH_1,
            workflow_stage_id="pending_branch",
            sold_at=timezone.now(),
        )

    def _login(self, username):
        client = Client()
        client.login(username=username, password="secret123")
        return client

    def test_sales_expert_reports_hide_amounts(self):
        client = self._login("expert1")
        jy, jm, _ = date_to_jalali(timezone.localdate())

        monthly = parse(client.get(f"/api/sales/reports/monthly/?year={jy}&month={jm}"))
        self.assertTrue(monthly["ok"])
        data = monthly["data"]
        self.assertGreaterEqual(data["count"], 1)
        self.assertIsNone(data["total_final"])
        self.assertTrue(data["amounts_masked"])
        self.assertEqual(data.get("results") or [], [])

        daily = parse(client.get("/api/sales/reports/daily/"))
        self.assertTrue(daily["ok"])
        self.assertGreaterEqual(daily["data"]["count"], 1)
        self.assertIsNone(daily["data"]["total_final"])
        self.assertTrue(daily["data"]["amounts_masked"])

        weekly = parse(client.get("/api/sales/reports/weekly/"))
        self.assertTrue(weekly["ok"])
        self.assertGreaterEqual(weekly["data"]["count"], 1)
        self.assertIsNone(weekly["data"]["total_final"])
        self.assertTrue(weekly["data"]["amounts_masked"])

        breakdown = parse(client.get(f"/api/sales/reports/daily-breakdown/?year={jy}&month={jm}"))
        self.assertTrue(breakdown["ok"])
        self.assertIsNone(breakdown["data"]["total_final"])
        self.assertTrue(breakdown["data"]["amounts_masked"])
        for day in breakdown["data"]["days"]:
            self.assertIsNone(day["total_final"])
            self.assertGreaterEqual(day["count"], 1)

        listing = client.get("/api/sales/")
        self.assertEqual(listing.status_code, 403)

    def test_branch_supervisor_reports_hide_amounts_list_keeps_them(self):
        client = self._login("supervisor1")
        jy, jm, _ = date_to_jalali(timezone.localdate())

        monthly = parse(client.get(f"/api/sales/reports/monthly/?year={jy}&month={jm}"))
        self.assertTrue(monthly["ok"])
        self.assertGreaterEqual(monthly["data"]["count"], 1)
        self.assertIsNone(monthly["data"]["total_final"])
        self.assertTrue(monthly["data"]["amounts_masked"])
        self.assertEqual(monthly["data"].get("results") or [], [])

        daily_resp = client.get("/api/sales/reports/daily/")
        self.assertEqual(daily_resp.status_code, 200)
        daily = parse(daily_resp)
        self.assertTrue(daily["ok"])
        self.assertIsNone(daily["data"]["total_final"])

        listing = parse(client.get("/api/sales/"))
        self.assertTrue(listing["ok"])
        results = listing["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["final_amount"], 1_250_000)
        self.assertFalse(results[0]["amounts_masked"])
        self.assertIsNone(listing["data"]["summary"]["total_final"])
        self.assertTrue(listing["data"]["summary"]["amounts_masked"])

    def test_sales_manager_reports_keep_amounts(self):
        client = self._login("mgr1")
        jy, jm, _ = date_to_jalali(timezone.localdate())
        monthly = parse(client.get(f"/api/sales/reports/monthly/?year={jy}&month={jm}"))
        self.assertTrue(monthly["ok"])
        self.assertEqual(monthly["data"]["total_final"], 1_250_000)
        self.assertFalse(monthly["data"]["amounts_masked"])

    def test_weekly_report_saturday_to_friday(self):
        client = self._login("mgr1")
        tuesday = datetime(2026, 9, 15).date()
        start, end = jalali_week_bounds(tuesday)
        resp = parse(client.get(f"/api/sales/reports/weekly/?date={tuesday.isoformat()}"))
        self.assertTrue(resp["ok"])
        data = resp["data"]
        self.assertEqual(data["start_jalali_year"], start[0])
        self.assertEqual(data["start_jalali_month"], start[1])
        self.assertEqual(data["start_jalali_day"], start[2])
        self.assertEqual(data["end_jalali_year"], end[0])
        self.assertEqual(data["end_jalali_month"], end[1])
        self.assertEqual(data["end_jalali_day"], end[2])
