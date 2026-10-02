import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from backend.models import (
    Account,
    Branch,
    Customer,
    InventoryCostLayer,
    InventoryReservation,
    InventoryTransaction,
    Material,
    MaterialSupplier,
    Product,
    ProductMaterial,
    ProductVariant,
    ReconciliationQueue,
    Sale,
    SaleLineItem,
)
from logic.accounting_accounts import get_account
from logic.accounting_controls import discrepancy_scan
from logic.delivery import deliver_sale, delivery_trace, return_sale
from logic.document_attachments import create_attachment
from logic.feature_flags import FeatureDisabledError
from logic.fulfillment import save_fulfillment_plan
from logic.inventory_costing import receive_stock
from logic.procurement import approve_goods_receipt, approve_request, receive_order
from logic.production import complete_run, consume_requirement, publish_bom_version, release_run
from logic.sales import record_payment
from logic.stock_locations import ensure_central_warehouse
from testing.accounting_helpers import seed_accounts
from logic.ledger import LEGAL_LEDGER


class PhaseRolloutControlsTests(TestCase):
    def setUp(self):
        seed_accounts(ledger=LEGAL_LEDGER)
        self.warehouse = ensure_central_warehouse()
        self.material = Material.objects.create(name="Control material", unit_cost=10)

    @override_settings(FEATURE_ACTUAL_COST_PRODUCTION=False)
    def test_server_side_feature_gate_blocks_entry_point(self):
        with self.assertRaises(FeatureDisabledError):
            publish_bom_version(Product(name="disabled"))

    def test_controls_find_negative_available_lot_mismatch_and_queue(self):
        InventoryTransaction.objects.create(
            material=self.material,
            quantity=1,
            unit_cost=10,
            reason="legacy",
        )
        InventoryReservation.objects.create(
            material=self.material,
            location_kind="warehouse",
            warehouse=self.warehouse,
            quantity=2,
        )
        InventoryCostLayer.objects.create(
            material=self.material,
            original_qty=2,
            qty_remaining=1,
            unit_cost=10,
        )
        ReconciliationQueue.objects.create(
            domain="inventory",
            source_type="InventoryTransaction",
            source_key="legacy-1",
            reason="ambiguous",
        )
        today = timezone.localdate()
        report = discrepancy_scan({
            "date_from": (today - timedelta(days=1)).isoformat(),
            "date_to": (today + timedelta(days=1)).isoformat(),
            "domains": "inventory,reconciliation",
            "limit": 100,
        })
        kinds = {row["kind"] for row in report["items"]}
        self.assertIn("inventory_negative_available", kinds)
        self.assertIn("inventory_lot_remaining_mismatch", kinds)
        self.assertIn("reconciliation_queue_open", kinds)

    def test_immutable_cost_layer_rejects_identity_mutation(self):
        layer = InventoryCostLayer.objects.create(
            material=self.material,
            original_qty=1,
            qty_remaining=1,
            unit_cost=10,
        )
        layer.unit_cost = 99
        with self.assertRaises(ValueError):
            layer.save()
        with self.assertRaises(ValueError):
            InventoryCostLayer.objects.filter(pk=layer.pk).update(unit_cost=99)

    def test_rollout_command_dry_run(self):
        call_command("phase_rollout_status", "--json")


class PhaseOneToSixEndToEndTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        media_override = override_settings(MEDIA_ROOT=self.media_root)
        media_override.enable()
        self.addCleanup(media_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)
        seed_accounts(ledger=LEGAL_LEDGER)
        self.user = get_user_model().objects.create_superuser(
            username="phase-e2e", password="secret123"
        )
        self.branch, _ = Branch.objects.get_or_create(
            code="phase_e2e", defaults={"label": "Phase E2E"}
        )
        self.warehouse = ensure_central_warehouse()
        self.location = {"kind": "warehouse", "warehouse": self.warehouse}
        self.customer = Customer.objects.create(
            full_name="E2E customer", phone="09120000777"
        )
        self.product = Product.objects.create(name="E2E sofa", default_price=1000)
        self.variant = ProductVariant.objects.create(
            product=self.product, color_name="Blue", price=1000
        )
        self.material = Material.objects.create(
            name="E2E wood",
            unit="m",
            unit_cost=100,
            valuation_method=Material.VALUATION_FIFO,
        )
        ProductMaterial.objects.create(
            product=self.product, material=self.material, quantity=2
        )
        payable = get_account("accounts_payable", ledger=LEGAL_LEDGER)
        supplier_account = Account.objects.create(
            ledger=payable.ledger,
            parent=payable,
            slug="supplier-phase-e2e",
            code="E2E",
            name="E2E supplier",
            account_class=payable.account_class,
            normal_balance=payable.normal_balance,
        )
        self.supplier = MaterialSupplier.objects.create(
            code="E2E", name="E2E supplier", account=supplier_account
        )

    def test_exact_trace_with_retries_from_shortage_through_return(self):
        receive_stock(self.material, 1, 100, location=self.location)
        sale = Sale.objects.create(
            customer=self.customer,
            branch=self.branch,
            workflow_stage_id=Sale.WORKFLOW_STAGE_IN_WAREHOUSE,
            amount=1000,
            final_amount=1000,
            paid_amount=0,
            invoice_number="E2E-1",
            accounting_mode=Sale.ACCOUNTING_MODE_MANUAL,
            recorded_by=self.user,
        )
        sale_line = SaleLineItem.objects.create(
            sale=sale,
            product=self.product,
            variant=self.variant,
            product_name=self.product.name,
            quantity=1,
            unit_price=1000,
            line_total=1000,
        )
        plan = save_fulfillment_plan(
            sale_line,
            [{"route_kind": "factory", "quantity": 1}],
            user=self.user,
        )
        route = plan.lines.get()
        run = route.production_run
        run.refresh_from_db()
        self.assertEqual(run.status, run.STATUS_BLOCKED)
        request = run.production_order.purchase_request_lines.get().request
        request_line = request.lines.get()
        order = approve_request(
            request,
            supplier=self.supplier,
            prices={request_line.pk: 200},
            user=self.user,
        )
        order_line = order.lines.get()
        receipt = receive_order(
            order,
            [{
                "order_line_id": order_line.pk,
                "expected_quantity": 1,
                "received_quantity": 1,
                "unit_price": 200,
            }],
            receipt_number="E2E-GR",
            invoice_number="E2E-INV",
            user=self.user,
        )
        create_attachment(
            SimpleUploadedFile(
                "invoice.pdf", b"%PDF-1.7\nE2E", content_type="application/pdf"
            ),
            source_type="goods_receipt",
            source_id=receipt.pk,
            user=self.user,
        )
        approve_goods_receipt(receipt, user=self.user)
        approve_goods_receipt(receipt, user=self.user)

        release_run(run, user=self.user)
        requirement = run.requirements.get()
        consumed = consume_requirement(
            requirement, user=self.user, idempotency_key="e2e-consume"
        )
        retried = consume_requirement(
            requirement, user=self.user, idempotency_key="e2e-consume"
        )
        self.assertEqual(consumed.pk, retried.pk)
        self.assertEqual(consumed.total_cost, Decimal("300"))
        completion = complete_run(run, user=self.user, idempotency_key="e2e-complete")
        self.assertEqual(
            completion.pk,
            complete_run(run, user=self.user, idempotency_key="e2e-complete").pk,
        )

        delivery = deliver_sale(sale, user=self.user, idempotency_key="e2e-delivery")
        self.assertEqual(
            delivery.pk,
            deliver_sale(sale, user=self.user, idempotency_key="e2e-delivery").pk,
        )
        record_payment(
            sale, 1000, recorded_by=self.user, idempotency_key="e2e-payment"
        )
        record_payment(
            sale, 1000, recorded_by=self.user, idempotency_key="e2e-payment"
        )
        delivery_line = delivery.lines.get()
        returned = return_sale(
            delivery,
            [{"delivery_line_id": delivery_line.pk, "quantity": 1}],
            reason="E2E return",
            user=self.user,
            idempotency_key="e2e-return",
        )
        self.assertEqual(
            returned.pk,
            return_sale(
                delivery,
                [{"delivery_line_id": delivery_line.pk, "quantity": 1}],
                reason="E2E return",
                user=self.user,
                idempotency_key="e2e-return",
            ).pk,
        )
        trace = delivery_trace(sale)
        self.assertEqual(trace["delivery"]["total_actual_cogs"], "300")
        self.assertEqual(
            trace["delivery"]["lines"][0]["product_lot_uuid"],
            str(run.product_lot.uuid),
        )
        self.assertEqual(
            [row["unit_cost"] for row in consumed.consumption.allocations.order_by("id").values(
                "unit_cost"
            )],
            [Decimal("100"), Decimal("200")],
        )
        self.assertEqual(len(trace["payments"]), 1)
        self.assertEqual(len(trace["delivery"]["returns"]), 1)
        today = timezone.localdate()
        controls = discrepancy_scan({
            "date_from": (today - timedelta(days=1)).isoformat(),
            "date_to": (today + timedelta(days=1)).isoformat(),
            "domains": "inventory,production,procurement,delivery",
            "limit": 500,
        })
        invariant_failures = {
            "inventory_allocation_sum_mismatch",
            "inventory_consumption_movement_mismatch",
            "production_consumption_without_event",
            "approved_receipt_missing_lot_or_journal",
            "delivered_sale_missing_accounting_event",
        }
        self.assertFalse(
            invariant_failures & {row["kind"] for row in controls["items"]},
            controls["items"],
        )
