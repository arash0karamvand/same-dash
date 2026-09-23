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
    FabricCatalogNode,
    WorkshopRecipe,
)
from logic.materials import committed_material_demand, compute_factory_order_material_requirements
from logic.production_line import spawn_workshop_jobs_for_sale
from logic.products import product_to_dict, resolve_line_item_from_catalog
from logic.sale_workflow import receive_factory_order
from logic.workshop_recipes import (
    apply_product_workset,
    create_catalog_node,
    create_paint_category,
    create_recipe,
    delete_catalog_node,
    fabric_named_ids,
    filter_recipes,
    recipe_to_dict,
    update_recipe,
)


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
                "paint_category": WorkshopRecipe.PAINT_CATEGORY_PAINT,
                "stock_unit": "کیلوگرم",
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
        fabric = create_recipe({
            "kind": WorkshopRecipe.KIND_FABRIC,
            "name": "مخمل",
            "materials": [],
            **fabric_named_ids(),
        })
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


class PaintRegistrationTests(TestCase):
    def _paint(self, **extra):
        payload = {
            "kind": WorkshopRecipe.KIND_PAINT,
            "name": "سیلر سنباده‌خور",
            "paint_category": WorkshopRecipe.PAINT_CATEGORY_PUTTY,
            "stock_unit": "لیتر",
            "current_stock": "4",
            "min_stock": "10",
            "unit_cost": "1000",
            "brand": "کارخانه نمونه",
        }
        payload.update(extra)
        return create_recipe(payload)

    def test_paint_requires_category_and_unit(self):
        with self.assertRaises(ValueError):
            create_recipe({"kind": WorkshopRecipe.KIND_PAINT, "name": "بدون دسته"})
        with self.assertRaises(ValueError):
            create_recipe(
                {
                    "kind": WorkshopRecipe.KIND_PAINT,
                    "name": "بدون واحد",
                    "paint_category": WorkshopRecipe.PAINT_CATEGORY_PAINT,
                }
            )

    def test_paint_registration_assigns_code_value_and_shortage(self):
        recipe = self._paint()
        data = recipe_to_dict(recipe)
        self.assertEqual(data["item_code"], "PNT-0001")
        self.assertEqual(data["paint_category_display"], "بتونه و سیلر")
        self.assertEqual(data["stock_status"], "low")
        self.assertEqual(data["stock_value"], 4000)
        self.assertEqual(data["brand"], "کارخانه نمونه")
        self.assertEqual(data["storage_shelf"], "")

    def test_zero_stock_is_separate_from_shortage(self):
        data = recipe_to_dict(self._paint(current_stock="0", min_stock="2"))
        self.assertEqual(data["stock_status"], "zero")

    def test_duplicate_code_is_rejected(self):
        first = self._paint(item_code="PNT-CUSTOM")
        with self.assertRaises(ValueError):
            self._paint(name="قلم دوم", item_code="PNT-CUSTOM")
        self.assertEqual(first.item_code, "PNT-CUSTOM")

    def test_negative_stock_and_cost_are_rejected(self):
        with self.assertRaises(ValueError):
            self._paint(current_stock="-1")
        with self.assertRaises(ValueError):
            self._paint(unit_cost="-5")

    def test_search_matches_code_and_brand(self):
        recipe = self._paint(item_code="PNT-SEARCH", brand="برند ویژه")
        found = list(filter_recipes(WorkshopRecipe.objects.all(), search="PNT-SEARCH"))
        self.assertEqual([row.id for row in found], [recipe.id])
        by_brand = list(filter_recipes(WorkshopRecipe.objects.all(), search="برند ویژه"))
        self.assertEqual([row.id for row in by_brand], [recipe.id])

    def test_fabric_recipe_skips_paint_fields(self):
        recipe = create_recipe({
            "kind": WorkshopRecipe.KIND_FABRIC,
            "name": "کتان",
            **fabric_named_ids(brand="منسوجات آریا", cloth="کتان شست"),
        })
        self.assertEqual(recipe.paint_category, "")
        self.assertTrue(recipe.item_code.startswith("KLT-"))
        self.assertEqual(recipe.stock_unit, "متر")

    def test_update_keeps_blank_brand_and_rejects_bad_unit(self):
        recipe = self._paint(brand="", storage_shelf="")
        updated = update_recipe(recipe, {"current_stock": "12", "min_stock": "10"})
        data = recipe_to_dict(updated)
        self.assertEqual(data["stock_status"], "ok")
        self.assertEqual(data["brand"], "")
        with self.assertRaises(ValueError):
            update_recipe(recipe, {"stock_unit": "متر"})

    def test_custom_paint_category_can_be_created_and_used(self):
        option = create_paint_category("رزین")
        self.assertTrue(option.code.startswith("c"))
        recipe = self._paint(paint_category=option.code, name="رزین پلی‌استر")
        self.assertEqual(recipe_to_dict(recipe)["paint_category_display"], "رزین")
        with self.assertRaises(ValueError):
            create_paint_category("رزین")
        with self.assertRaises(ValueError):
            create_paint_category("تینر")


