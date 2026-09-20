"""تست رده‌بندی کارکنان."""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from auth import roles
from auth.branches import BRANCH_1, BRANCH_2
from backend.models import Customer, RoleDefinition, Sale, Seller, StaffAttendance, StaffProfile
from logic.config_seed import seed_config_defaults
from logic.jalali import date_to_jalali
from logic.ranking_settings import DEFAULT_WEIGHTS, set_ranking_weights
from logic.role_definitions import seed_builtin_roles, sync_group_for_role
from logic.sales import record_payment, record_sale

User = get_user_model()


def _json(resp):
    return resp.json()


class EmployeeRankingTest(TestCase):
    def setUp(self):
        seed_config_defaults()
        seed_builtin_roles()
        set_ranking_weights(DEFAULT_WEIGHTS)
        RoleDefinition.objects.update_or_create(
            slug="rank_viewer",
            defaults={
                "label": "ناظر",
                "permissions": ["view_employee_ranking", "view_dashboard"],
                "is_builtin": False,
            },
        )
        sync_group_for_role("rank_viewer")

        self.viewer = User.objects.create_user(username="viewer", password="secret123")
        roles.assign_role(self.viewer, "rank_viewer")

        self.admin = User.objects.create_user(username="boss", password="secret123")
        roles.assign_role(self.admin, roles.ADMIN)

        self.seller_user = User.objects.create_user(username="seller1", password="secret123")
        roles.assign_role(self.seller_user, roles.PENDING)
        StaffProfile.objects.create(user=self.seller_user, branch_id=BRANCH_1, job_title="فروشنده")
        self.seller = Seller.objects.create(
            full_name="فروشنده یک",
            branch_id=BRANCH_1,
            user=self.seller_user,
        )

        self.seller_user_2 = User.objects.create_user(username="seller2", password="secret123")
        roles.assign_role(self.seller_user_2, roles.PENDING)
        StaffProfile.objects.create(user=self.seller_user_2, branch_id=BRANCH_1, job_title="فروشنده")
        self.seller_2 = Seller.objects.create(
            full_name="فروشنده دو",
            branch_id=BRANCH_1,
            user=self.seller_user_2,
        )

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        now = timezone.now()
        StaffAttendance.objects.create(
            seller=self.seller,
            date=today,
            status="present",
            approval_status="approved",
            work_branch_id=BRANCH_1,
            check_in_at=now,
            check_out_at=now,
        )
        StaffAttendance.objects.create(
            seller=self.seller,
            date=yesterday,
            status="present",
            approval_status="approved",
            work_branch_id=BRANCH_2,
            check_in_at=now - timedelta(days=1),
            check_out_at=now - timedelta(days=1),
        )

        self.customer = Customer.objects.create(full_name="C1", phone="09123334444")
        Sale.objects.create(
            customer=self.customer,
            amount=1000,
            final_amount=1000,
            paid_amount=1000,
            payment_status="paid",
            recorded_by=self.seller_user,
            branch_id=BRANCH_1,
            sold_at=timezone.now(),
        )
        Sale.objects.create(
            customer=self.customer,
            amount=500,
            final_amount=500,
            paid_amount=500,
            payment_status="paid",
            recorded_by=self.seller_user,
            branch_id=BRANCH_2,
            sold_at=timezone.now(),
        )

        self.jy, self.jm, self.jd = date_to_jalali(today)
        self.client = Client()
        self.client.login(username="viewer", password="secret123")

    def _ranking(self):
        resp = self.client.get(
            f"/api/sales/employee-ranking/?period=month&year={self.jy}&month={self.jm}"
        )
        self.assertEqual(resp.status_code, 200)
        body = _json(resp)
        self.assertTrue(body["ok"])
        return body["data"]

    def test_ranking_returns_branch_breakdown(self):
        data = self._ranking()
        results = data["results"]
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row["home_branch"], BRANCH_1)
        self.assertEqual(len(row["sales_by_branch"]), 2)
        self.assertEqual(row["total_all_branches"], 1500)
        self.assertGreaterEqual(len(row["attendance_branches"]), 1)
        self.assertEqual(row["pre_delivery_paid"], 1500)
        self.assertEqual(row["total_discount"], 0)
        self.assertEqual(row["avg_discount_percent"], 0)
        self.assertEqual(data["weights"]["sales"], 100)

    def test_discount_percent_and_rial(self):
        Sale.objects.create(
            customer=self.customer,
            amount=2000,
            discount_type="percent",
            discount_value=10,
            discount=200,
            final_amount=1800,
            paid_amount=1800,
            payment_status="paid",
            recorded_by=self.seller_user,
            branch_id=BRANCH_1,
            sold_at=timezone.now(),
        )
        Sale.objects.create(
            customer=self.customer,
            amount=1000,
            discount_type="wallet",
            discount_value=100,
            discount=100,
            final_amount=900,
            paid_amount=900,
            payment_status="paid",
            recorded_by=self.seller_user,
            branch_id=BRANCH_1,
            sold_at=timezone.now(),
        )
        row = self._ranking()["results"][0]
        self.assertEqual(row["total_discount"], 200)
        # (200) / (1000+500+2000) = 5.71% — wallet sale excluded from denominator
        self.assertAlmostEqual(row["avg_discount_percent"], 5.71, places=2)

    def test_cancelled_sales_are_excluded(self):
        Sale.objects.create(
            customer=self.customer,
            amount=99999,
            final_amount=99999,
            paid_amount=99999,
            payment_status="paid",
            order_status=Sale.ORDER_STATUS_CANCELLED,
            recorded_by=self.seller_user,
            branch_id=BRANCH_1,
            sold_at=timezone.now(),
        )
        row = self._ranking()["results"][0]
        self.assertEqual(row["total_final"], 1500)

    def test_default_weights_keep_sales_order(self):
        Sale.objects.create(
            customer=self.customer,
            amount=800,
            discount_type="amount",
            discount=0,
            final_amount=800,
            paid_amount=800,
            payment_status="paid",
            recorded_by=self.seller_user_2,
            branch_id=BRANCH_1,
            sold_at=timezone.now(),
        )
        results = self._ranking()["results"]
        self.assertEqual(results[0]["user_id"], self.seller_user.id)
        self.assertEqual(results[1]["user_id"], self.seller_user_2.id)

    def test_discount_weight_changes_rank(self):
        Sale.objects.create(
            customer=self.customer,
            amount=2000,
            discount_type="amount",
            discount=400,
            final_amount=1600,
            paid_amount=1600,
            payment_status="paid",
            recorded_by=self.seller_user_2,
            branch_id=BRANCH_1,
            sold_at=timezone.now(),
        )
        set_ranking_weights({"sales": 0, "pre_delivery": 0, "discount_percent": 100, "discount_rial": 0})
        results = self._ranking()["results"]
        self.assertEqual(results[0]["user_id"], self.seller_user.id)
        self.assertEqual(results[1]["user_id"], self.seller_user_2.id)
        self.assertGreater(results[1]["avg_discount_percent"], results[0]["avg_discount_percent"])

    def test_pre_delivery_from_payment_journals(self):
        today = timezone.localdate()
        before = record_sale(
            self.customer,
            Decimal("2000"),
            paid_amount=700,
            payment_status="unpaid",
            order_kind=Sale.ORDER_KIND_DEPOSIT,
            delivery_date=today + timedelta(days=3),
        )
        before.recorded_by = self.seller_user_2
        before.save(update_fields=["recorded_by"])

        after = record_sale(
            self.customer,
            Decimal("3000"),
            paid_amount=0,
            payment_status="unpaid",
            order_kind=Sale.ORDER_KIND_DEPOSIT,
            delivery_date=today - timedelta(days=2),
        )
        after.recorded_by = self.seller_user
        after.save(update_fields=["recorded_by"])
        record_payment(after, Decimal("900"))

        set_ranking_weights({"sales": 0, "pre_delivery": 100, "discount_percent": 0, "discount_rial": 0})
        by_user = {row["user_id"]: row for row in self._ranking()["results"]}
        self.assertEqual(by_user[self.seller_user_2.id]["pre_delivery_paid"], 700)
        self.assertEqual(by_user[self.seller_user.id]["pre_delivery_paid"], 1500)
        self.assertEqual(self._ranking()["results"][0]["user_id"], self.seller_user.id)

    def test_ranking_settings_get_and_admin_put(self):
        resp = self.client.get("/api/config/ranking-settings/")
        self.assertEqual(resp.status_code, 200)
        body = _json(resp)
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["sales"], 100)

        denied = self.client.put(
            "/api/config/ranking-settings/",
            data=json.dumps({"sales": 40, "pre_delivery": 30, "discount_percent": 20, "discount_rial": 10}),
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

        admin_client = Client()
        admin_client.login(username="boss", password="secret123")
        saved = admin_client.put(
            "/api/config/ranking-settings/",
            data=json.dumps({"sales": 40, "pre_delivery": 30, "discount_percent": 20, "discount_rial": 10}),
            content_type="application/json",
        )
        self.assertEqual(saved.status_code, 200)
        payload = _json(saved)["data"]
        self.assertEqual(payload["sales"], 40)
        self.assertEqual(payload["pre_delivery"], 30)
        self.assertEqual(payload["discount_percent"], 20)
        self.assertEqual(payload["discount_rial"], 10)

        invalid = admin_client.put(
            "/api/config/ranking-settings/",
            data=json.dumps({"sales": 200}),
            content_type="application/json",
        )
        self.assertEqual(invalid.status_code, 400)
