"""چارت سازمانی — جابه‌جایی زیردست، تیکت/مسئولیت و رنگ درجه."""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from auth import roles
from auth.permissions import VIEW_ORG_CHART
from backend.models import Customer, Notification, Sale, StaffProfile
from logic.config_seed import seed_config_defaults
from logic.notifications import (
    complete_org_responsibility,
    notification_sections_for_user,
    receipt_queryset,
    send_org_message,
)
from logic.org_chart import (
    REL_ANCESTOR,
    REL_DESCENDANT,
    build_org_chart,
    reassign_manager,
    relation_to,
)
from logic.ticket_grades import DEFAULT_TICKET_GRADE, get_ticket_grades, set_ticket_grades
from testing.test_notifications import PASSWORD, make_user

User = get_user_model()


def parse(response):
    return json.loads(response.content)


class OrgChartHierarchyTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        self.boss = User.objects.create_user(username="oboss", password=PASSWORD)
        roles.assign_role(self.boss, roles.ADMIN)
        self.mid = make_user("omid", "org_mid", [VIEW_ORG_CHART], label="میانی")
        self.leaf = make_user("oleaf", "org_leaf", [VIEW_ORG_CHART], label="زیردست")
        self.outsider = make_user("oout", "org_out", [VIEW_ORG_CHART], label="خارج")
        StaffProfile.objects.create(user=self.boss, branch_id="branch_1")
        StaffProfile.objects.create(user=self.mid, branch_id="branch_1", manager=self.boss)
        StaffProfile.objects.create(user=self.leaf, branch_id="branch_1", manager=self.mid)
        StaffProfile.objects.create(user=self.outsider, branch_id="branch_1")

    def test_relation_follows_manager_chain(self):
        self.assertEqual(relation_to(self.boss.id, self.leaf.id), REL_DESCENDANT)
        self.assertEqual(relation_to(self.leaf.id, self.boss.id), REL_ANCESTOR)
        self.assertEqual(relation_to(self.boss.id, self.outsider.id), "other")
        self.assertEqual(relation_to(self.boss.id, self.boss.id), "self")

    def test_reassign_sets_manager_and_rejects_cycle(self):
        reassign_manager(self.leaf.id, self.boss.id)
        self.leaf.staff_profile.refresh_from_db()
        self.assertEqual(self.leaf.staff_profile.manager_id, self.boss.id)

        with self.assertRaises(ValueError):
            reassign_manager(self.boss.id, self.leaf.id)
        with self.assertRaises(ValueError):
            reassign_manager(self.boss.id, self.boss.id)

        reassign_manager(self.leaf.id, None)
        self.leaf.staff_profile.refresh_from_db()
        self.assertIsNone(self.leaf.staff_profile.manager_id)

    def test_build_chart_includes_viewer_flags(self):
        data = build_org_chart(viewer=self.boss)
        self.assertEqual(data["me_id"], self.boss.id)
        self.assertTrue(data["can_edit"])
        self.assertTrue(any(node["id"] == self.leaf.id for node in data["flat"]))
        mid_data = build_org_chart(viewer=self.mid)
        self.assertFalse(mid_data["can_edit"])


class OrgMessageTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        self.boss = User.objects.create_user(username="mboss", password=PASSWORD)
        roles.assign_role(self.boss, roles.ADMIN)
        self.leaf = make_user("mleaf", "msg_leaf", [VIEW_ORG_CHART], label="زیردست")
        self.no_chart = make_user("mnone", "msg_none", ["view_products"], label="بدون چارت")
        StaffProfile.objects.create(user=self.boss, branch_id="branch_1")
        StaffProfile.objects.create(user=self.leaf, branch_id="branch_1", manager=self.boss)
        self.customer = Customer.objects.create(full_name="مشتری چارت", phone="09120000999")
        self.sale = Sale.objects.create(
            customer=self.customer,
            amount=50000,
            final_amount=50000,
            invoice_number="ORG-1",
        )

    def test_ticket_and_responsibility_allowed_in_any_direction(self):
        ticket = send_org_message(
            sender=self.boss,
            to_user_id=self.leaf.id,
            kind="ticket",
            title="گزارش روزانه",
            grade=1,
            sale_id=self.sale.id,
        )
        self.assertEqual(ticket.action_type, Notification.ACTION_ORG_TICKET)
        self.assertEqual(ticket.payload["color"], "#dc2626")
        self.assertTrue(receipt_queryset(self.leaf).filter(notification=ticket).exists())

        duty = send_org_message(
            sender=self.leaf,
            to_user_id=self.boss.id,
            kind="responsibility",
            title="پیگیری از مدیر",
        )
        self.assertEqual(duty.action_type, Notification.ACTION_ORG_RESPONSIBILITY)
        self.assertTrue(receipt_queryset(self.boss).filter(notification=duty).exists())

    def test_responsibility_down_and_complete(self):
        note = send_org_message(
            sender=self.boss,
            to_user_id=self.leaf.id,
            kind="responsibility",
            title="پیگیری سفارش",
            body="تا فردا",
        )
        self.assertEqual(note.action_type, Notification.ACTION_ORG_RESPONSIBILITY)
        self.assertTrue(receipt_queryset(self.leaf).filter(notification=note).exists())
        complete_org_responsibility(note, self.leaf)
        note.refresh_from_db()
        self.assertTrue(note.resolved_at)
        self.assertEqual(note.payload["status"], "done")

    def test_self_send_rejected(self):
        with self.assertRaises(ValueError):
            send_org_message(sender=self.boss, to_user_id=self.boss.id, kind="ticket", title="خودم")

    def test_org_section_visible_without_org_chart_permission(self):
        ids = [item["id"] for item in notification_sections_for_user(self.no_chart)]
        self.assertIn(Notification.SECTION_ORG, ids)
        send_org_message(
            sender=self.boss,
            to_user_id=self.no_chart.id,
            kind="ticket",
            title="برای همکار",
            sale_id=self.sale.id,
        )
        self.assertEqual(receipt_queryset(self.no_chart).count(), 1)


class OrgChartApiTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        self.boss = User.objects.create_user(username="aboss", password=PASSWORD)
        roles.assign_role(self.boss, roles.ADMIN)
        self.leaf = make_user("aleaf", "api_leaf", [VIEW_ORG_CHART], label="زیردست")
        self.viewer = make_user("aview", "api_view", [VIEW_ORG_CHART], label="مشاهده")
        StaffProfile.objects.create(user=self.boss, branch_id="branch_1")
        StaffProfile.objects.create(user=self.leaf, branch_id="branch_1", manager=self.boss)
        StaffProfile.objects.create(user=self.viewer, branch_id="branch_1")
        self.client = Client()

    def _login(self, user):
        self.assertTrue(self.client.login(username=user.username, password=PASSWORD))

    def _post(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    def test_get_chart_and_reassign(self):
        self._login(self.boss)
        data = parse(self.client.get("/api/org-chart/"))["data"]
        self.assertTrue(data["can_edit"])
        self.assertEqual(data["me_id"], self.boss.id)

        cycle = parse(self._post("/api/org-chart/reassign/", {"user_id": self.boss.id, "manager_id": self.leaf.id}))
        self.assertFalse(cycle["ok"])

        body = parse(self._post("/api/org-chart/reassign/", {"user_id": self.leaf.id, "manager_id": None}))
        self.assertTrue(body["ok"])
        self.leaf.staff_profile.refresh_from_db()
        self.assertIsNone(self.leaf.staff_profile.manager_id)

    def test_reassign_requires_manage_permission(self):
        self._login(self.viewer)
        body = parse(self._post("/api/org-chart/reassign/", {"user_id": self.leaf.id, "manager_id": self.viewer.id}))
        self.assertEqual(body["ok"], False)

    def test_send_message_and_complete_via_inbox(self):
        self._login(self.boss)
        people = parse(self.client.get("/api/notifications/recipients/"))["data"]["results"]
        self.assertTrue(any(row["id"] == self.leaf.id for row in people))
        sent = parse(
            self._post(
                "/api/notifications/messages/",
                {
                    "to_user_id": self.leaf.id,
                    "kind": "responsibility",
                    "title": "جمع‌آوری فاکتور",
                    "grade": 2,
                },
            )
        )
        self.assertTrue(sent["ok"])
        self.assertEqual(sent["data"]["payload"]["color"], "#f59e0b")

        self.client.logout()
        self._login(self.leaf)
        inbox = parse(self.client.get("/api/notifications/?section=org"))["data"]
        self.assertEqual(inbox["results"][0]["title"], "جمع‌آوری فاکتور")
        receipt_id = inbox["results"][0]["id"]
        done = parse(self._post(f"/api/notifications/{receipt_id}/act/", {}))
        self.assertTrue(done["ok"])
        self.assertTrue(done["data"]["resolved"])

    def test_upward_responsibility_allowed_via_notifications(self):
        self._login(self.leaf)
        body = parse(
            self._post(
                "/api/notifications/messages/",
                {"to_user_id": self.boss.id, "kind": "responsibility", "title": "به بالا"},
            )
        )
        self.assertTrue(body["ok"])


class TicketGradeSettingsTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        self.admin = User.objects.create_superuser("tadmin", "t@t.com", PASSWORD)
        roles.assign_role(self.admin, roles.ADMIN)
        self.client = Client()

    def test_defaults_and_update(self):
        data = get_ticket_grades()
        self.assertEqual(data["default_grade"], DEFAULT_TICKET_GRADE)
        self.assertEqual(len(data["grades"]), 4)
        updated = set_ticket_grades(
            grades=[{"grade": 3, "color": "#111111"}],
            default_grade=1,
        )
        self.assertEqual(updated["default_grade"], 1)
        self.assertEqual(updated["grades"][2]["color"], "#111111")
        self.assertEqual(updated["grades"][0]["color"], "#dc2626")

    def test_config_endpoint(self):
        self.assertTrue(self.client.login(username=self.admin.username, password=PASSWORD))
        data = parse(self.client.get("/api/config/ticket-grades/"))["data"]
        self.assertEqual(len(data["grades"]), 4)
        saved = parse(
            self.client.put(
                "/api/config/ticket-grades/",
                data=json.dumps(
                    {
                        "grades": [{"grade": 1, "color": "#abcdef"}],
                        "default_grade": 4,
                    }
                ),
                content_type="application/json",
            )
        )
        self.assertTrue(saved["ok"])
        self.assertEqual(saved["data"]["default_grade"], 4)
        self.assertEqual(saved["data"]["grades"][0]["color"], "#abcdef")
        bundle = parse(self.client.get("/api/config/"))["data"]
        self.assertEqual(bundle["ticket_grades"]["default_grade"], 4)
