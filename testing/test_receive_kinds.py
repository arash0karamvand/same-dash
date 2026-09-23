"""تست نوع دریافت و قطع خط مدل اول (کلاف)."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.models import (
    BetaAssemblyJob,
    BetaClearanceJob,
    BetaPaintOrder,
    BetaQcInspection,
    BetaUpholsteryJob,
    Branch,
    Customer,
    Material,
    Product,
    Sale,
    SaleLineItem,
    Warehouse,
    WorkshopRecipe,
)
from logic.production_line import spawn_workshop_jobs_for_sale
from logic.products import product_to_dict
from logic.receive_kinds import create_office_factory_work
from logic.sales import record_sale
from logic.workshop_recipes import apply_product_workset, create_recipe, fabric_named_ids


class ReceiveKindsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="office_recv", password="secret123")
        Branch.objects.get_or_create(code="branch_1", defaults={"label": "کمرد", "is_active": True})
        self.warehouse = Warehouse.objects.create(code="wh_recv", label="انبار تست دریافت")
        self.customer = Customer.objects.create(full_name="مشتری فروشگاه", phone="09120000001")
        self.product = Product.objects.create(name="مبل اداری", default_price=1500000)

    def test_shop_sale_is_customer_receive_kind(self):
        sale = record_sale(
            self.customer,
            1500000,
            branch="branch_1",
        )
        self.assertEqual(sale.receive_kind, Sale.RECEIVE_KIND_CUSTOMER)
        self.assertEqual(sale.customer_id, self.customer.id)

    def test_office_factory_work_without_customer(self):
        cases = [
            (Sale.RECEIVE_KIND_BRANCH_FLOOR, {"source_branch": "branch_1"}),
            (Sale.RECEIVE_KIND_WAREHOUSE, {"warehouse_id": self.warehouse.id}),
            (Sale.RECEIVE_KIND_REPAIR, {}),
            (Sale.RECEIVE_KIND_MERCHANT, {"contract_party": "بازرگان پارس"}),
        ]
        for kind, extra in cases:
            sale = create_office_factory_work(
                self.user,
                {
                    "receive_kind": kind,
                    "branch": "branch_1",
                    "line_items": [{"product_id": self.product.id, "quantity": 1}],
                    **extra,
                },
            )
            self.assertIsNone(sale.customer_id)
            self.assertEqual(sale.receive_kind, kind)
            self.assertEqual(sale.workflow_stage_id, Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED)
            self.assertEqual(sale.fulfillment_route, Sale.FULFILLMENT_ROUTE_FACTORY)
            if kind == Sale.RECEIVE_KIND_MERCHANT:
                self.assertEqual(sale.contract_party, "بازرگان پارس")

    def test_merchant_requires_contract_party(self):
        with self.assertRaises(ValueError):
            create_office_factory_work(
                self.user,
                {
                    "receive_kind": Sale.RECEIVE_KIND_MERCHANT,
                    "branch": "branch_1",
                    "line_items": [{"product_id": self.product.id, "quantity": 1}],
                },
            )


class FrameLineCutoffTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(full_name="مشتری خط", phone="09121110000")
        self.paint = create_recipe(
            {
                "kind": WorkshopRecipe.KIND_PAINT,
                "name": "گردویی گالن",
                "color_name": "گردویی",
                "paint_category": WorkshopRecipe.PAINT_CATEGORY_PAINT,
                "stock_unit": "گالن",
                "materials": [],
            }
        )
        self.fabric = create_recipe({
            "kind": WorkshopRecipe.KIND_FABRIC,
            "name": "مخمل",
            "materials": [],
            **fabric_named_ids(),
        })
        self.foam = create_recipe({"kind": WorkshopRecipe.KIND_FOAM, "name": "اسفنج سرد", "materials": []})
        self.webbing = create_recipe({"kind": WorkshopRecipe.KIND_WEBBING, "name": "تسمه متری", "materials": []})

    def _sale(self, product):
        from logic.workshop_recipes import build_workset_from_product

        sale = Sale.objects.create(
            customer=self.customer,
            amount=product.default_price,
            final_amount=product.default_price,
            paid_amount=product.default_price,
            workflow_stage_id=Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
        )
        SaleLineItem.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            quantity=1,
            unit_price=product.default_price,
            line_total=product.default_price,
            workset_config=build_workset_from_product(product),
        )
        return sale

    def test_sofa_without_paint_skips_paint_and_assembly(self):
        product = Product.objects.create(name="مبل بدون رنگ", default_price=2000000)
        apply_product_workset(
            product,
            {
                "paint_recipe_id": self.paint.id,
                "fabric_recipe_id": self.fabric.id,
                "foam_recipe_id": self.foam.id,
                "webbing_recipe_id": self.webbing.id,
                "needs_paint": False,
                "pipeline_end": "upholstery",
            },
        )
        product.save()
        sale = self._sale(product)
        spawned = spawn_workshop_jobs_for_sale(sale)
        self.assertNotIn("paint", spawned["created"])
        self.assertNotIn("assembly", spawned["created"])
        self.assertIn("upholstery", spawned["created"])
        self.assertIn("qc", spawned["created"])
        self.assertIn("clearance", spawned["created"])
        self.assertEqual(BetaPaintOrder.objects.filter(sale=sale).count(), 0)
        self.assertEqual(BetaAssemblyJob.objects.filter(sale=sale).count(), 0)
        self.assertEqual(BetaUpholsteryJob.objects.filter(sale=sale).count(), 1)
        self.assertEqual(BetaQcInspection.objects.filter(sale=sale).count(), 1)
        self.assertEqual(BetaClearanceJob.objects.filter(sale=sale).count(), 1)

    def test_side_table_spawns_assembly(self):
        product = Product.objects.create(name="جلو مبلی", default_price=800000)
        apply_product_workset(
            product,
            {
                "fabric_recipe_id": self.fabric.id,
                "needs_paint": False,
                "pipeline_end": "assembly",
            },
        )
        product.save()
        sale = self._sale(product)
        spawned = spawn_workshop_jobs_for_sale(sale)
        self.assertIn("assembly", spawned["created"])
        self.assertIn("qc", spawned["created"])
        self.assertEqual(BetaAssemblyJob.objects.filter(sale=sale).count(), 1)

    def test_gallon_unit_persists_on_paint_recipe(self):
        material = Material.objects.create(
            name="رنگ پلی‌استر",
            usage_kind=Material.USAGE_PAINT,
            unit="گالن",
            unit_cost=10,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        recipe = create_recipe(
            {
                "kind": WorkshopRecipe.KIND_PAINT,
                "name": "کرم گالن",
                "paint_category": WorkshopRecipe.PAINT_CATEGORY_PAINT,
                "stock_unit": "گالن",
                "materials": [{"material_id": material.id, "quantity": 2, "unit": "گالن"}],
            }
        )
        self.assertEqual(recipe.materials.first().unit, "گالن")
        product = Product.objects.create(name="مبل گالن", default_price=1000000)
        apply_product_workset(product, {"paint_recipe_id": recipe.id, "needs_paint": True})
        product.save()
        data = product_to_dict(product, audience="factory")
        self.assertEqual(data["workset"]["paint"]["materials"][0]["unit"], "گالن")
        self.assertTrue(data["needs_paint"])
        self.assertEqual(data["pipeline_end"], "upholstery")
        self.assertEqual(data["build_model"], "frame_line")
