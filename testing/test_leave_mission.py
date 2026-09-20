"""ارسال مرخصی و ماموریت از اعلان‌ها."""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from auth import roles
from auth.views import apply_user_access
from backend.models import Notification, StaffAttendance, Warehouse
from logic.attendance import check_in, today_leave_record, today_mission_record
from logic.attendance_settings import set_attendance_enforced, set_attendance_work_hours, work_day_hours
from logic.config_seed import seed_config_defaults
from logic.sale_attendance import evaluate_sale_attendance
from logic.sellers import ensure_seller_for_user
from logic.stock_locations import ensure_central_warehouse
from testing.role_helpers import ensure_legacy_test_roles

User = get_user_model()
PASSWORD = "secret123"


def parse(response):
    return json.loads(response.content)


class LeaveMissionDispatchTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        ensure_legacy_test_roles()
        set_attendance_enforced(True)
        set_attendance_work_hours("08:00", "16:00")
        ensure_central_warehouse()

        self.admin = User.objects.create_user(username="lmadmin", password=PASSWORD, first_name="مدیر")
        apply_user_access(self.admin, roles.ADMIN)
        self.expert = User.objects.create_user(username="lmexpert", password=PASSWORD, first_name="کارشناس")
        apply_user_access(self.expert, roles.SALES_EXPERT, "branch_1")
        self.seller = ensure_seller_for_user(self.expert, branch="branch_1")
        self.client = Client()

    def _login(self, user):
        self.assertTrue(self.client.login(username=user.username, password=PASSWORD))

    def _post(self, url, payload=None):
        return self.client.post(
            url,
            data=json.dumps(payload or {}),
            content_type="application/json",
        )

    def _put(self, url, payload=None):
        return self.client.put(
            url,
            data=json.dumps(payload or {}),
            content_type="application/json",
        )

    def test_recipients_flag_only_for_managers_portal(self):
        self._login(self.admin)
        data = parse(self.client.get("/api/notifications/recipients/"))["data"]
        self.assertTrue(data["can_send_leave_mission"])

        self.client.logout()
        self._login(self.expert)
        data = parse(self.client.get("/api/notifications/recipients/"))["data"]
        self.assertFalse(data["can_send_leave_mission"])

    def test_expert_cannot_send_leave(self):
        self._login(self.expert)
        resp = self._post(
            "/api/notifications/messages/",
            {
                "to_user_id": self.admin.id,
                "kind": "leave",
                "pay_type": "paid",
                "duration_unit": "days",
                "start_date": timezone.localdate().isoformat(),
                "end_date": timezone.localdate().isoformat(),
            },
        )
        self.assertEqual(resp.status_code, 403)

    def test_send_paid_daily_leave_blocks_checkin_and_sale(self):
        today = timezone.localdate()
        self._login(self.admin)
        sent = parse(
            self._post(
                "/api/notifications/messages/",
                {
                    "to_user_id": self.expert.id,
                    "kind": "leave",
                    "pay_type": "paid",
                    "duration_unit": "days",
                    "start_date": today.isoformat(),
                    "end_date": (today + timedelta(days=1)).isoformat(),
                    "body": "مرخصی تست",
                },
            )
        )
        self.assertTrue(sent["ok"])
        self.assertEqual(sent["data"]["action_type"], Notification.ACTION_ORG_LEAVE)
        self.assertEqual(sent["data"]["payload"]["pay_type"], "paid")
        self.assertEqual(
            StaffAttendance.objects.filter(seller=self.seller, status_ref_id="leave", is_deleted=False).count(),
            2,
        )
        leave = today_leave_record(self.seller)
        self.assertIsNotNone(leave)
        self.assertEqual(leave.leave_pay_type, "paid")
        self.assertIsNone(leave.leave_hours)

        with self.assertRaises(ValueError):
            check_in(self.seller, self.expert)
        state = evaluate_sale_attendance(self.expert)
        self.assertTrue(state["blocked"])
        self.assertIn("مرخصی", state["reason"])

        self.client.logout()
        self._login(self.expert)
        inbox = parse(self.client.get("/api/notifications/"))["data"]["results"]
        self.assertTrue(any(row["action_type"] == Notification.ACTION_ORG_LEAVE for row in inbox))

    def test_hourly_leave_allows_checkin_and_sale(self):
        today = timezone.localdate()
        self._login(self.admin)
        sent = parse(
            self._post(
                "/api/notifications/messages/",
                {
                    "to_user_id": self.expert.id,
                    "kind": "leave",
                    "pay_type": "unpaid",
                    "duration_unit": "hours",
                    "hours": 2,
                    "start_date": today.isoformat(),
                },
            )
        )
        self.assertTrue(sent["ok"])
        self.assertEqual(sent["data"]["payload"]["hours"], 2)
        self.assertIsNone(today_leave_record(self.seller))
        record = StaffAttendance.objects.get(seller=self.seller, date=today, status_ref_id="leave")
        self.assertEqual(record.leave_pay_type, "unpaid")
        self.assertEqual(record.leave_hours, Decimal("2.00"))

        checkin, _ = check_in(self.seller, self.expert, work_branch="branch_1")
        checkin.approval_status = "approved"
        checkin.approved_at = timezone.now()
        checkin.save()
        state = evaluate_sale_attendance(self.expert)
        self.assertFalse(state["blocked"])

    def test_hourly_leave_requires_work_hours(self):
        set_attendance_work_hours("", "")
        self.assertIsNone(work_day_hours())
        self._login(self.admin)
        resp = self._post(
            "/api/notifications/messages/",
            {
                "to_user_id": self.expert.id,
                "kind": "leave",
                "pay_type": "paid",
                "duration_unit": "hours",
                "hours": 2,
                "start_date": timezone.localdate().isoformat(),
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("ساعت کاری", parse(resp)["error"])

    def test_mission_to_warehouse_blocks_sale(self):
        warehouse = Warehouse.objects.filter(is_active=True).first()
        self.assertIsNotNone(warehouse)
        today = timezone.localdate()
        self._login(self.admin)
        sent = parse(
            self._post(
                "/api/notifications/messages/",
                {
                    "to_user_id": self.expert.id,
                    "kind": "mission",
                    "dest_kind": "warehouse",
                    "dest_code": str(warehouse.id),
                    "start_date": today.isoformat(),
                    "end_date": today.isoformat(),
                },
            )
        )
        self.assertTrue(sent["ok"])
        self.assertEqual(sent["data"]["action_type"], Notification.ACTION_ORG_MISSION)
        mission = today_mission_record(self.seller)
        self.assertIsNotNone(mission)
        self.assertEqual(mission.mission_dest_kind, "warehouse")
        state = evaluate_sale_attendance(self.expert)
        self.assertTrue(state["blocked"])
        self.assertIn("ماموریت", state["reason"])
        with self.assertRaises(ValueError):
            check_in(self.seller, self.expert)

    def test_mission_to_branch_allows_sale_without_checkin(self):
        today = timezone.localdate()
        self._login(self.admin)
        sent = parse(
            self._post(
                "/api/notifications/messages/",
                {
                    "to_user_id": self.expert.id,
                    "kind": "mission",
                    "dest_kind": "branch",
                    "dest_code": "branch_2",
                    "start_date": today.isoformat(),
                    "end_date": today.isoformat(),
                },
            )
        )
        self.assertTrue(sent["ok"])
        mission = today_mission_record(self.seller)
        self.assertEqual(mission.work_branch_id, "branch_2")
        state = evaluate_sale_attendance(self.expert)
        self.assertFalse(state["blocked"])
        self.assertEqual(state["work_branch"], "branch_2")
        self.assertTrue(state["present"])

    def test_mission_factory_and_outside(self):
        today = timezone.localdate()
        self._login(self.admin)
        factory = parse(
            self._post(
                "/api/notifications/messages/",
                {
                    "to_user_id": self.expert.id,
                    "kind": "mission",
                    "dest_kind": "factory",
                    "start_date": today.isoformat(),
                    "end_date": today.isoformat(),
                },
            )
        )
        self.assertTrue(factory["ok"])
        self.assertEqual(factory["data"]["payload"]["dest_kind"], "factory")
        StaffAttendance.objects.filter(seller=self.seller).delete()

        outside = parse(
            self._post(
                "/api/notifications/messages/",
                {
                    "to_user_id": self.expert.id,
                    "kind": "mission",
                    "dest_kind": "outside",
                    "dest_label": "دفتر مشتری",
                    "start_date": today.isoformat(),
                    "end_date": today.isoformat(),
                },
            )
        )
        self.assertTrue(outside["ok"])
        self.assertEqual(outside["data"]["payload"]["dest_label"], "دفتر مشتری")
        state = evaluate_sale_attendance(self.expert)
        self.assertTrue(state["blocked"])

    def test_saving_work_hours_keeps_enforced(self):
        self._login(self.admin)
        saved = parse(self._put("/api/config/attendance-settings/", {"work_start": "09:00", "work_end": "17:00"}))
        self.assertTrue(saved["ok"])
        self.assertEqual(saved["data"]["work_start"], "09:00")
        self.assertEqual(saved["data"]["work_end"], "17:00")
        self.assertEqual(saved["data"]["work_day_hours"], 8)
        self.assertTrue(saved["data"]["enforced"])
        toggled = parse(self._put("/api/config/attendance-settings/", {"enforced": False}))
        self.assertFalse(toggled["data"]["enforced"])
        self.assertEqual(toggled["data"]["work_start"], "09:00")
