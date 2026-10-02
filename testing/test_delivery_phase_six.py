import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from backend.models import (
    Branch,
    Customer,
    DeliveryDocument,
    FinancialEvent,
    InventoryCostLayer,
    InventoryReservation,
    JournalEntry,
    Material,
    Product,
    ProductMaterial,
    ProductVariant,
    Sale,
    SaleLineItem,
    SalesReturn,
)
from logic.delivery import deliver_sale, return_sale
from logic.inventory_costing import adjust_stock, availability, receive_stock
from logic.production import complete_run, consume_requirement
from logic.sales import cancel_order, record_payment
from logic.stock_locations import ensure_central_warehouse, parse_location
from testing.accounting_helpers import seed_accounts
from logic.ledger import LEGAL_LEDGER
from logic.fulfillment import receive_merchant_supply, save_fulfillment_plan


class DeliveryPhaseSixTests(TestCase):
    def setUp(self):
        seed_accounts(ledger=LEGAL_LEDGER)
        self.user = get_user_model().objects.create_superuser(
            username="delivery-admin", password="secret123"
        )
        self.plain = get_user_model().objects.create_user(
            username="delivery-viewer", password="secret123"
        )
        self.branch, _ = Branch.objects.get_or_create(
            code="branch_1", defaults={"label": "Branch one"}
        )
        self.warehouse = ensure_central_warehouse()
        self.location = parse_location(
            {"kind": "warehouse", "warehouse_id": self.warehouse.pk}, required=True
        )
        self.customer = Customer.objects.create(full_name="Customer", phone="09120000061")
        self.product = Product.objects.create(name="FIFO product", default_price=1000)
        self.variant = ProductVariant.objects.create(
            product=self.product, color_name="Blue", price=1000
        )

    def make_sale(self, quantity=3, *, invoice="D-1"):
        sale = Sale.objects.create(
            customer=self.customer,
            branch=self.branch,
            workflow_stage_id=Sale.WORKFLOW_STAGE_IN_WAREHOUSE,
            amount=Decimal(1000) * quantity,
            final_amount=Decimal(1100) * quantity,
            vat_rate=10,
            vat_amount=Decimal(100) * quantity,
            paid_amount=0,
            invoice_number=invoice,
            accounting_mode=Sale.ACCOUNTING_MODE_MANUAL,
            recorded_by=self.user,
        )
        line = SaleLineItem.objects.create(
            sale=sale, product=self.product, variant=self.variant,
            product_name=self.product.name, quantity=quantity, unit_price=1000,
            line_total=Decimal(1000) * quantity,
        )
        return sale, line

    def stock_plan(self, line, quantity):
        return save_fulfillment_plan(
            line,
            [{
                "route_kind": "warehouse_stock",
                "quantity": quantity,
                "warehouse_id": self.warehouse.pk,
            }],
            user=self.user,
        )

    def test_fifo_delivery_is_idempotent_and_posts_separate_events(self):
        adjust_stock(self.variant, 2, unit_cost=100, location=self.location, reason="lot-1")
        adjust_stock(self.variant, 3, unit_cost=200, location=self.location, reason="lot-2")
        sale, line = self.make_sale()
        self.stock_plan(line, 3)

        first = deliver_sale(sale, user=self.user, idempotency_key="delivery-one")
        second = deliver_sale(sale, user=self.user, idempotency_key="delivery-one")

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.total_actual_cogs, Decimal("400"))
        self.assertEqual(first.lines.get().consumption.allocations.count(), 2)
        self.assertEqual(
            FinancialEvent.objects.filter(
                source_type="DeliveryDocument", source_key=str(first.uuid)
            ).count(),
            2,
        )
        self.assertEqual(first.sale_event.event_type, "sale_recognized")
        self.assertEqual(first.cogs_event.event_type, "actual_cogs_recognized")

    def test_factory_route_uses_its_actual_product_lot_not_older_fifo(self):
        material = Material.objects.create(
            name="Factory wood", unit="m", unit_cost=50, valuation_method=Material.VALUATION_FIFO
        )
        ProductMaterial.objects.create(product=self.product, material=material, quantity=1)
        receive_stock(material, 1, 50, location=self.location)
        adjust_stock(self.variant, 1, unit_cost=999, location=self.location, reason="older-finished-lot")
        sale, line = self.make_sale(quantity=1, invoice="FACTORY-1")
        plan = save_fulfillment_plan(
            line, [{"route_kind": "factory", "quantity": 1}], user=self.user
        )
        run = plan.lines.get().production_run
        consume_requirement(run.requirements.get(), user=self.user)
        complete_run(run, user=self.user)
        delivery = deliver_sale(sale, user=self.user)
        delivered = delivery.lines.get()
        self.assertEqual(delivered.product_lot_id, run.product_lot.pk)
        self.assertEqual(delivered.total_actual_cost, Decimal("50"))
        self.assertEqual(
            delivered.consumption.allocations.get().cost_layer_id,
            run.product_lot.cost_layer_id,
        )

    def test_merchant_route_requires_and_consumes_received_goods(self):
        sale, line = self.make_sale(quantity=1, invoice="MERCHANT-1")
        plan = save_fulfillment_plan(
            line, [{"route_kind": "merchant", "quantity": 1}], user=self.user
        )
        demand = plan.lines.get().merchant_demand
        with self.assertRaisesRegex(ValueError, "must be received"):
            deliver_sale(sale, user=self.user)
        receive_merchant_supply(demand, unit_cost=425, user=self.user)
        delivery = deliver_sale(sale, user=self.user)
        self.assertEqual(delivery.total_actual_cogs, Decimal("425"))
        demand.refresh_from_db()
        self.assertIsNotNone(demand.receipt_movement_id)

    def test_legacy_draft_is_retired_without_duplicate_live_sale(self):
        adjust_stock(self.variant, 1, unit_cost=250, location=self.location, reason="lot")
        sale, line = self.make_sale(quantity=1)
        self.stock_plan(line, 1)
        from logic.sales import _create_sale_accounting

        _create_sale_accounting(sale, sale.final_amount, is_approved=False)
        legacy = JournalEntry.objects.get(order_links__order=sale, entry_type_ref_id="sale")
        delivery = deliver_sale(sale, user=self.user)
        legacy.refresh_from_db()
        self.assertEqual(legacy.status, JournalEntry.STATUS_VOID)
        self.assertNotEqual(delivery.sale_event.journal_id, legacy.pk)
        self.assertEqual(
            JournalEntry.objects.filter(
                order_links__order=sale, entry_type_ref_id="sale"
            ).exclude(status_ref_id=JournalEntry.STATUS_VOID).count(),
            2,  # separate revenue and actual-cost journals
        )

    def test_cancel_releases_before_delivery_and_is_blocked_after(self):
        adjust_stock(self.variant, 2, unit_cost=100, location=self.location, reason="lot")
        sale, line = self.make_sale(quantity=1, invoice="C-1")
        sale.order_kind = Sale.ORDER_KIND_DEPOSIT
        sale.order_status = Sale.ORDER_STATUS_PENDING
        sale.save(update_fields=["order_kind", "order_status"])
        self.stock_plan(line, 1)
        cancel_order(sale, recorded_by=self.user)
        self.assertEqual(InventoryReservation.objects.get().status, "released")

        sale2, line2 = self.make_sale(quantity=1, invoice="C-2")
        sale2.order_kind = Sale.ORDER_KIND_DEPOSIT
        sale2.order_status = Sale.ORDER_STATUS_PENDING
        sale2.save(update_fields=["order_kind", "order_status"])
        self.stock_plan(line2, 1)
        deliver_sale(sale2, user=self.user)
        with self.assertRaisesRegex(ValueError, "return/correction"):
            cancel_order(sale2, recorded_by=self.user)

    def test_payment_key_is_idempotent(self):
        sale, _line = self.make_sale(quantity=1)
        record_payment(sale, 300, recorded_by=self.user, idempotency_key="payment-one")
        record_payment(sale, 300, recorded_by=self.user, idempotency_key="payment-one")
        sale.refresh_from_db()
        self.assertEqual(sale.paid_amount, Decimal("300"))
        self.assertEqual(
            FinancialEvent.objects.filter(
                source_type="SalePayment", source_key="payment-one"
            ).count(),
            1,
        )

    def test_partial_and_full_return_use_original_cost_and_block_excess(self):
        adjust_stock(self.variant, 2, unit_cost=100, location=self.location, reason="lot-1")
        adjust_stock(self.variant, 1, unit_cost=200, location=self.location, reason="lot-2")
        sale, line = self.make_sale()
        self.stock_plan(line, 3)
        delivery = deliver_sale(sale, user=self.user)
        delivery_line = delivery.lines.get()

        first = return_sale(
            delivery,
            [{"delivery_line_id": delivery_line.pk, "quantity": 1}],
            reason="first return", user=self.user, idempotency_key="return-one",
        )
        self.assertEqual(first.total_actual_cogs, Decimal("100"))
        self.assertEqual(first.lines.get().return_cost_layer.unit_cost, Decimal("100"))
        second = return_sale(
            delivery,
            [{"delivery_line_id": delivery_line.pk, "quantity": 2}],
            reason="final return", user=self.user, idempotency_key="return-two",
        )
        self.assertEqual(second.total_actual_cogs, Decimal("300"))
        self.assertEqual(second.lines.get().return_cost_layer.unit_cost, Decimal("150"))
        with self.assertRaisesRegex(ValueError, "exceeds"):
            return_sale(
                delivery,
                [{"delivery_line_id": delivery_line.pk, "quantity": 1}],
                reason="too much", user=self.user, idempotency_key="return-three",
            )
        self.assertEqual(SalesReturn.objects.count(), 2)
        self.assertEqual(availability(self.variant, location=self.location)["on_hand"], Decimal("3"))

    def test_trace_api_permissions_and_delivery_payload(self):
        adjust_stock(self.variant, 1, unit_cost=300, location=self.location, reason="lot")
        sale, line = self.make_sale(quantity=1)
        self.stock_plan(line, 1)
        denied = Client()
        denied.force_login(self.plain)
        self.assertEqual(denied.get(f"/api/sales/{sale.pk}/trace/").status_code, 403)
        client = Client()
        client.force_login(self.user)
        delivered = client.post(
            f"/api/sales/{sale.pk}/deliver/",
            data=json.dumps({"idempotency_key": "api-delivery"}),
            content_type="application/json",
        )
        self.assertEqual(delivered.status_code, 200, delivered.content)
        payload = delivered.json()["data"]
        self.assertEqual(payload["delivery"]["total_actual_cogs"], "300")
        self.assertEqual(len(payload["delivery"]["lines"][0]["allocations"]), 1)
        self.assertEqual(DeliveryDocument.objects.count(), 1)
