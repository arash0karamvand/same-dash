"""تایید نهایی ساخته‌شده‌ها، تیکت تعیین تکلیف و ارسال به باربری."""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from auth import roles
from auth.views import apply_user_access
from backend.models import Customer, LoyaltyLevel, Notification, NotificationReceipt, Sale
from logic.config_seed import seed_config_defaults
from logic.early_ship import (
    READY_FOR_DELIVERY_COLOR,
    READY_FOR_DELIVERY_LABEL,
    confirm_factory_delivery_ready,
    delivery_urgency,
    send_factory_order_to_freight,
)
from logic.factory_orders import factory_queryset_for_user
from logic.order_cycle import seed_order_cycle
from logic.order_queues import as_factory_order
from logic.sale_workflow import complete_factory_freight, complete_factory_production
from testing.role_helpers import ensure_legacy_test_roles

User = get_user_model()
PASSWORD = "secret123"


def parse(response):
    return json.loads(response.content)


class DeliveryReadyFreightTests(TestCase):
    def setUp(self):
        seed_config_defaults()
        seed_order_cycle()
        ensure_legacy_test_roles()
        LoyaltyLevel.objects.create(name="برنز", min_purchase=0, max_purchase=None)
        self.factory = User.objects.create_user(username="factory1", password=PASSWORD, first_name="کارخانه")
        apply_user_access(self.factory, roles.FACTORY_SUPERVISOR)
        self.office_a = User.objects.create_user(username="officea", password=PASSWORD, first_name="اداری‌یک")
        apply_user_access(self.office_a, roles.ACCOUNTING_FINANCE)
        self.office_b = User.objects.create_user(username="officeb", password=PASSWORD, first_name="اداری‌دو")
        apply_user_access(self.office_b, roles.ACCOUNTING_FINANCE)
        self.shop = User.objects.create_user(username="shopcrm", password=PASSWORD, first_name="فروشگاه")
        apply_user_access(self.shop, roles.SALES_EXPERT, "branch_1")
        self.customer = Customer.objects.create(full_name="مشتری باربری", phone="09120009988")
        self.today = timezone.localdate()

    def _sale(self, *, lead_days, remaining_days, invoice="INV-READY"):
        sold = timezone.now() - timedelta(days=lead_days - remaining_days)
        delivery = self.today + timedelta(days=remaining_days)
        sale = Sale.objects.create(
            customer=self.customer,
            branch_id="branch_1",
            workflow_stage_id=Sale.WORKFLOW_STAGE_IN_PRODUCTION,
            amount=Decimal("1500000"),
            final_amount=Decimal("1500000"),
            paid_amount=Decimal("1500000"),
            accounting_mode=Sale.ACCOUNTING_MODE_MANUAL,
            delivery_date=delivery,
            invoice_number=invoice,
            sold_at=sold,
        )
        return as_factory_order(sale)

    def _built(self, **kwargs):
        factory = self._sale(**kwargs)
        return complete_factory_production(factory, self.factory)

    def test_built_orders_are_not_in_freight_queue(self):
        built = self._built(lead_days=5, remaining_days=2)
        freight = factory_queryset_for_user(self.office_a, {"section": "freight"})
        built_qs = factory_queryset_for_user(self.factory, {"section": "built"})
        self.assertFalse(freight.filter(pk=built.pk).exists())
        self.assertTrue(built_qs.filter(pk=built.pk).exists())

    def test_send_without_final_confirm_is_rejected(self):
        built = self._built(lead_days=5, remaining_days=2)
        with self.assertRaisesMessage(ValueError, "ابتدا تایید نهایی را بزنید"):
            send_factory_order_to_freight(built, self.factory)

    def test_short_lead_confirm_ready_allows_early_send_with_flag(self):
        from api.serializers import factory_order_to_dict

        built = self._built(lead_days=8, remaining_days=5)
        self.assertEqual(delivery_urgency(built), "orange")
        ready = confirm_factory_delivery_ready(built, self.factory)
        ready.refresh_from_db()
        self.assertTrue(ready.delivery_ready_at)
        self.assertFalse(ready.early_disposition_required)
        self.assertEqual(ready.early_ship_allowed_date, self.today)
        payload = factory_order_to_dict(ready)
        self.assertEqual(payload["stage_badge_label"], READY_FOR_DELIVERY_LABEL)
        self.assertEqual(payload["stage_badge_color"], READY_FOR_DELIVERY_COLOR)
        sent = send_factory_order_to_freight(ready, self.factory)
        sent.refresh_from_db()
        self.assertEqual(sent.workflow_stage_id, Sale.WORKFLOW_STAGE_IN_FREIGHT)
        self.assertTrue(sent.shipped_early)
        freight = factory_queryset_for_user(self.office_a, {"section": "freight"})
        self.assertTrue(freight.filter(pk=sent.pk).exists())
        self.assertFalse(
            factory_queryset_for_user(self.office_a, {"section": "built"}).filter(pk=sent.pk).exists()
        )

    def test_long_lead_creates_ticket_and_blocks_early_send(self):
        built = self._built(lead_days=14, remaining_days=6, invoice="INV-LONG")
        ready = confirm_factory_delivery_ready(built, self.factory)
        ready.refresh_from_db()
        self.assertTrue(ready.early_disposition_required)
        self.assertIsNone(ready.early_ship_allowed_date)
        tickets = Notification.objects.filter(
            action_type=Notification.ACTION_ORG_TICKET,
            payload__purpose="early_ship_disposition",
            payload__sale_id=ready.pk,
        )
        duties = Notification.objects.filter(
            action_type=Notification.ACTION_ORG_RESPONSIBILITY,
            payload__purpose="early_ship_disposition",
            payload__sale_id=ready.pk,
        )
        self.assertEqual(tickets.count(), 1)
        self.assertEqual(duties.count(), 1)
        ticket = tickets.get()
        recipient_ids = set(NotificationReceipt.objects.filter(notification=ticket).values_list("user_id", flat=True))
        self.assertEqual(recipient_ids, {self.office_a.id, self.office_b.id, self.shop.id})
        with self.assertRaisesMessage(ValueError, "منتظر تعیین تکلیف اداری"):
            send_factory_order_to_freight(ready, self.factory)

    def test_first_open_claims_ticket_and_date_unlocks_send(self):
        built = self._built(lead_days=14, remaining_days=6, invoice="INV-CLAIM")
        ready = confirm_factory_delivery_ready(built, self.factory)
        ticket = Notification.objects.get(
            action_type=Notification.ACTION_ORG_TICKET,
            payload__sale_id=ready.pk,
        )
        client = Client()
        self.assertTrue(client.login(username=self.office_a.username, password=PASSWORD))
        first = client.get(f"/api/notifications/{ticket.id}/")
        self.assertEqual(first.status_code, 200, msg=first.content)
        body = parse(first)["data"]
        self.assertEqual(body["payload"]["claimed_by_id"], self.office_a.id)
        self.assertTrue(body["can_set_early_ship_date"])
        ready.refresh_from_db()
        self.assertEqual(ready.early_disposition_by_id, self.office_a.id)

        other = Client()
        self.assertTrue(other.login(username=self.office_b.username, password=PASSWORD))
        second = other.get(f"/api/notifications/{ticket.id}/")
        self.assertEqual(second.status_code, 404)

        set_resp = client.post(
            f"/api/notifications/{ticket.id}/act/",
            data=json.dumps({"action": "set_early_ship_date", "allowed_date": self.today.isoformat()}),
            content_type="application/json",
        )
        self.assertEqual(set_resp.status_code, 200, msg=set_resp.content)
        ready.refresh_from_db()
        self.assertEqual(ready.early_ship_allowed_date, self.today)
        sent = send_factory_order_to_freight(as_factory_order(ready), self.factory)
        self.assertTrue(sent.shipped_early)

    def test_complete_freight_still_requires_delivery_day(self):
        built = self._built(lead_days=4, remaining_days=2)
        ready = confirm_factory_delivery_ready(built, self.factory)
        sent = send_factory_order_to_freight(ready, self.factory)
        with self.assertRaisesMessage(ValueError, "فقط سفارش‌های با تاریخ تحویل امروز"):
            complete_factory_freight(sent, self.factory)

    def test_urgency_red_within_three_days(self):
        built = self._built(lead_days=5, remaining_days=3)
        self.assertEqual(delivery_urgency(built), "red")
        ready = confirm_factory_delivery_ready(built, self.factory)
        self.assertEqual(delivery_urgency(ready), "")

    def test_api_confirm_and_send_for_factory_user(self):
        built = self._built(lead_days=6, remaining_days=1, invoice="INV-API")
        client = Client()
        self.assertTrue(client.login(username=self.factory.username, password=PASSWORD))
        deny = client.post(f"/api/factory/orders/{built.pk}/send-to-freight/")
        self.assertEqual(deny.status_code, 400)
        ready = client.post(f"/api/factory/orders/{built.pk}/confirm-ready/")
        self.assertEqual(ready.status_code, 200, msg=ready.content)
        payload = parse(ready)["data"]
        self.assertEqual(payload["stage_badge_label"], READY_FOR_DELIVERY_LABEL)
        sent = client.post(f"/api/factory/orders/{built.pk}/send-to-freight/")
        self.assertEqual(sent.status_code, 200, msg=sent.content)
        self.assertEqual(parse(sent)["data"]["workflow_stage"], Sale.WORKFLOW_STAGE_IN_FREIGHT)
        self.assertTrue(parse(sent)["data"]["shipped_early"])
        listed = Client()
        self.assertTrue(listed.login(username=self.office_a.username, password=PASSWORD))
        listed_resp = listed.get("/api/factory/orders/?section=freight")
        ids = [row["id"] for row in parse(listed_resp)["data"]["results"]]
        self.assertIn(built.pk, ids)
