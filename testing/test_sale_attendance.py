"""گیت حضور برای ثبت سفارش و تغییر شعبه همان‌روز."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auth import roles
from backend.models import Branch, Customer, Product, ProductVariant, Seller, StaffAttendance
from logic.attendance import approve_branch_switch, check_in, check_out, request_branch_switch
from logic.attendance_settings import set_attendance_enforced
from logic.config_seed import seed_config_defaults
from logic.sale_attendance import evaluate_sale_attendance
from logic.sales import record_sale, update_sale
from logic.sellers import ensure_seller_for_user, resolve_sale_branch_for_create
from testing.role_helpers import ensure_legacy_test_roles, ensure_test_role

User = get_user_model()


class SaleAttendanceGateTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        ensure_legacy_test_roles()
        Branch.objects.get_or_create(code="branch_1", defaults={"label": "کمرد", "is_active": True})
        Branch.objects.get_or_create(code="branch_2", defaults={"label": "پاسداران", "is_active": True})
        self.customer = Customer.objects.create(full_name="خریدار", phone="09121111111")
        self.product = Product.objects.create(name="میز", default_price=50000)
        self.variant = ProductVariant.objects.create(product=self.product, color_name="چوب")
        set_attendance_enforced(True)

        ensure_test_role(
            roles.SALES_EXPERT,
            ["create_sale", "view_own_sales", "self_check_in", "view_products"],
            label="کارشناس فروش",
            needs_branch=True,
        )
        self.expert = User.objects.create_user(username="expert", password="x")
        roles.assign_role(self.expert, roles.SALES_EXPERT)
        self.seller = ensure_seller_for_user(self.expert, branch="branch_1")

        ensure_test_role(
            roles.BRANCH_SUPERVISOR,
            ["create_sale", "approve_sale_branch", "self_check_in", "view_sales"],
            label="سرپرست شعبه",
            needs_branch=True,
        )
        self.supervisor = User.objects.create_user(username="boss", password="x")
        roles.assign_role(self.supervisor, roles.BRANCH_SUPERVISOR)
        ensure_seller_for_user(self.supervisor, branch="branch_1")

    def _sell(self, user, branch="branch_1"):
        seller = Seller.objects.filter(user=user).first()
        return record_sale(
            self.customer,
            0,
            line_items=[{"product_id": self.product.id, "variant_id": self.variant.id, "quantity": 1}],
            recorded_by=user,
            branch=branch,
            seller=seller,
        )

    def test_expert_without_checkin_cannot_sell_when_enforced(self):
        state = evaluate_sale_attendance(self.expert)
        self.assertTrue(state["blocked"])
        with self.assertRaises(ValueError):
            self._sell(self.expert)

    def test_expert_with_checkin_can_sell(self):
        record, _ = check_in(self.seller, self.expert, work_branch="branch_1")
        record.approval_status = "approved"
        record.approved_at = timezone.now()
        record.save()
        sale = self._sell(self.expert)
        self.assertEqual(sale.branch_id, "branch_1")

    def test_pending_checkin_cannot_sell(self):
        record, _ = check_in(self.seller, self.expert, work_branch="branch_1")
        self.assertEqual(record.approval_status, "pending")
        state = evaluate_sale_attendance(self.expert)
        self.assertTrue(state["blocked"])
        with self.assertRaises(ValueError):
            self._sell(self.expert)

    def test_checked_out_expert_cannot_replace_sale_lines(self):
        record, _ = check_in(self.seller, self.expert, work_branch="branch_1")
        record.approval_status = "approved"
        record.approved_at = timezone.now()
        record.save()
        sale = self._sell(self.expert)
        check_out(self.seller)
        with self.assertRaises(ValueError):
            update_sale(
                sale,
                line_items=[
                    {
                        "product_id": self.product.id,
                        "variant_id": self.variant.id,
                        "quantity": 2,
                    }
                ],
                recorded_by=self.expert,
            )

    def test_leave_blocks_sale(self):
        StaffAttendance.objects.create(
            seller=self.seller,
            date=timezone.localdate(),
            status="leave",
            work_branch_id="branch_1",
            approval_status="approved",
        )
        state = evaluate_sale_attendance(self.expert)
        self.assertTrue(state["blocked"])
        self.assertIn("مرخصی", state["reason"])

    def test_manager_can_sell_without_attendance_but_must_pick_branch(self):
        state = evaluate_sale_attendance(self.supervisor)
        self.assertFalse(state["blocked"])
        self.assertTrue(state["must_pick_branch"])
        branch = resolve_sale_branch_for_create(self.supervisor, "branch_2")
        self.assertEqual(branch, "branch_2")

    def test_manager_with_checkin_uses_session_branch(self):
        seller = Seller.objects.get(user=self.supervisor)
        record, _ = check_in(seller, self.supervisor, work_branch="branch_1")
        record.approval_status = "approved"
        record.approved_at = timezone.now()
        record.save()
        state = evaluate_sale_attendance(self.supervisor)
        self.assertFalse(state["blocked"])
        self.assertFalse(state["must_pick_branch"])
        self.assertEqual(state["work_branch"], "branch_1")
        self.assertEqual(resolve_sale_branch_for_create(self.supervisor), "branch_1")

    def test_attendance_off_requires_branch_and_ignores_time(self):
        set_attendance_enforced(False)
        state = evaluate_sale_attendance(self.expert)
        self.assertFalse(state["blocked"])
        self.assertTrue(state["must_pick_branch"])
        branch = resolve_sale_branch_for_create(self.expert, "branch_2")
        self.assertEqual(branch, "branch_2")

    def test_attendance_off_ignores_leave(self):
        StaffAttendance.objects.create(
            seller=self.seller,
            date=timezone.localdate(),
            status="leave",
            work_branch_id="branch_1",
            approval_status="approved",
        )
        set_attendance_enforced(False)
        state = evaluate_sale_attendance(self.expert)
        self.assertFalse(state["blocked"])
        self.assertTrue(state["must_pick_branch"])


class SameDayBranchSwitchTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        ensure_legacy_test_roles()
        Branch.objects.get_or_create(code="branch_1", defaults={"label": "کمرد", "is_active": True})
        Branch.objects.get_or_create(code="branch_2", defaults={"label": "پاسداران", "is_active": True})
        ensure_test_role(
            roles.SALES_EXPERT,
            ["create_sale", "self_check_in"],
            label="کارشناس فروش",
            needs_branch=True,
        )
        ensure_test_role(
            "hr_manager",
            ["manage_attendance", "view_attendance"],
            label="مدیر حضور",
        )
        self.expert = User.objects.create_user(username="exp2", password="x")
        roles.assign_role(self.expert, roles.SALES_EXPERT)
        self.seller = ensure_seller_for_user(self.expert, branch="branch_1")
        self.manager = User.objects.create_user(username="hrm", password="x")
        roles.assign_role(self.manager, "hr_manager")

    def test_manager_approves_remaining_hours_on_other_branch(self):
        record, _ = check_in(self.seller, self.expert, work_branch="branch_1")
        record.approval_status = "approved"
        record.approved_at = timezone.now()
        record.save()
        notification, _ = request_branch_switch(self.seller, self.expert, "branch_2")
        new_record = approve_branch_switch(notification, self.manager)
        record.refresh_from_db()
        self.assertIsNotNone(record.check_out_at)
        self.assertEqual(new_record.work_branch_id, "branch_2")
        self.assertIsNone(new_record.check_out_at)
        from logic.sellers import effective_sale_branch

        self.assertEqual(effective_sale_branch(self.expert), "branch_2")

    def test_second_pending_switch_cannot_open_another_session(self):
        record, _ = check_in(self.seller, self.expert, work_branch="branch_1")
        record.approval_status = "approved"
        record.approved_at = timezone.now()
        record.save()
        first, _ = request_branch_switch(self.seller, self.expert, "branch_2")
        with self.assertRaises(ValueError):
            request_branch_switch(self.seller, self.expert, "branch_2")
        approve_branch_switch(first, self.manager)
        self.assertEqual(
            StaffAttendance.objects.filter(
                seller=self.seller,
                status="present",
                check_out_at__isnull=True,
                is_deleted=False,
            ).count(),
            1,
        )
