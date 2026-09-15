"""تست چرخه ماژولار سفارش و چهار مسیر بعد از CRM."""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from auth import roles
from backend.models import Customer, LoyaltyLevel, Sale
from logic.order_cycle import (
    create_warehouse,
    get_active_cycle,
    save_cycle,
    seed_order_cycle,
)
from logic.sale_workflow import (
    approve_office_order,
    approve_sale_branch,
    complete_pickup_order,
    complete_warehouse_order,
)
from logic.sales import record_sale
from testing.role_helpers import ensure_legacy_test_roles

User = get_user_model()


def make_user(username, password="secret123", role=roles.ADMIN):
    ensure_legacy_test_roles()
    user = User.objects.create_user(username=username, password=password)
    roles.assign_role(user, role)
    return user


def parse(response):
    return json.loads(response.content)


def _slot_payload(cycle, **overrides):
    slots = []
    for slot in cycle.slots.all():
        item = {
            "step_key": slot.step_key,
            "assignee_type": slot.assignee_type,
            "user_id": slot.user_id,
            "org_rank_id": slot.org_rank_id,
            "is_enabled": slot.is_enabled,
        }
        if slot.step_key in overrides:
            item.update(overrides[slot.step_key])
        slots.append(item)
    return slots


class OrderCycleConfigTest(TestCase):
    def setUp(self):
        LoyaltyLevel.objects.create(name="برنز", min_purchase=0, max_purchase=None)
        self.admin = make_user("cycadm")
        self.monitor = make_user("monitor", role=roles.OPERATOR)
        self.supervisor = make_user("superslot", role=roles.OPERATOR)
        self.client = Client()
        self.client.login(username="cycadm", password="secret123")
        seed_order_cycle()

    def test_get_cycle_requires_admin(self):
        other = Client()
        other.login(username="monitor", password="secret123")
        resp = other.get("/api/cycle/")
        self.assertEqual(resp.status_code, 403)

    def test_save_cycle_requires_monitors(self):
        cycle = get_active_cycle()
        resp = self.client.put(
            "/api/cycle/",
            data=json.dumps({"slots": _slot_payload(cycle)}),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("ناظر", body["error"])

    def test_save_cycle_with_users(self):
        cycle = get_active_cycle()
        resp = self.client.put(
            "/api/cycle/",
            data=json.dumps({
                "slots": _slot_payload(
                    cycle,
                    shop_crm_monitor={
                        "assignee_type": "user",
                        "user_id": self.monitor.id,
                    },
                    fulfillment_supervisor={
                        "assignee_type": "user",
                        "user_id": self.supervisor.id,
                    },
                )
            }),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertEqual(resp.status_code, 200, msg=body)
        self.assertTrue(body["ok"])
        me = Client()
        me.login(username="monitor", password="secret123")
        mine = parse(me.get("/api/auth/me/"))
        self.assertTrue(mine["data"]["cycle"]["is_shop_crm_monitor"])
        self.assertIn("view_cycle_watch", mine["data"]["permissions"])

    def test_create_warehouse(self):
        resp = self.client.post(
            "/api/cycle/warehouses/",
            data=json.dumps({"code": "wh_main", "label": "انبار مرکزی"}),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertEqual(resp.status_code, 201, msg=body)
        self.assertEqual(body["data"]["label"], "انبار مرکزی")


class OrderCycleRoutesTest(TestCase):
    def setUp(self):
        LoyaltyLevel.objects.create(name="برنز", min_purchase=0, max_purchase=None)
        self.user = make_user("crmuser")
        self.colleague = make_user("colleague", role=roles.OPERATOR)
        self.customer = Customer.objects.create(full_name="مشتری چرخه", phone="09121112233")
        seed_order_cycle()
        self.warehouse = create_warehouse({"code": "wh1", "label": "انبار یک"})

    def _office_from_new_sale(self):
        sale = record_sale(
            self.customer,
            Decimal("2000000"),
            payment_status="paid",
            accounting_mode="automatic",
            recorded_by=self.user,
        )
        from backend.models import OfficeOrder

        approve_sale_branch(sale, self.user)
        return OfficeOrder.objects.get(pk=sale.pk)

    def test_factory_route_still_default(self):
        office = self._office_from_new_sale()
        approve_office_order(office, self.user)
        office.refresh_from_db()
        self.assertEqual(office.workflow_stage_id, Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED)
        self.assertEqual(office.fulfillment_route, Sale.FULFILLMENT_ROUTE_FACTORY)

    def test_warehouse_requires_exactly_one_source(self):
        office = self._office_from_new_sale()
        with self.assertRaises(ValueError):
            approve_office_order(office, self.user, fulfillment_route="warehouse")

    def test_warehouse_route_and_complete(self):
        office = self._office_from_new_sale()
        approve_office_order(office, self.user, fulfillment_route="warehouse", warehouse_id=self.warehouse.id)
        office.refresh_from_db()
        self.assertEqual(office.workflow_stage_id, Sale.WORKFLOW_STAGE_IN_WAREHOUSE)
        self.assertEqual(office.fulfillment_warehouse_id, self.warehouse.id)
        sale = complete_warehouse_order(office, self.user)
        self.assertEqual(sale.workflow_stage_id, Sale.WORKFLOW_STAGE_COMPLETED)

    def test_warehouse_from_branch(self):
        office = self._office_from_new_sale()
        approve_office_order(office, self.user, fulfillment_route="warehouse", source_branch="branch_1")
        office.refresh_from_db()
        self.assertEqual(office.fulfillment_source_branch_id, "branch_1")
        self.assertIsNone(office.fulfillment_warehouse_id)

    def test_pickup_route_and_complete(self):
        office = self._office_from_new_sale()
        approve_office_order(office, self.user, fulfillment_route="customer_pickup")
        office.refresh_from_db()
        self.assertEqual(office.workflow_stage_id, Sale.WORKFLOW_STAGE_READY_FOR_PICKUP)
        sale = complete_pickup_order(office, self.user)
        self.assertEqual(sale.workflow_stage_id, Sale.WORKFLOW_STAGE_COMPLETED)

    def test_merchant_requires_colleague(self):
        office = self._office_from_new_sale()
        with self.assertRaises(ValueError):
            approve_office_order(office, self.user, fulfillment_route="merchant")

    def test_merchant_goes_to_factory_queue(self):
        from backend.models import FactoryOrder

        office = self._office_from_new_sale()
        approve_office_order(office, self.user, fulfillment_route="merchant", merchant_user_id=self.colleague.id)
        office.refresh_from_db()
        self.assertEqual(office.workflow_stage_id, Sale.WORKFLOW_STAGE_MERCHANT_ASSIGNED)
        self.assertEqual(office.merchant_user_id, self.colleague.id)
        self.assertTrue(FactoryOrder.objects.filter(pk=office.pk).exists())

    def test_disabled_route_rejected(self):
        cycle = get_active_cycle()
        save_cycle({
            "slots": _slot_payload(
                cycle,
                shop_crm_monitor={"assignee_type": "user", "user_id": self.colleague.id},
                fulfillment_supervisor={"assignee_type": "user", "user_id": self.user.id},
                warehouse={"is_enabled": False},
            )
        })
        office = self._office_from_new_sale()
        with self.assertRaises(ValueError):
            approve_office_order(office, self.user, fulfillment_route="warehouse", warehouse_id=self.warehouse.id)

    def test_monitor_cannot_approve(self):
        cycle = get_active_cycle()
        save_cycle({
            "slots": _slot_payload(
                cycle,
                shop_crm_monitor={"assignee_type": "user", "user_id": self.colleague.id},
                fulfillment_supervisor={"assignee_type": "user", "user_id": self.user.id},
            )
        })
        client = Client()
        client.login(username="colleague", password="secret123")
        office = self._office_from_new_sale()
        resp = client.post(f"/api/office/orders/{office.id}/approve/", data=json.dumps({}), content_type="application/json")
        self.assertEqual(resp.status_code, 403)
        watch = client.get("/api/cycle/watch/?scope=shop_crm")
        self.assertEqual(watch.status_code, 200)
        self.assertTrue(parse(watch)["ok"])
