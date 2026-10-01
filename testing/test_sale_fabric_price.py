"""قیمت فروش از متراژ قفل‌شدهٔ کار و نرخ پارچهٔ انتخاب‌شده."""

from decimal import Decimal

from django.test import TestCase

from backend.models import Material, Product, WorkshopRecipe
from logic.products import resolve_line_item_from_catalog
from logic.workshop_recipes import create_recipe, fabric_named_ids


class SaleFabricPriceTests(TestCase):
    def setUp(self):
        self.cloth = Material.objects.create(
            name="نخ پارچه",
            unit="متر",
            unit_cost=1,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        self.paint = create_recipe({
            "kind": WorkshopRecipe.KIND_PAINT,
            "name": "گردویی",
            "color_name": "گردویی",
            "paint_category": WorkshopRecipe.PAINT_CATEGORY_PAINT,
            "stock_unit": "کیلوگرم",
            "materials": [],
        })
        self.job_fabric = create_recipe({
            "kind": WorkshopRecipe.KIND_FABRIC,
            "name": "پارچه کار",
            "unit_cost": "1000",
            "materials": [{"material_id": self.cloth.id, "quantity": 4, "unit": "متر"}],
            **fabric_named_ids(color="استخوانی", cloth="مخمل ساده"),
        })
        self.sale_fabric = create_recipe({
            "kind": WorkshopRecipe.KIND_FABRIC,
            "name": "مخمل فروش",
            "unit_cost": "50000",
            "materials": [{"material_id": self.cloth.id, "quantity": 99, "unit": "متر"}],
            **fabric_named_ids(color="کرم"),
        })
        self.foam = create_recipe({
            "kind": WorkshopRecipe.KIND_FOAM,
            "name": "فوم سرد",
            "materials": [],
        })
        self.product = Product.objects.create(name="مبل نمونه", default_price=1)
        self.product.suite_config = [{
            "piece_label": "کنار",
            "quantity": 2,
            "needs_paint": True,
            "fabric": {
                "id": self.job_fabric.id,
                "name": "پارچه کار",
                "materials": [{"material_id": self.cloth.id, "quantity": 4, "unit": "متر"}],
            },
            "foam": {"id": self.foam.id, "name": "فوم سرد", "materials": []},
        }]
        self.product.save(update_fields=["suite_config"])

    def test_price_uses_job_meters_and_selected_fabric_rate(self):
        resolved = resolve_line_item_from_catalog({
            "product_id": self.product.id,
            "quantity": 3,
            "fabric_recipe_id": self.sale_fabric.id,
            "paint_recipe_id": self.paint.id,
        })
        self.assertEqual(resolved["unit_price"], Decimal("400000"))
        self.assertEqual(resolved["quantity"], 3)
        self.assertEqual(resolved["color_name"], "گردویی")
        self.assertIn("مخمل فروش", resolved["fabric"])
        piece = resolved["workset_config"]["pieces"][0]
        self.assertEqual(piece["foam"]["name"], "فوم سرد")
        self.assertEqual(piece["fabric"]["materials"][0]["quantity"], 4)
        self.assertEqual(resolved["workset_config"]["sale_choices"]["meters"], 8)

    def test_missing_meters_block_a_made_up_price(self):
        self.product.suite_config[0]["fabric"]["materials"] = []
        self.product.save(update_fields=["suite_config"])
        with self.assertRaises(ValueError) as caught:
            resolve_line_item_from_catalog({
                "product_id": self.product.id,
                "fabric_recipe_id": self.sale_fabric.id,
                "paint_recipe_id": self.paint.id,
            })
        self.assertIn("متراژ", str(caught.exception))

    def test_catalog_price_stays_when_seller_does_not_choose_fabric(self):
        plain = Product.objects.create(name="میز", default_price=50000)
        resolved = resolve_line_item_from_catalog({"product_id": plain.id, "quantity": 1})
        self.assertEqual(resolved["unit_price"], Decimal("50000"))
