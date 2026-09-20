"""تست دست‌کار محصول، کمبود بین‌سفارشی و ساخت خودکار کارها هنگام دریافت."""

from decimal import Decimal

from django.test import TestCase

from backend.models import (
    BetaCarpentryWorkshop,
    BetaCushionJob,
    BetaFabricNeed,
    BetaFoamJob,
    BetaPaintOrder,
    BetaUpholsteryJob,
    Customer,
    InventoryTransaction,
    Material,
    Product,
    Sale,
    SaleLineItem,
    WorkshopRecipe,
)
from logic.materials import committed_material_demand, compute_factory_order_material_requirements
from logic.production_line import spawn_workshop_jobs_for_sale
from logic.products import product_to_dict, resolve_line_item_from_catalog
from logic.sale_workflow import receive_factory_order
from logic.workshop_recipes import apply_product_workset, create_recipe


class WorkshopLineTests(TestCase):
    def setUp(self):
        self.user = self._user()
        self.customer = Customer.objects.create(full_name="مشتری خط", phone="09121112233")
        self.paint_material = Material.objects.create(
            name="رنگ پلی‌استر",
            usage_kind=Material.USAGE_PAINT,
            unit="کیلو",
            unit_cost=100,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        InventoryTransaction.objects.create(
            material=self.paint_material,
            quantity=1,
            unit_cost=100,
            reason="initial_stock",
        )
        self.recipe = create_recipe(
            {
                "kind": WorkshopRecipe.KIND_PAINT,
                "name": "گردویی",
                "color_name": "گردویی",
                "materials": [{"material_id": self.paint_material.id, "quantity": 1, "unit": "کیلو"}],
            }
        )
        self.product = Product.objects.create(name="مبل تست دست‌کار", default_price=2000000)
        apply_product_workset(self.product, {"paint_recipe_id": self.recipe.id})
        self.product.save()

    def _user(self):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(username="line_user", password="secret123")

    def _sale(self, *, stage, quantity=1, workset=None):
        sale = Sale.objects.create(
            customer=self.customer,
            amount=2000000,
            final_amount=2000000,
            paid_amount=2000000,
            workflow_stage_id=stage,
        )
        config = workset
        if config is None:
            from logic.workshop_recipes import build_workset_from_product

            config = build_workset_from_product(self.product)
        SaleLineItem.objects.create(
            sale=sale,
            product=self.product,
            product_name=self.product.name,
            quantity=quantity,
            unit_price=2000000,
            line_total=2000000 * quantity,
            workset_config=config,
        )
        return sale

    def test_product_workset_serialization(self):
        data = product_to_dict(self.product, audience="factory")
        self.assertEqual(data["paint_recipe"]["id"], self.recipe.id)
        self.assertEqual(data["workset"]["paint"]["name"], "گردویی")
        self.assertEqual(data["workset"]["paint"]["materials"][0]["material_id"], self.paint_material.id)

    def test_sale_line_snapshots_workset(self):
        resolved = resolve_line_item_from_catalog({"product_id": self.product.id, "quantity": 2})
        self.assertEqual(resolved["workset_config"]["paint"]["name"], "گردویی")
        self.assertEqual(len(resolved["workset_config"]["paint"]["materials"]), 1)

    def test_cross_order_shortage_uses_queue_not_raw_stock(self):
        first = self._sale(stage=Sale.WORKFLOW_STAGE_IN_PRODUCTION, quantity=1)
        first_only = compute_factory_order_material_requirements(first)
        first_row = next(item for item in first_only if item["material_id"] == self.paint_material.id)
        self.assertTrue(first_row["sufficient"])

        second = self._sale(stage=Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED, quantity=1)
        committed = committed_material_demand(exclude_sale_id=second.pk)
        self.assertEqual(committed[self.paint_material.id], Decimal("1"))

        second_reqs = compute_factory_order_material_requirements(second)
        paint_row = next(item for item in second_reqs if item["material_id"] == self.paint_material.id)
        self.assertFalse(paint_row["sufficient"])
        self.assertEqual(paint_row["committed_by_others"], 1.0)
        self.assertGreater(paint_row["shortage"], 0)

        raw = compute_factory_order_material_requirements(second, queue_aware=False)
        raw_row = next(item for item in raw if item["material_id"] == self.paint_material.id)
        self.assertTrue(raw_row["sufficient"])

    def test_receive_spawns_workshop_jobs(self):
        workshop = BetaCarpentryWorkshop.objects.create(name="نجاری داخلی", kind=BetaCarpentryWorkshop.KIND_INTERNAL)
        foam = create_recipe({"kind": WorkshopRecipe.KIND_FOAM, "name": "فوم سرد", "materials": []})
        cushion = create_recipe({"kind": WorkshopRecipe.KIND_CUSHION, "name": "کوسن ساده", "materials": []})
        fabric = create_recipe({"kind": WorkshopRecipe.KIND_FABRIC, "name": "مخمل", "color_name": "کرم", "materials": []})
        apply_product_workset(
            self.product,
            {
                "paint_recipe_id": self.recipe.id,
                "foam_recipe_id": foam.id,
                "cushion_recipe_id": cushion.id,
                "fabric_recipe_id": fabric.id,
            },
        )
        self.product.save()
        sale = self._sale(stage=Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED)
        spawned = spawn_workshop_jobs_for_sale(sale)
        self.assertIn("paint", spawned["created"])
        self.assertIn("foam", spawned["created"])
        self.assertIn("cushion", spawned["created"])
        self.assertIn("fabric", spawned["created"])
        self.assertIn("upholstery", spawned["created"])
        self.assertIn("qc", spawned["created"])
        self.assertIn("clearance", spawned["created"])
        self.assertNotIn("assembly", spawned["created"])
        self.assertEqual(BetaPaintOrder.objects.filter(sale=sale).count(), 1)
        self.assertEqual(BetaFoamJob.objects.filter(sale=sale).count(), 1)
        self.assertEqual(BetaCushionJob.objects.filter(sale=sale).count(), 1)
        self.assertEqual(BetaFabricNeed.objects.filter(sale=sale).count(), 1)
        self.assertEqual(BetaUpholsteryJob.objects.filter(sale=sale).count(), 1)

        again = spawn_workshop_jobs_for_sale(sale)
        self.assertEqual(again["created"], [])
        self.assertTrue(workshop.id)

    def test_receive_factory_order_attaches_spawned_jobs(self):
        from django.contrib.auth import get_user_model
        from backend.models import FactoryOrder
        from logic.order_queues import create_office_order_from_sale
        from logic.sale_workflow import approve_office_order

        user = get_user_model().objects.create_user(username="recv_user", password="secret123")
        sale = self._sale(stage=Sale.WORKFLOW_STAGE_PENDING_BRANCH)
        office = create_office_order_from_sale(sale, user)
        approve_office_order(office, user)
        factory = FactoryOrder.objects.get(pk=sale.pk)
        result = receive_factory_order(factory, user)
        self.assertEqual(result.workflow_stage_id, Sale.WORKFLOW_STAGE_IN_PRODUCTION)
        self.assertTrue(getattr(result, "spawned_workshop_jobs", None))
        self.assertIn("paint", result.spawned_workshop_jobs["created"])
        self.assertEqual(BetaPaintOrder.objects.filter(sale_id=sale.pk).count(), 1)
