"""تست رده‌بندی کارکنان."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from auth import roles
from auth.branches import BRANCH_1, BRANCH_2
from backend.models import Customer, RoleDefinition, Sale, Seller, StaffAttendance, StaffProfile
from logic.jalali import date_to_jalali
from logic.role_definitions import seed_builtin_roles, sync_group_for_role

User = get_user_model()


class EmployeeRankingTest(TestCase):
    def setUp(self):
        seed_builtin_roles()
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

        self.seller_user = User.objects.create_user(username="seller1", password="secret123")
        roles.assign_role(self.seller_user, roles.PENDING)
        StaffProfile.objects.create(user=self.seller_user, branch=BRANCH_1, job_title="فروشنده")
        self.seller = Seller.objects.create(
            full_name="فروشنده یک",
            branch=BRANCH_1,
            user=self.seller_user,
        )

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        StaffAttendance.objects.create(
            seller=self.seller,
            date=today,
            status="present",
            approval_status="approved",
            work_branch=BRANCH_1,
        )
        StaffAttendance.objects.create(
            seller=self.seller,
            date=yesterday,
            status="present",
            approval_status="approved",
            work_branch=BRANCH_2,
        )

        customer = Customer.objects.create(full_name="C1", phone="09123334444")
        Sale.objects.create(
            customer=customer,
            amount=1000,
            final_amount=1000,
            paid_amount=1000,
            payment_status="paid",
            recorded_by=self.seller_user,
            branch=BRANCH_1,
            sold_at=timezone.now(),
        )
        Sale.objects.create(
            customer=customer,
            amount=500,
            final_amount=500,
            paid_amount=500,
            payment_status="paid",
            recorded_by=self.seller_user,
            branch=BRANCH_2,
            sold_at=timezone.now(),
        )

        self.jy, self.jm, self.jd = date_to_jalali(today)

    def test_ranking_returns_branch_breakdown(self):
        client = Client()
        client.login(username="viewer", password="secret123")
        resp = client.get(
            f"/api/sales/employee-ranking/?period=month&year={self.jy}&month={self.jm}"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        results = body["data"]["results"]
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row["home_branch"], BRANCH_1)
        self.assertEqual(len(row["sales_by_branch"]), 2)
        self.assertEqual(row["total_all_branches"], 1500)
        self.assertGreaterEqual(len(row["attendance_branches"]), 1)
