from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from backend.models import (
    BOMLine,
    InventoryTransaction,
    Material,
    MaterialRequirement,
    Product,
    ProductLot,
    ProductMaterial,
    ProductVariant,
    ProductionOrder,
    ProductionRun,
)
from logic.inventory_costing import receive_stock
from logic.production import (
    complete_run,
    consume_extra,
    consume_requirement,
    publish_bom_version,
    record_scrap,
    release_run,
    return_material,
)
from logic.stock_locations import ensure_central_warehouse
from logic.ledger import OFFICE_LEDGER, ensure_ledgers
from testing.accounting_helpers import seed_accounts


class ProductionPhaseFiveTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="production-admin", email="production@example.test", password="pass"
        )
        ensure_ledgers()
        seed_accounts(ledger=OFFICE_LEDGER)
        self.product = Product.objects.create(name="Actual-cost sofa")
        self.variant = ProductVariant.objects.create(product=self.product, color_name="Blue")
        self.material = Material.objects.create(
            name="FIFO wood", unit="m", unit_cost=100, valuation_method=Material.VALUATION_FIFO
        )
        ProductMaterial.objects.create(product=self.product, material=self.material, quantity=3)
        self.warehouse = ensure_central_warehouse()
        self.location = {
            "kind": InventoryTransaction.LOCATION_WAREHOUSE,
            "warehouse": self.warehouse,
        }
        self.order = ProductionOrder.objects.create(
            delivery_date=date.today(), product_name=self.product.name, created_by=self.user
        )

    def _run(self, quantity=2):
        bom = publish_bom_version(self.product, user=self.user)
        run = ProductionRun.objects.create(
            production_order=self.order,
            product=self.product,
            variant=self.variant,
            bom_version=bom,
            quantity=quantity,
            warehouse=self.warehouse,
            created_by=self.user,
        )
        line = bom.lines.get()
        requirement = MaterialRequirement.objects.create(
            run=run,
            bom_line=line,
            material=self.material,
            required_quantity=line.quantity * quantity,
        )
        return run, requirement

    def test_published_version_is_frozen_and_validates_material_approval(self):
        bom = publish_bom_version(self.product, user=self.user)
        line = bom.lines.get()
        line.quantity = 99
        with self.assertRaises(ValidationError):
            line.save()
        self.material.is_active = False
        self.material.save(update_fields=["is_active"])
        with self.assertRaisesRegex(ValueError, "active and approved"):
            publish_bom_version(self.product, user=self.user)

    def test_shortage_blocks_then_fifo_consumption_posts_actual_cost(self):
        run, requirement = self._run()
        release_run(run, user=self.user)
        run.refresh_from_db()
        requirement.refresh_from_db()
        self.assertEqual(run.status, ProductionRun.STATUS_BLOCKED)
        self.assertEqual(requirement.shortage_quantity, Decimal("6"))

        receive_stock(self.material, 5, 100, location=self.location)
        receive_stock(self.material, 5, 200, location=self.location)
        release_run(run, user=self.user)
        requirement.refresh_from_db()
        event = consume_requirement(requirement, user=self.user)
        self.assertEqual(event.total_cost, Decimal("700"))
        self.assertEqual(
            list(event.consumption.allocations.values_list("quantity", flat=True)),
            [Decimal("5"), Decimal("1")],
        )
        self.assertIsNotNone(event.financial_event.journal_id)

    def test_extra_requires_authorization_and_reason(self):
        run, _requirement = self._run()
        run.status = ProductionRun.STATUS_IN_PROGRESS
        run.save(update_fields=["status"])
        receive_stock(self.material, 2, 100, location=self.location)
        plain = get_user_model().objects.create_user(username="plain")
        with self.assertRaises(PermissionDenied):
            consume_extra(
                run, self.material, 1, reason="repair", user=plain, idempotency_key="extra-1"
            )
        with self.assertRaisesRegex(ValueError, "reason"):
            consume_extra(
                run, self.material, 1, reason="", user=self.user, idempotency_key="extra-2"
            )

    def test_return_reverses_wip_and_completion_creates_one_actual_cost_lot(self):
        receive_stock(self.material, 10, 100, location=self.location)
        run, requirement = self._run()
        release_run(run, user=self.user)
        consumed = consume_requirement(requirement, user=self.user)
        returned = return_material(consumed, 1, reason="unused", user=self.user)
        self.assertEqual(returned.total_cost, Decimal("100"))
        self.assertIsNotNone(returned.financial_event.journal_id)

        completion = complete_run(run, overhead_cost=300, user=self.user)
        lot = ProductLot.objects.get(run=run)
        self.assertEqual(lot.total_cost, Decimal("800"))
        self.assertEqual(lot.unit_cost, Decimal("400"))
        self.assertEqual(lot.cost_layer.qty_remaining, Decimal("2"))
        duplicate = complete_run(run, overhead_cost=300, user=self.user)
        self.assertEqual(duplicate.pk, completion.pk)
        self.assertEqual(ProductLot.objects.filter(run=run).count(), 1)

    def test_scrap_reclassifies_wip_without_mutating_consumption(self):
        receive_stock(self.material, 10, 100, location=self.location)
        run, requirement = self._run()
        release_run(run, user=self.user)
        consumed = consume_requirement(requirement, user=self.user)
        scrap = record_scrap(
            run, self.material, 1, reason="abnormal damage",
            user=self.user, idempotency_key="scrap-1",
        )
        consumed.refresh_from_db()
        self.assertEqual(consumed.quantity, Decimal("6"))
        self.assertEqual(scrap.total_cost, Decimal("100"))
        self.assertIsNotNone(scrap.financial_event.journal_id)

    def test_production_api_enforces_permissions(self):
        plain = get_user_model().objects.create_user(username="production-view-denied")
        self.client.force_login(plain)
        denied = self.client.get("/api/production/runs/")
        self.assertEqual(denied.status_code, 403)
        self.client.force_login(self.user)
        allowed = self.client.get("/api/production/runs/")
        self.assertEqual(allowed.status_code, 200)
