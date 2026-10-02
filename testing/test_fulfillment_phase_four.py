import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from backend.models import (
    Branch,
    Customer,
    FulfillmentPlanLine,
    InventoryReservation,
    InventoryTransaction,
    Material,
    MerchantSupplyDemand,
    Product,
    ProductMaterial,
    ProductVariant,
    Sale,
    SaleLineItem,
    StockTransfer,
)
from logic.fulfillment import (
    assert_factory_fulfillment_ready,
    complete_stock_transfer,
    release_fulfillment_plan,
    save_fulfillment_plan,
    start_stock_transfer,
)
from logic.inventory_costing import adjust_stock, availability
from logic.stock_locations import ensure_central_warehouse, parse_location


class FulfillmentPhaseFourTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="fulfillment-admin", password="secret123"
        )
        self.plain = get_user_model().objects.create_user(
            username="fulfillment-plain", password="secret123"
        )
        self.branch, _ = Branch.objects.get_or_create(
            code="branch_1", defaults={"label": "Branch one"}
        )
        self.warehouse = ensure_central_warehouse()
        self.customer = Customer.objects.create(full_name="Customer", phone="09121110000")
        self.product = Product.objects.create(name="Chair", default_price=1000)
        self.variant = ProductVariant.objects.create(
            product=self.product, color_name="Blue", price=1000
        )
        self.sale = Sale.objects.create(
            customer=self.customer,
            branch=self.branch,
            workflow_stage_id=Sale.WORKFLOW_STAGE_BRANCH_APPROVED,
            amount=4000,
            final_amount=4000,
            accounting_mode=Sale.ACCOUNTING_MODE_MANUAL,
            recorded_by=self.user,
        )
        self.line = SaleLineItem.objects.create(
            sale=self.sale,
            product=self.product,
            variant=self.variant,
            product_name=self.product.name,
            quantity=4,
            unit_price=1000,
            line_total=4000,
        )
        self.warehouse_location = parse_location(
            {"kind": "warehouse", "warehouse_id": self.warehouse.pk}, required=True
        )
        self.branch_location = parse_location(
            {"kind": "branch", "branch": self.branch.code}, required=True
        )
        adjust_stock(
            self.variant, 10, unit_cost=700, location=self.warehouse_location,
            reason="opening", user=self.user,
        )

    def test_sale_line_creation_does_not_deduct_and_plan_reserves(self):
        self.assertEqual(self.variant.stock_at(warehouse_id=self.warehouse.pk), Decimal("10"))
        plan = save_fulfillment_plan(
            self.line,
            [{"route_kind": "warehouse_stock", "quantity": 4, "warehouse_id": self.warehouse.pk}],
            user=self.user,
        )
        self.assertEqual(self.variant.stock_at(warehouse_id=self.warehouse.pk), Decimal("10"))
        self.assertEqual(
            availability(self.variant, location=self.warehouse_location)["available"], Decimal("6")
        )
        self.assertEqual(plan.lines.get().status, FulfillmentPlanLine.STATUS_RESERVED)

    def test_split_sum_validation_and_cancel_release(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            save_fulfillment_plan(
                self.line,
                [
                    {"route_kind": "warehouse_stock", "quantity": 3, "warehouse_id": self.warehouse.pk},
                    {"route_kind": "merchant", "quantity": 2},
                ],
                user=self.user,
            )
        plan = save_fulfillment_plan(
            self.line,
            [
                {"route_kind": "warehouse_stock", "quantity": 2, "warehouse_id": self.warehouse.pk},
                {"route_kind": "merchant", "quantity": 2},
            ],
            user=self.user,
        )
        release_fulfillment_plan(plan, user=self.user, cancel=True)
        self.assertFalse(InventoryReservation.objects.filter(status="active").exists())
        self.assertEqual(MerchantSupplyDemand.objects.get().status, "cancelled")

    def test_factory_snapshots_bom_and_links_shortage(self):
        material = Material.objects.create(name="Wood", unit="m", unit_cost=100)
        ProductMaterial.objects.create(product=self.product, material=material, quantity=2)
        plan = save_fulfillment_plan(
            self.line, [{"route_kind": "factory", "quantity": 2}], user=self.user
        )
        route = plan.lines.get()
        self.assertEqual(route.bom_snapshot[0]["required_quantity"], "4.000")
        self.assertIsNotNone(route.production_order_id)
        self.assertIsNotNone(route.shortage_request_id)
        self.assertEqual(route.status, FulfillmentPlanLine.STATUS_BLOCKED)
        with self.assertRaisesRegex(ValueError, "shortages"):
            assert_factory_fulfillment_ready(self.sale)

    def test_merchant_uses_finished_goods_demand(self):
        plan = save_fulfillment_plan(
            self.line, [{"route_kind": "merchant", "quantity": 4}], user=self.user
        )
        demand = plan.lines.get().merchant_demand
        self.assertEqual(demand.variant, self.variant)
        self.assertEqual(demand.quantity, Decimal("4"))
        self.assertEqual(demand.destination_kind, "branch")

    def test_paired_transfer_is_in_transit_and_idempotent(self):
        first = start_stock_transfer(
            self.variant, self.warehouse_location, self.branch_location, 3,
            idempotency_key="transfer-one", user=self.user,
        )
        second = start_stock_transfer(
            self.variant, self.warehouse_location, self.branch_location, 3,
            idempotency_key="transfer-one", user=self.user,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.status, StockTransfer.STATUS_IN_TRANSIT)
        self.assertIsNotNone(first.issue_movement_id)
        self.assertIsNone(first.receipt_movement_id)
        complete_stock_transfer(first, user=self.user)
        first.refresh_from_db()
        self.assertEqual(first.status, StockTransfer.STATUS_COMPLETED)
        self.assertIsNotNone(first.receipt_movement_id)
        self.assertEqual(
            InventoryTransaction.objects.filter(reference="transfer:transfer-one").count(), 2
        )
        self.assertIsNotNone(first.accounting_event_id)

    def test_api_permissions_and_location_availability(self):
        denied = Client()
        denied.force_login(self.plain)
        self.assertEqual(
            denied.get(f"/api/fulfillment/lines/{self.line.pk}/availability/").status_code, 403
        )
        client = Client()
        client.force_login(self.user)
        response = client.put(
            f"/api/fulfillment/lines/{self.line.pk}/plan/",
            data=json.dumps({"lines": [{
                "route_kind": "warehouse_stock",
                "quantity": 4,
                "warehouse_id": self.warehouse.pk,
            }]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"]["lines"][0]["status"], "reserved")
        availability_response = client.get(
            f"/api/fulfillment/lines/{self.line.pk}/availability/"
        )
        self.assertEqual(availability_response.status_code, 200)
        self.assertTrue(availability_response.json()["data"]["locations"])