TINY_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class FabricCaliteTests(TestCase):
    def _fabric(self, **extra):
        payload = {
            "kind": WorkshopRecipe.KIND_FABRIC,
            "name": "نشست روشن",
            "current_stock": "18",
            "min_stock": "6",
            "unit_cost": "250000",
            "roll_count": 2,
            "image_url": TINY_PNG,
            "technical_specs": "عرض ۱۵۰",
            **fabric_named_ids(),
        }
        payload.update(extra)
        return create_recipe(payload)

    def test_paint_does_not_require_fabric_fields(self):
        recipe = create_recipe({
            "kind": WorkshopRecipe.KIND_PAINT,
            "name": "سیلرکاری",
            "paint_category": WorkshopRecipe.PAINT_CATEGORY_PUTTY,
            "stock_unit": "لیتر",
        })
        data = recipe_to_dict(recipe)
        self.assertEqual(data["fabric_category"], "")
        self.assertEqual(data["company_code"], "")
        self.assertEqual(data["origin_country"], "")
        self.assertEqual(data["gallery_urls"], [])
        self.assertTrue(data["item_code"].startswith("PNT-"))

    def test_fabric_requires_the_catalog_chain(self):
        with self.assertRaises(ValueError):
            create_recipe({"kind": WorkshopRecipe.KIND_FABRIC, "name": "بدون زنجیره"})
        with self.assertRaises(ValueError):
            self._fabric(fabric_brand_id=None, name="بدون برند")

    def test_calite_assigns_code_and_keeps_meters(self):
        data = recipe_to_dict(self._fabric())
        self.assertEqual(data["item_code"], "KLT-0001")
        self.assertEqual(data["company_display"], "بافندگی نورا")
        self.assertEqual(data["fabric_category_display"], "مخمل ساده")
        self.assertEqual(data["color_name"], "استخوانی")
        self.assertEqual(data["stock_unit"], "متر")
        self.assertEqual(data["current_stock"], 18)
        self.assertEqual(data["roll_count"], 2)
        self.assertEqual(data["stock_status"], "ok")
        self.assertEqual(data["origin_country"], "ایران")
        self.assertTrue(data["image_url"].startswith("data:image/png"))

    def test_second_calite_increments_code(self):
        self._fabric(name="اول")
        second = recipe_to_dict(self._fabric(name="دوم", color_name="دودی"))
        self.assertEqual(second["item_code"], "KLT-0002")

    def test_catalog_chain_rejects_bad_parent_and_duplicates(self):
        country = FabricCatalogNode.objects.get(kind=FabricCatalogNode.KIND_COUNTRY, name="چین")
        with self.assertRaises(ValueError):
            create_catalog_node({"kind": "color", "name": "قرمز", "parent_id": country.id})
        brand = create_catalog_node({"kind": "brand", "name": "نساجی پارس", "parent_id": country.id})
        with self.assertRaises(ValueError):
            create_catalog_node({"kind": "brand", "name": "نساجی پارس", "parent_id": country.id})
        color = create_catalog_node({"kind": "color", "name": "یشمی", "parent_id": brand.id})
        cloth = create_catalog_node({"kind": "type", "name": "ابریشم خام", "parent_id": color.id})
        recipe = self._fabric(
            name="ابریشم پارس",
            fabric_country_id=country.id,
            fabric_brand_id=brand.id,
            fabric_color_id=color.id,
            fabric_type_id=cloth.id,
        )
        data = recipe_to_dict(recipe)
        self.assertEqual(data["company_display"], "نساجی پارس")
        self.assertEqual(data["fabric_category_display"], "ابریشم خام")
        self.assertEqual(data["color_name"], "یشمی")
        with self.assertRaises(ValueError):
            delete_catalog_node(color)
        with self.assertRaises(ValueError):
            delete_catalog_node(cloth)

    def test_mismatched_color_is_rejected(self):
        aria = fabric_named_ids(brand="منسوجات آریا")
        nura = fabric_named_ids()
        with self.assertRaises(ValueError):
            self._fabric(fabric_brand_id=nura["fabric_brand_id"], fabric_color_id=aria["fabric_color_id"])

    def test_negative_meters_and_http_image_are_rejected(self):
        with self.assertRaises(ValueError):
            self._fabric(current_stock="-1")
        with self.assertRaises(ValueError):
            self._fabric(roll_count=-2)
        with self.assertRaises(ValueError):
            self._fabric(unit_cost="-5")
        with self.assertRaises(ValueError):
            self._fabric(image_url="https://example.com/swatch.jpg")
        with self.assertRaises(ValueError):
            self._fabric(image_url="not-a-link")

    def test_brand_filter_shows_only_that_brand(self):
        nura = self._fabric(name="نورا", item_code="KLT-NURA")
        aria_ids = fabric_named_ids(brand="منسوجات آریا")
        self._fabric(name="آریا", item_code="KLT-ARIA", **aria_ids)
        found = list(filter_recipes(
            WorkshopRecipe.objects.all(),
            kind="fabric",
            brand_id=nura.fabric_brand_id,
        ))
        self.assertEqual([row.id for row in found], [nura.id])

    def test_update_keeps_brand_when_only_meters_change(self):
        recipe = self._fabric()
        updated = update_recipe(recipe, {"current_stock": "4", "min_stock": "6"})
        data = recipe_to_dict(updated)
        self.assertEqual(data["company_display"], "بافندگی نورا")
        self.assertEqual(data["stock_status"], "low")
        self.assertTrue(data["image_url"].startswith("data:image/png"))
