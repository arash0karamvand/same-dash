from django.test import TestCase

from backend.models import Material, Product, ProductMaterial, WorkshopRecipe
from logic.materials import mask_cost_fields, resolve_material_requirements


class FactoryBundleCostingTests(TestCase):
    def setUp(self):
        self.base = Material.objects.create(
            name="چوب پایه",
            unit="متر",
            unit_cost=100,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        self.cloth = Material.objects.create(
            name="پارچه",
            unit="متر",
            unit_cost=200,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        self.fabric = WorkshopRecipe.objects.create(
            kind=WorkshopRecipe.KIND_FABRIC,
            name="پارچه تست",
            unit_cost=500,
            is_active=True,
        )
        self.product = Product.objects.create(name="دست تست", default_price=1000)
        ProductMaterial.objects.create(product=self.product, material=self.base, quantity=2)

    def test_resolver_uses_exact_piece_snapshot_quantities(self):
        rows = resolve_material_requirements(
            product=self.product,
            workset_config={
                "pieces": [
                    {
                        "piece_kind": "sofa_3",
                        "arm_style": "two",
                        "quantity": 2,
                        "fabric": {
                            "id": self.fabric.id,
                            "materials": [
                                {"material_id": self.cloth.id, "quantity": 3, "unit": "متر"}
                            ],
                        },
                    }
                ]
            },
            quantity=2,
        )
        by_id = {row["material_id"]: row for row in rows}
        self.assertEqual(by_id[self.base.id]["required_quantity"], 4.0)
        self.assertEqual(by_id[self.cloth.id]["required_quantity"], 12.0)
        self.assertEqual(by_id[self.cloth.id]["line_cost"], 2400)

    def test_cost_mask_is_recursive(self):
        masked = mask_cost_fields({
            "material_cost_total": 500,
            "rows": [{"unit_cost": 10, "quantity": 2, "material": {"inventory_value": 20}}],
        })
        self.assertNotIn("material_cost_total", masked)
        self.assertNotIn("unit_cost", masked["rows"][0])
        self.assertNotIn("inventory_value", masked["rows"][0]["material"])
        self.assertEqual(masked["rows"][0]["quantity"], 2)
