"""اعلان‌ها — دسترسی بخش، توزیع گیرندگان، وضعیت خواندن و API."""

import json
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.utils import timezone

from auth import roles
from auth.permissions import (
    APPROVE_SALE_ACCOUNTING,
    APPROVE_SALE_BRANCH,
    CREATE_SALE,
    MANAGE_ATTENDANCE,
    VIEW_ATTENDANCE,
    VIEW_FACTORY_ORDERS,
    VIEW_FACTORY_PRODUCTS,
    VIEW_PRODUCTS,
    VIEW_SALES,
    VIEW_SALES_SUMMARY,
    VIEW_WAREHOUSE_ORDERS,
)
from backend.models import Branch, Customer, Notification, NotificationReceipt, Sale, TicketMessage
from logic.attendance import check_in, request_branch_switch
from logic.branches import invalidate_branch_cache
from logic.config_seed import seed_config_defaults
from logic.notifications import (
    create_notification,
    mark_read,
    notification_sections_for_user,
    notify_branch_switch_request,
    receipt_queryset,
    receipt_to_dict,
    unread_count,
    users_with_permission,
)
from logic.sale_workflow import STAGE_PENDING_BRANCH
from logic.sellers import ensure_seller_for_user
from testing.role_helpers import ensure_test_role

User = get_user_model()

PASSWORD = "secret123"
HR_ROLE = "hr_manager"
EXPERT_PERMISSIONS = [CREATE_SALE, "view_own_sales", VIEW_PRODUCTS]


def parse(response):
    return json.loads(response.content)


def make_user(username, role, permissions, *, label=None, needs_branch=False):
    """کاربر با نقش سفارشی و مجموعه مجوز مشخص."""
    ensure_test_role(role, permissions, label=label or role, needs_branch=needs_branch)
    user = User.objects.create_user(username=username, password=PASSWORD)
    roles.assign_role(user, role)
    return user


def section_ids(user):
    return [item["id"] for item in notification_sections_for_user(user)]


def with_org(*sections):
    return set(sections) | {Notification.SECTION_ORG}


class NotificationAccessTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        self.manager = make_user(
            "nmanager", HR_ROLE, [MANAGE_ATTENDANCE, VIEW_ATTENDANCE], label="مدیر حضور"
        )
        self.expert = make_user(
            "nexpert", roles.SALES_EXPERT, EXPERT_PERMISSIONS, label="کارشناس فروش"
        )

    def test_attendance_notification_goes_to_managers_only(self):
        create_notification(
            section=Notification.SECTION_ATTENDANCE,
            title="تغییر شعبه",
            body="درخواست",
            target_permission=MANAGE_ATTENDANCE,
            created_by=self.expert,
        )
        self.assertGreater(unread_count(self.manager), 0)
        self.assertEqual(receipt_queryset(self.expert).count(), 0)
        self.assertTrue(receipt_queryset(self.manager).filter(notification__section="attendance").exists())

    def test_sections_follow_menu_access(self):
        self.assertIn(Notification.SECTION_ATTENDANCE, section_ids(self.manager))
        self.assertEqual(
            set(section_ids(self.expert)),
            with_org(Notification.SECTION_SALES, Notification.SECTION_PRODUCTS),
        )

    def test_manage_attendance_alone_unlocks_attendance_section(self):
        approver = make_user("napprover", "attendance_approver", [MANAGE_ATTENDANCE])
        self.assertEqual(section_ids(approver), [Notification.SECTION_ATTENDANCE, Notification.SECTION_ORG])

    def test_office_permission_unlocks_sales_and_warehouse(self):
        clerk = make_user("nclerk", "office_clerk", [APPROVE_SALE_ACCOUNTING])
        self.assertEqual(
            set(section_ids(clerk)),
            with_org(Notification.SECTION_SALES, Notification.SECTION_WAREHOUSE),
        )

    def test_warehouse_permission_unlocks_warehouse_section_only(self):
        keeper = make_user("nkeeper", "warehouse_keeper", [VIEW_WAREHOUSE_ORDERS])
        self.assertEqual(section_ids(keeper), [Notification.SECTION_WAREHOUSE, Notification.SECTION_ORG])

    def test_user_without_any_section_sees_nothing(self):
        outsider = User.objects.create_user(username="noutsider", password=PASSWORD)
        roles.assign_role(outsider, roles.PENDING)
        create_notification(
            section=Notification.SECTION_ATTENDANCE,
            title="اعلان",
            recipients=[outsider],
        )
        self.assertEqual(section_ids(outsider), [])
        self.assertEqual(NotificationReceipt.objects.filter(user=outsider).count(), 1)
        self.assertEqual(receipt_queryset(outsider).count(), 0)
        self.assertEqual(unread_count(outsider), 0)

    def test_recipient_outside_section_cannot_see_notification(self):
        create_notification(
            section=Notification.SECTION_ATTENDANCE,
            title="اعلان حضور",
            recipients=[self.expert],
        )
        self.assertEqual(NotificationReceipt.objects.filter(user=self.expert).count(), 1)
        self.assertEqual(receipt_queryset(self.expert).count(), 0)

    def test_sales_notification_visible_to_expert(self):
        create_notification(
            section=Notification.SECTION_SALES,
            title="سفارش جدید",
            recipients=[self.expert],
        )
        self.assertEqual(receipt_queryset(self.expert).count(), 1)
        self.assertEqual(unread_count(self.expert), 1)

    def test_products_permission_unlocks_products_section_only(self):
        cataloger = make_user("ncataloger", "product_viewer", [VIEW_PRODUCTS])
        self.assertEqual(section_ids(cataloger), [Notification.SECTION_PRODUCTS, Notification.SECTION_ORG])
        create_notification(
            section=Notification.SECTION_PRODUCTS,
            title="محصول جدید",
            recipients=[cataloger, self.manager],
        )
        self.assertEqual(receipt_queryset(cataloger).count(), 1)
        self.assertEqual(receipt_queryset(self.manager).count(), 0)

    def test_view_sales_unlocks_sales_section_only(self):
        clerk = make_user("nsalesview", "sales_viewer", [VIEW_SALES])
        self.assertEqual(section_ids(clerk), [Notification.SECTION_SALES, Notification.SECTION_ORG])

    def test_sales_summary_and_branch_approve_unlock_sales(self):
        summary = make_user("nsummary", "sales_summary", [VIEW_SALES_SUMMARY])
        approver = make_user("nbranchapp", "branch_approver", [APPROVE_SALE_BRANCH])
        self.assertEqual(section_ids(summary), [Notification.SECTION_SALES, Notification.SECTION_ORG])
        self.assertEqual(section_ids(approver), [Notification.SECTION_SALES, Notification.SECTION_ORG])

    def test_factory_products_unlock_products_section(self):
        factory = make_user("nfactoryprod", "factory_catalog", [VIEW_FACTORY_PRODUCTS])
        self.assertEqual(section_ids(factory), [Notification.SECTION_PRODUCTS, Notification.SECTION_ORG])

    def test_factory_orders_do_not_unlock_notification_sections(self):
        factory = make_user("nfactoryord", "factory_orders", [VIEW_FACTORY_ORDERS])
        self.assertEqual(section_ids(factory), [Notification.SECTION_ORG])

    def test_notifications_page_is_in_nav_tree_not_permission_matrix(self):
        from logic.module_catalog import module_tree_for_config, portal_modules_for_matrix

        tree = module_tree_for_config()
        self.assertTrue(tree)
        for portal in tree:
            keys = [mod["page_key"] for mod in portal["modules"]]
            self.assertIn("notifications", keys, portal["id"])
            note = next(mod for mod in portal["modules"] if mod["page_key"] == "notifications")
            self.assertEqual(note["menu_permission_codes"], [])
            self.assertEqual(note["section_permission_codes"], [])

        for assignable_only in (False, True):
            matrix = portal_modules_for_matrix(assignable_only=assignable_only)
            for portal in matrix:
                keys = [mod["page_key"] for mod in portal["modules"]]
                self.assertNotIn("notifications", keys, portal["id"])


class NotificationFanOutTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        self.manager = make_user(
            "fmanager", HR_ROLE, [MANAGE_ATTENDANCE, VIEW_ATTENDANCE], label="مدیر حضور"
        )
        self.other_manager = User.objects.create_user(username="fmanager2", password=PASSWORD)
        roles.assign_role(self.other_manager, HR_ROLE)
        self.expert = make_user(
            "fexpert", roles.SALES_EXPERT, EXPERT_PERMISSIONS, label="کارشناس فروش"
        )

    def test_users_with_permission_skips_inactive_accounts(self):
        self.assertEqual(
            set(users_with_permission(MANAGE_ATTENDANCE)),
            {self.manager, self.other_manager},
        )
        self.other_manager.is_active = False
        self.other_manager.save(update_fields=["is_active"])
        self.assertEqual(users_with_permission(MANAGE_ATTENDANCE), [self.manager])

    def test_target_permission_creates_receipt_per_permitted_user(self):
        note = create_notification(
            section=Notification.SECTION_ATTENDANCE,
            title="فن‌اوت",
            target_permission=MANAGE_ATTENDANCE,
        )
        self.assertEqual(
            set(note.receipts.values_list("user_id", flat=True)),
            {self.manager.pk, self.other_manager.pk},
        )

    def test_explicit_recipients_override_target_permission(self):
        note = create_notification(
            section=Notification.SECTION_ATTENDANCE,
            title="فقط یک نفر",
            target_permission=MANAGE_ATTENDANCE,
            recipients=[self.manager],
        )
        self.assertEqual(list(note.receipts.values_list("user_id", flat=True)), [self.manager.pk])
        self.assertEqual(note.target_permission, MANAGE_ATTENDANCE)

    def test_repeated_recipient_yields_single_receipt(self):
        note = create_notification(
            section=Notification.SECTION_ATTENDANCE,
            title="تکراری",
            recipients=[self.manager, self.manager],
        )
        self.assertEqual(note.receipts.count(), 1)

    def test_notification_without_recipients_has_no_receipts(self):
        note = create_notification(section=Notification.SECTION_SALES, title="بی‌گیرنده")
        self.assertEqual(note.receipts.count(), 0)
        self.assertEqual(note.payload, {})
        self.assertEqual(note.body, "")
        self.assertEqual(note.action_type, "")

    def test_empty_recipient_list_does_not_fan_out_by_permission(self):
        note = create_notification(
            section=Notification.SECTION_ATTENDANCE,
            title="لیست خالی",
            target_permission=MANAGE_ATTENDANCE,
            recipients=[],
        )
        self.assertEqual(note.receipts.count(), 0)

    def test_none_payload_and_body_are_normalized(self):
        note = create_notification(
            section=Notification.SECTION_SALES,
            title="نرمال",
            body=None,
            action_type=None,
            payload=None,
            target_permission=None,
        )
        self.assertEqual(note.body, "")
        self.assertEqual(note.action_type, "")
        self.assertEqual(note.payload, {})
        self.assertEqual(note.target_permission, "")


class NotificationStateTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        self.manager = make_user(
            "smanager", HR_ROLE, [MANAGE_ATTENDANCE, VIEW_ATTENDANCE], label="مدیر حضور"
        )
        self.manager.first_name = "زهرا"
        self.manager.last_name = "احمدی"
        self.manager.save(update_fields=["first_name", "last_name"])

    def _notify(self, title="اعلان", **kwargs):
        return create_notification(
            section=Notification.SECTION_ATTENDANCE,
            title=title,
            recipients=[self.manager],
            **kwargs,
        )

    def test_mark_read_then_unread_resets_timestamp(self):
        self._notify()
        receipt = receipt_queryset(self.manager).first()
        mark_read(receipt)
        receipt.refresh_from_db()
        self.assertTrue(receipt.is_read)
        self.assertIsNotNone(receipt.read_at)

        mark_read(receipt, read=False)
        receipt.refresh_from_db()
        self.assertFalse(receipt.is_read)
        self.assertIsNone(receipt.read_at)

    def test_unread_count_ignores_read_receipts(self):
        self._notify("اول")
        self._notify("دوم")
        self.assertEqual(unread_count(self.manager), 2)
        mark_read(receipt_queryset(self.manager).first())
        self.assertEqual(unread_count(self.manager), 1)

    def test_receipts_are_ordered_newest_first(self):
        self._notify("قدیمی")
        self._notify("جدید")
        titles = [row.notification.title for row in receipt_queryset(self.manager)]
        self.assertEqual(titles, ["جدید", "قدیمی"])

    def test_receipt_to_dict_exposes_section_label_and_author(self):
        note = self._notify(
            "عنوان",
            body="متن",
            action_type=Notification.ACTION_BRANCH_SWITCH,
            payload={"seller_id": 7},
            created_by=self.manager,
        )
        data = receipt_to_dict(receipt_queryset(self.manager).first())
        self.assertEqual(data["notification_id"], note.pk)
        self.assertEqual(data["section"], Notification.SECTION_ATTENDANCE)
        self.assertEqual(data["section_label"], "حضور و غیاب")
        self.assertEqual(data["title"], "عنوان")
        self.assertEqual(data["body"], "متن")
        self.assertEqual(data["action_type"], Notification.ACTION_BRANCH_SWITCH)
        self.assertEqual(data["payload"], {"seller_id": 7})
        self.assertFalse(data["is_read"])
        self.assertIsNone(data["read_at"])
        self.assertFalse(data["resolved"])
        self.assertIsNone(data["resolved_at"])
        self.assertEqual(data["created_by"], "زهرا احمدی")

    def test_receipt_to_dict_marks_resolved_notification(self):
        note = self._notify()
        note.resolved_at = timezone.now()
        note.resolved_by = self.manager
        note.save(update_fields=["resolved_at", "resolved_by"])
        data = receipt_to_dict(receipt_queryset(self.manager).first())
        self.assertTrue(data["resolved"])
        self.assertIsNotNone(data["resolved_at"])

    def test_receipt_to_dict_without_author(self):
        self._notify()
        data = receipt_to_dict(receipt_queryset(self.manager).first())
        self.assertEqual(data["created_by"], "")

    def test_receipt_to_dict_falls_back_to_username(self):
        author = make_user(
            "sauthor", HR_ROLE, [MANAGE_ATTENDANCE, VIEW_ATTENDANCE], label="مدیر حضور"
        )
        self._notify(created_by=author)
        data = receipt_to_dict(receipt_queryset(self.manager).first())
        self.assertEqual(data["created_by"], "sauthor")
        self.assertIsNotNone(data["created_at"])
        self.assertRegex(data["created_at"], r"^\d{4}-\d{2}-\d{2}T")


class BranchSwitchNotificationTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        Branch.objects.get_or_create(code="branch_1", defaults={"label": "کمرد", "is_active": True})
        Branch.objects.get_or_create(
            code="branch_2", defaults={"label": "پاسداران", "is_active": True}
        )
        invalidate_branch_cache()
        self.manager = make_user(
            "bmanager", HR_ROLE, [MANAGE_ATTENDANCE, VIEW_ATTENDANCE], label="مدیر حضور"
        )
        self.expert = make_user(
            "bexpert",
            roles.SALES_EXPERT,
            [CREATE_SALE, "self_check_in"],
            label="کارشناس فروش",
            needs_branch=True,
        )
        self.seller = ensure_seller_for_user(self.expert, branch="branch_1")

    def _approved_session(self):
        record, _ = check_in(self.seller, self.expert, work_branch="branch_1")
        record.approval_status = "approved"
        record.approved_at = timezone.now()
        record.save()
        return record

    def test_notify_branch_switch_builds_actionable_payload(self):
        record = self._approved_session()
        note = notify_branch_switch_request(
            self.seller, "branch_1", "branch_2", record, self.expert
        )
        self.assertEqual(note.section, Notification.SECTION_ATTENDANCE)
        self.assertEqual(note.action_type, Notification.ACTION_BRANCH_SWITCH)
        self.assertEqual(note.target_permission, MANAGE_ATTENDANCE)
        self.assertEqual(note.created_by, self.expert)
        self.assertEqual(
            note.payload,
            {
                "seller_id": self.seller.pk,
                "seller_name": self.seller.full_name,
                "from_branch": "branch_1",
                "to_branch": "branch_2",
                "attendance_id": record.pk,
                "status": "pending",
            },
        )
        self.assertIn("کمرد", note.body)
        self.assertIn("پاسداران", note.body)

    def test_request_branch_switch_notifies_attendance_managers(self):
        self._approved_session()
        note, _ = request_branch_switch(self.seller, self.expert, "branch_2")
        self.assertEqual(list(note.receipts.values_list("user_id", flat=True)), [self.manager.pk])
        self.assertEqual(unread_count(self.manager), 1)
        self.assertEqual(receipt_queryset(self.expert).count(), 0)

    def test_notify_branch_switch_falls_back_to_branch_codes(self):
        record = self._approved_session()
        note = notify_branch_switch_request(
            self.seller, "unknown_from", "unknown_to", record, self.expert
        )
        self.assertIn(self.seller.full_name, note.title)
        self.assertIn("unknown_from", note.body)
        self.assertIn("unknown_to", note.body)


class NotificationApiTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        Branch.objects.get_or_create(code="branch_1", defaults={"label": "کمرد", "is_active": True})
        Branch.objects.get_or_create(
            code="branch_2", defaults={"label": "پاسداران", "is_active": True}
        )
        invalidate_branch_cache()
        self.manager = make_user(
            "amanager",
            HR_ROLE,
            [MANAGE_ATTENDANCE, VIEW_ATTENDANCE, VIEW_SALES],
            label="مدیر حضور",
        )
        self.viewer = make_user("aviewer", "attendance_viewer", [VIEW_ATTENDANCE])
        self.expert = make_user(
            "aexpert",
            roles.SALES_EXPERT,
            [CREATE_SALE, "self_check_in", VIEW_PRODUCTS],
            label="کارشناس فروش",
            needs_branch=True,
        )
        self.seller = ensure_seller_for_user(self.expert, branch="branch_1")
        self.client = Client()

    def _login(self, user):
        self.assertTrue(self.client.login(username=user.username, password=PASSWORD))

    def _notify(self, section=Notification.SECTION_ATTENDANCE, title="اعلان", user=None, **kwargs):
        return create_notification(
            section=section, title=title, recipients=[user or self.manager], **kwargs
        )

    def _receipt_for(self, note, user):
        return NotificationReceipt.objects.get(notification=note, user=user)

    def _pending_switch(self):
        record, _ = check_in(self.seller, self.expert, work_branch="branch_1")
        record.approval_status = "approved"
        record.approved_at = timezone.now()
        record.save()
        note, record = request_branch_switch(self.seller, self.expert, "branch_2")
        return note, record

    def test_endpoints_require_authentication(self):
        for url in ("/api/notifications/", "/api/notifications/unread/"):
            self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.post("/api/notifications/read-all/").status_code, 401)
        self.assertEqual(self.client.post("/api/notifications/1/read/").status_code, 401)
        self.assertEqual(self.client.post("/api/notifications/1/act/").status_code, 401)

    def test_list_returns_sections_unread_count_and_pagination(self):
        for index in range(12):
            self._notify(title=f"اعلان {index}")
        self._login(self.manager)
        body = parse(self.client.get("/api/notifications/"))
        self.assertTrue(body["ok"])
        data = body["data"]
        self.assertEqual(data["total"], 12)
        self.assertEqual(data["offset"], 0)
        self.assertEqual(data["limit"], 10)
        self.assertEqual(len(data["results"]), 10)
        self.assertEqual(data["unread_count"], 12)
        self.assertIn(
            Notification.SECTION_ATTENDANCE, [s["id"] for s in data["sections"]]
        )
        self.assertEqual(data["results"][0]["title"], "اعلان 11")

    def test_list_filters_by_section_and_unread_flag(self):
        attendance = self._notify(title="حضور")
        self._notify(section=Notification.SECTION_SALES, title="فروش")
        self._login(self.manager)

        data = parse(self.client.get("/api/notifications/?section=attendance"))["data"]
        self.assertEqual([row["title"] for row in data["results"]], ["حضور"])

        mark_read(self._receipt_for(attendance, self.manager))
        data = parse(self.client.get("/api/notifications/?unread=1"))["data"]
        self.assertNotIn("حضور", [row["title"] for row in data["results"]])
        self.assertEqual(data["unread_count"], 1)

    def test_unread_endpoint_reports_count_and_sections(self):
        self._notify()
        self._login(self.manager)
        data = parse(self.client.get("/api/notifications/unread/"))["data"]
        self.assertEqual(data["unread_count"], 1)
        self.assertTrue(data["sections"])

    def test_read_endpoint_marks_and_unmarks(self):
        note = self._notify()
        receipt = self._receipt_for(note, self.manager)
        self._login(self.manager)

        body = parse(self.client.post(f"/api/notifications/{receipt.pk}/read/"))
        self.assertTrue(body["data"]["is_read"])

        body = parse(
            self.client.post(
                f"/api/notifications/{receipt.pk}/read/",
                data=json.dumps({"read": False}),
                content_type="application/json",
            )
        )
        self.assertFalse(body["data"]["is_read"])
        receipt.refresh_from_db()
        self.assertFalse(receipt.is_read)

    def test_read_endpoint_rejects_foreign_receipt(self):
        note = self._notify(user=self.viewer)
        receipt = self._receipt_for(note, self.viewer)
        self._login(self.manager)
        resp = self.client.post(f"/api/notifications/{receipt.pk}/read/")
        self.assertEqual(resp.status_code, 404)
        receipt.refresh_from_db()
        self.assertFalse(receipt.is_read)

    def test_read_all_clears_unread_for_visible_sections(self):
        attendance = self._notify(title="یک")
        sales = self._notify(section=Notification.SECTION_SALES, title="دو")
        hidden = self._notify(section=Notification.SECTION_PRODUCTS, title="پنهان")
        self._login(self.manager)
        body = parse(self.client.post("/api/notifications/read-all/"))
        self.assertEqual(body["data"]["unread_count"], 0)
        self.assertEqual(unread_count(self.manager), 0)
        for note in (attendance, sales):
            self.assertTrue(self._receipt_for(note, self.manager).is_read)
        self.assertFalse(self._receipt_for(hidden, self.manager).is_read)

    def test_act_approves_branch_switch(self):
        note, old_record = self._pending_switch()
        receipt = self._receipt_for(note, self.manager)
        self._login(self.manager)

        body = parse(self.client.post(f"/api/notifications/{receipt.pk}/act/"))
        self.assertTrue(body["ok"])
        self.assertTrue(body["data"]["is_read"])
        self.assertTrue(body["data"]["resolved"])

        note.refresh_from_db()
        old_record.refresh_from_db()
        self.assertIsNotNone(note.resolved_at)
        self.assertEqual(note.resolved_by, self.manager)
        self.assertEqual(note.payload["status"], "approved")
        self.assertIsNotNone(old_record.check_out_at)

    def test_act_twice_fails(self):
        note, _ = self._pending_switch()
        receipt = self._receipt_for(note, self.manager)
        self._login(self.manager)
        self.client.post(f"/api/notifications/{receipt.pk}/act/")
        resp = self.client.post(f"/api/notifications/{receipt.pk}/act/")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(parse(resp)["ok"])

    def test_act_requires_manage_attendance(self):
        record, _ = check_in(self.seller, self.expert, work_branch="branch_1")
        record.approval_status = "approved"
        record.approved_at = timezone.now()
        record.save()
        note = notify_branch_switch_request(
            self.seller, "branch_1", "branch_2", record, self.expert
        )
        NotificationReceipt.objects.create(notification=note, user=self.viewer)
        receipt = self._receipt_for(note, self.viewer)
        self._login(self.viewer)
        resp = self.client.post(f"/api/notifications/{receipt.pk}/act/")
        self.assertEqual(resp.status_code, 403)
        note.refresh_from_db()
        self.assertIsNone(note.resolved_at)

    def test_act_on_plain_notification_fails(self):
        note = self._notify(title="بدون اقدام")
        receipt = self._receipt_for(note, self.manager)
        self._login(self.manager)
        resp = self.client.post(f"/api/notifications/{receipt.pk}/act/")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(parse(resp)["error"], "این اعلان اقدام قابل انجام ندارد.")

    def test_list_respects_offset_and_limit(self):
        for index in range(5):
            self._notify(title=f"اعلان {index}")
        self._login(self.manager)
        data = parse(self.client.get("/api/notifications/?offset=2&limit=2"))["data"]
        self.assertEqual(data["total"], 5)
        self.assertEqual(data["offset"], 2)
        self.assertEqual(data["limit"], 2)
        self.assertEqual([row["title"] for row in data["results"]], ["اعلان 2", "اعلان 1"])

    def test_list_unread_count_is_global_when_filtering_section(self):
        self._notify(title="حضور")
        self._notify(section=Notification.SECTION_SALES, title="فروش")
        self._login(self.manager)
        data = parse(self.client.get("/api/notifications/?section=attendance"))["data"]
        self.assertEqual([row["title"] for row in data["results"]], ["حضور"])
        self.assertEqual(data["unread_count"], 2)

    def test_list_unknown_section_is_empty(self):
        self._notify()
        self._login(self.manager)
        data = parse(self.client.get("/api/notifications/?section=products"))["data"]
        self.assertEqual(data["results"], [])
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["unread_count"], 1)

    def test_read_and_act_missing_receipt_return_404(self):
        self._login(self.manager)
        for suffix in ("read", "act"):
            resp = self.client.post(f"/api/notifications/99999/{suffix}/")
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(parse(resp)["error"], "اعلان یافت نشد.")

    def test_act_rejects_foreign_receipt(self):
        note, _ = self._pending_switch()
        receipt = self._receipt_for(note, self.manager)
        self._login(self.expert)
        resp = self.client.post(f"/api/notifications/{receipt.pk}/act/")
        self.assertEqual(resp.status_code, 404)
        note.refresh_from_db()
        self.assertIsNone(note.resolved_at)

    def test_read_all_does_not_mark_other_users(self):
        note = create_notification(
            section=Notification.SECTION_ATTENDANCE,
            title="مشترک",
            recipients=[self.manager, self.viewer],
        )
        self._login(self.manager)
        parse(self.client.post("/api/notifications/read-all/"))
        self.assertTrue(self._receipt_for(note, self.manager).is_read)
        self.assertFalse(self._receipt_for(note, self.viewer).is_read)

    def test_read_empty_body_defaults_to_read(self):
        note = self._notify()
        receipt = self._receipt_for(note, self.manager)
        self._login(self.manager)
        body = parse(self.client.post(f"/api/notifications/{receipt.pk}/read/"))
        self.assertTrue(body["data"]["is_read"])
        self.assertIsNotNone(body["data"]["read_at"])

    def test_wrong_methods_are_rejected(self):
        self._login(self.manager)
        self.assertEqual(self.client.post("/api/notifications/").status_code, 405)
        self.assertEqual(self.client.get("/api/notifications/read-all/").status_code, 405)

    def test_pending_user_cannot_use_api(self):
        outsider = User.objects.create_user(username="apending", password=PASSWORD)
        roles.assign_role(outsider, roles.PENDING)
        self._login(outsider)
        resp = self.client.get("/api/notifications/")
        self.assertEqual(resp.status_code, 403)

    def test_act_unknown_action_type_fails(self):
        note = self._notify(title="ناشناخته", action_type="something_else")
        receipt = self._receipt_for(note, self.manager)
        self._login(self.manager)
        resp = self.client.post(f"/api/notifications/{receipt.pk}/act/")
        self.assertEqual(resp.status_code, 400)

    def test_act_missing_seller_returns_400(self):
        note = create_notification(
            section=Notification.SECTION_ATTENDANCE,
            title="فروشنده نامعتبر",
            action_type=Notification.ACTION_BRANCH_SWITCH,
            payload={"seller_id": 99999, "status": "pending"},
            recipients=[self.manager],
        )
        receipt = self._receipt_for(note, self.manager)
        self._login(self.manager)
        resp = self.client.post(f"/api/notifications/{receipt.pk}/act/")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(parse(resp)["error"], "فروشنده یافت نشد.")


class NotificationModelTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        self.user = make_user(
            "muser", HR_ROLE, [MANAGE_ATTENDANCE, VIEW_ATTENDANCE], label="مدیر حضور"
        )

    def test_receipt_unique_per_user(self):
        note = create_notification(
            section=Notification.SECTION_ATTENDANCE,
            title="یکتا",
            recipients=[self.user],
        )
        with self.assertRaises(IntegrityError):
            NotificationReceipt.objects.create(notification=note, user=self.user)

    def test_notification_str_is_title(self):
        note = create_notification(section=Notification.SECTION_SALES, title="عنوان نمایش")
        self.assertEqual(str(note), "عنوان نمایش")


class TicketRecipientDepartmentTests(TestCase):
    def setUp(self):
        seed_config_defaults()

    def test_recipient_shows_department_and_job(self):
        from auth.views import apply_user_access
        from logic.notifications import list_message_recipients

        sender = User.objects.create_user(username="tsender", password=PASSWORD)
        apply_user_access(sender, roles.ADMIN)
        target = User.objects.create_user(username="ttarget", password=PASSWORD, first_name="علی")
        apply_user_access(target, roles.BRANCH_SUPERVISOR, "branch_1")
        people = list_message_recipients(sender)
        row = next(item for item in people if item["id"] == target.id)
        self.assertEqual(row["department"], "shop")
        self.assertEqual(row["department_label"], "فروشگاه")
        self.assertEqual(row["role_label"], "سرپرست شعبه")
        self.assertEqual(row["hint"], "فروشگاه / سرپرست شعبه")


class InvoiceTicketThreadTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        from auth.views import apply_user_access

        self.admin = User.objects.create_user(username="tadmin", password=PASSWORD, first_name="مدیر")
        apply_user_access(self.admin, roles.ADMIN)
        self.supervisor = User.objects.create_user(
            username="tsup", password=PASSWORD, first_name="سرپرست"
        )
        apply_user_access(self.supervisor, roles.BRANCH_SUPERVISOR, "branch_1")
        self.expert = User.objects.create_user(username="texp", password=PASSWORD, first_name="کارشناس")
        apply_user_access(self.expert, roles.SALES_EXPERT, "branch_1")
        self.office_a = User.objects.create_user(username="tofficea", password=PASSWORD, first_name="اداری‌یک")
        apply_user_access(self.office_a, roles.ACCOUNTING_FINANCE)
        self.office_b = User.objects.create_user(username="tofficeb", password=PASSWORD, first_name="اداری‌دو")
        apply_user_access(self.office_b, roles.ACCOUNTING_FINANCE)
        self.customer = Customer.objects.create(full_name="خریدار تیکت", phone="09123334455")
        self.client = Client()

    def _login(self, user):
        self.assertTrue(self.client.login(username=user.username, password=PASSWORD))

    def _post(self, url, payload=None):
        return self.client.post(
            url,
            data=json.dumps(payload or {}),
            content_type="application/json",
        )

    def _aware(self, day, hh=12):
        tz = timezone.get_current_timezone()
        return timezone.make_aware(datetime(day.year, day.month, day.day, hh, 0), tz)

    def _sale(self, invoice, *, stage=STAGE_PENDING_BRANCH, branch="branch_1", sold_at=None, amount=100000):
        return Sale.objects.create(
            customer=self.customer,
            amount=amount,
            final_amount=amount,
            invoice_number=invoice,
            workflow_stage_id=stage,
            branch_id=branch,
            sold_at=sold_at or timezone.now(),
        )

    def test_invoice_picker_only_returns_visible_sales(self):
        visible = self._sale("1403-12")
        hidden_other_branch = self._sale("1403-99", branch="branch_2")
        self._login(self.supervisor)
        data = parse(self.client.get("/api/notifications/invoices/"))["data"]["results"]
        ids = [row["id"] for row in data]
        self.assertIn(visible.id, ids)
        self.assertNotIn(hidden_other_branch.id, ids)
        self.assertTrue(all(row.get("invoice_number") for row in data))

        self.client.logout()
        self._login(self.expert)
        expert_data = parse(self.client.get("/api/notifications/invoices/"))["data"]["results"]
        self.assertEqual(expert_data, [])

        self.client.logout()
        self._login(self.admin)
        admin_ids = [row["id"] for row in parse(self.client.get("/api/notifications/invoices/"))["data"]["results"]]
        self.assertIn(visible.id, admin_ids)
        self.assertIn(hidden_other_branch.id, admin_ids)

    def test_invoice_picker_search_and_date_and_limit(self):
        today = timezone.localdate()
        older = today - timedelta(days=5)
        match = self._sale("1403-SEARCH", sold_at=self._aware(today))
        self._sale("1403-OTHER", sold_at=self._aware(today))
        self._sale("1403-OLD", sold_at=self._aware(older))
        for index in range(12):
            self._sale(f"1403-L{index:02d}", sold_at=self._aware(today, hh=min(10 + index, 20)))

        self._login(self.admin)
        found = parse(self.client.get("/api/notifications/invoices/?search=SEARCH"))["data"]["results"]
        self.assertEqual([row["id"] for row in found], [match.id])

        by_date = parse(self.client.get(f"/api/notifications/invoices/?date={older.isoformat()}"))["data"]["results"]
        self.assertEqual([row["invoice_number"] for row in by_date], ["1403-OLD"])

        limited = parse(self.client.get("/api/notifications/invoices/?limit=10"))["data"]["results"]
        self.assertLessEqual(len(limited), 10)

    def test_send_to_department_first_get_claims_and_others_404(self):
        sale = self._sale("1403-DEP")
        self._login(self.supervisor)
        sent = parse(
            self._post(
                "/api/notifications/messages/",
                {
                    "to_department": "office",
                    "kind": "ticket",
                    "title": "اصلاح آدرس",
                    "body": "لطفاً بررسی شود",
                    "sale_id": sale.id,
                },
            )
        )
        self.assertTrue(sent["ok"])
        note_id = sent["data"]["id"]
        self.assertEqual(sent["data"]["payload"]["invoice_number"], "1403-DEP")
        self.assertIsNone(sent["data"]["payload"]["claimed_by_id"])
        self.assertTrue(NotificationReceipt.objects.filter(notification_id=note_id, user=self.office_a).exists())
        self.assertTrue(NotificationReceipt.objects.filter(notification_id=note_id, user=self.office_b).exists())

        sent_box = parse(self.client.get("/api/notifications/?box=sent"))["data"]["results"]
        self.assertEqual(sent_box[0]["notification_id"], note_id)

        self.client.logout()
        self._login(self.office_a)
        opened = parse(self.client.get(f"/api/notifications/{note_id}/"))
        self.assertTrue(opened["ok"])
        self.assertEqual(opened["data"]["payload"]["claimed_by_id"], self.office_a.id)
        self.assertFalse(NotificationReceipt.objects.filter(notification_id=note_id, user=self.office_b).exists())

        self.client.logout()
        self._login(self.office_b)
        missing = self.client.get(f"/api/notifications/{note_id}/")
        self.assertEqual(missing.status_code, 404)
        inbox = parse(self.client.get("/api/notifications/"))["data"]["results"]
        self.assertFalse(any(row["notification_id"] == note_id for row in inbox))

    def test_close_reopen_from_both_sides_and_reply(self):
        sale = self._sale("1403-CL")
        self._login(self.supervisor)
        note_id = parse(
            self._post(
                "/api/notifications/messages/",
                {
                    "to_user_id": self.office_a.id,
                    "kind": "ticket",
                    "title": "پیگیری",
                    "body": "شروع",
                    "sale_id": sale.id,
                },
            )
        )["data"]["id"]

        closed = parse(self._post(f"/api/notifications/{note_id}/act/", {"action": "close"}))
        self.assertTrue(closed["ok"])
        self.assertEqual(closed["data"]["payload"]["status"], "closed")
        self.assertTrue(closed["data"]["resolved"])

        self.client.logout()
        self._login(self.office_a)
        reopened = parse(self._post(f"/api/notifications/{note_id}/act/", {"action": "reopen"}))
        self.assertTrue(reopened["ok"])
        self.assertEqual(reopened["data"]["payload"]["status"], "open")

        reply = parse(self._post(f"/api/notifications/{note_id}/replies/", {"body": "انجام شد"}))
        self.assertTrue(reply["ok"])
        self.assertEqual(TicketMessage.objects.filter(notification_id=note_id).count(), 1)
        thread = parse(self.client.get(f"/api/notifications/{note_id}/"))["data"]
        self.assertEqual(len(thread["messages"]), 2)
        self.assertTrue(thread["messages"][0]["is_initial"])
        self.assertEqual(thread["messages"][1]["body"], "انجام شد")

        self.client.logout()
        self._login(self.office_b)
        denied = self._post(f"/api/notifications/{note_id}/replies/", {"body": "فضولی"})
        self.assertEqual(denied.status_code, 404)

    def test_admin_box_all_and_read_only_replies(self):
        sale = self._sale("1403-ALL")
        self._login(self.supervisor)
        note_id = parse(
            self._post(
                "/api/notifications/messages/",
                {
                    "to_user_id": self.office_a.id,
                    "kind": "ticket",
                    "title": "گفتگوی ادمین",
                    "sale_id": sale.id,
                },
            )
        )["data"]["id"]

        self.client.logout()
        self._login(self.office_a)
        forbidden_all = self.client.get("/api/notifications/?box=all")
        self.assertEqual(forbidden_all.status_code, 403)

        self.client.logout()
        self._login(self.admin)
        rows = parse(self.client.get("/api/notifications/?box=all"))["data"]["results"]
        match = next(row for row in rows if row["notification_id"] == note_id)
        self.assertIn("↔", match["parties"])
        thread = parse(self.client.get(f"/api/notifications/{note_id}/"))["data"]
        self.assertTrue(thread["is_admin_view"])
        self.assertFalse(thread["can_reply"])
        blocked = self._post(f"/api/notifications/{note_id}/replies/", {"body": "ادمین نباید بنویسد"})
        self.assertEqual(blocked.status_code, 403)

    def test_reply_delete_not_allowed(self):
        sale = self._sale("1403-DEL")
        self._login(self.supervisor)
        note_id = parse(
            self._post(
                "/api/notifications/messages/",
                {
                    "to_user_id": self.office_a.id,
                    "kind": "ticket",
                    "title": "حذف‌نشدنی",
                    "sale_id": sale.id,
                },
            )
        )["data"]["id"]
        parse(self._post(f"/api/notifications/{note_id}/replies/", {"body": "پاسخ"}))
        self.assertEqual(self.client.delete(f"/api/notifications/{note_id}/replies/").status_code, 405)
        self.assertEqual(TicketMessage.objects.filter(notification_id=note_id).count(), 1)

    def test_ticket_requires_invoice_responsibility_does_not(self):
        self._login(self.supervisor)
        missing = self._post(
            "/api/notifications/messages/",
            {"to_user_id": self.office_a.id, "kind": "ticket", "title": "بدون فاکتور"},
        )
        self.assertEqual(missing.status_code, 400)
        ok = parse(
            self._post(
                "/api/notifications/messages/",
                {"to_user_id": self.office_a.id, "kind": "responsibility", "title": "بدون فاکتور"},
            )
        )
        self.assertTrue(ok["ok"])
