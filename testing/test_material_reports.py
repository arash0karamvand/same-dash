"""گزارش انبار متریال: تعهد صف، خرید، ظرفیت، کاردکس و مصرف خالص."""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backend.models import Customer, InventoryTransaction, Material, Product, ProductMaterial, Sale, SaleLineItem, WorkshopRecipe
from logic.material_reports import warehouse_report
from logic.workshop_recipes import apply_product_workset, build_workset_from_product, create_recipe
from testing.accounting_helpers import seed_accounts


class MaterialReportTests(TestCase):
    def setUp(self):
        seed_accounts()
        self.customer = Customer.objects.create(full_name="مشتری انبار", phone="09120001122")

    def _material(self, name, *, stock, unit_cost=100, usage=Material.USAGE_FABRIC, unit="متر"):
        material = Material.objects.create(
            name=name,
            usage_kind=usage,
            unit=unit,
            unit_cost=unit_cost,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        if stock:
            InventoryTransaction.objects.create(
                material=material,
                quantity=Decimal(stock),
                unit_cost=unit_cost,
                reason="initial_stock",
            )
        return material

    def _sale(self, product, quantity):
        sale = Sale.objects.create(
            customer=self.customer,
            amount=1000,
            final_amount=1000,
            paid_amount=1000,
            workflow_stage_id=Sale.WORKFLOW_STAGE_IN_PRODUCTION,
        )
        SaleLineItem.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            quantity=quantity,
            unit_price=1000,
            line_total=1000 * quantity,
            workset_config=build_workset_from_product(product),
        )
        return sale

    def test_stock_commitment_and_purchase_suggestion(self):
        cloth = self._material("پارچه", stock=10, unit_cost=50)
        resin = self._material("رزین", stock=5, unit_cost=20, usage=Material.USAGE_PAINT, unit="کیلو")
        product = Product.objects.create(name="صندلی", default_price=1000)
        ProductMaterial.objects.create(product=product, material=cloth, quantity=1)
        ProductMaterial.objects.create(product=product, material=resin, quantity=4)
        self._sale(product, 2)

        stock = warehouse_report({"report": "stock"})
        by_id = {row["material_id"]: row for row in stock["rows"]}
        self.assertEqual(by_id[cloth.id]["on_hand"], 10)
        self.assertEqual(by_id[cloth.id]["committed"], 2)
        self.assertEqual(by_id[cloth.id]["available"], 8)
        self.assertEqual(by_id[resin.id]["committed"], 8)
        self.assertEqual(by_id[resin.id]["available"], -3)

        shortage = warehouse_report({"report": "shortage"})
        self.assertEqual(len(shortage["purchase"]), 1)
        row = shortage["purchase"][0]
        self.assertEqual(row["material_id"], resin.id)
        self.assertEqual(row["suggested_quantity"], 3)
        self.assertEqual(row["suggested_value"], 60)
        self.assertEqual(shortage["purchase_value"], 60)

        summary = warehouse_report({"report": "summary"})
        self.assertEqual(summary["shortage_count"], 1)
        self.assertEqual(summary["shortage_value"], 60)

    def test_capacity_bottleneck_uses_bom_recipe_and_queue(self):
        fabric = self._material("مخمل", stock=10)
        paint = self._material("پلی‌استر", stock=9, usage=Material.USAGE_PAINT, unit="کیلو")
        recipe = create_recipe(
            {
                "kind": WorkshopRecipe.KIND_PAINT,
                "name": "گردویی",
                "paint_category": WorkshopRecipe.PAINT_CATEGORY_PAINT,
                "stock_unit": "کیلوگرم",
                "materials": [{"material_id": paint.id, "quantity": 4, "unit": "کیلو"}],
            }
        )
        product = Product.objects.create(name="مبل ظرفیت", default_price=1000)
        ProductMaterial.objects.create(product=product, material=fabric, quantity=1)
        apply_product_workset(product, {"paint_recipe_id": recipe.id})
        product.save()

        before = warehouse_report({"report": "capacity", "search": "مبل ظرفیت"})
        row = before["rows"][0]
        self.assertTrue(row["has_bom"])
        self.assertEqual(row["buildable_on_hand"], 2)
        self.assertEqual(row["buildable_after_queue"], 2)
        self.assertEqual(row["bottleneck_material_id"], paint.id)

        self._sale(product, 1)
        after = warehouse_report({"report": "capacity", "search": "مبل ظرفیت"})
        queued = after["rows"][0]
        self.assertEqual(queued["buildable_on_hand"], 2)
        self.assertEqual(queued["buildable_after_queue"], 1)
        self.assertEqual(queued["bottleneck_name"], "پلی‌استر")

    def test_kardex_running_balance_and_opening(self):
        material = self._material("چوب راش", stock=10, usage=Material.USAGE_WOOD, unit="متر")
        InventoryTransaction.objects.create(
            material=material,
            quantity=Decimal("-4"),
            unit_cost=100,
            reason="production_consumption",
            reference="sale:1",
        )
        report = warehouse_report({"report": "movements", "material_id": str(material.id)})
        self.assertEqual([row["balance"] for row in report["rows"]], [10, 6])
        self.assertEqual(report["rows"][1]["out_quantity"], 4)
        self.assertEqual(report["closing_balance"], 6)
        self.assertEqual(report["opening_balance"], 0)

        future = warehouse_report(
            {
                "report": "movements",
                "material_id": str(material.id),
                "date_from": "2099-01-01",
                "date_to": "2099-01-02",
            }
        )
        self.assertEqual(future["rows"], [])
        self.assertEqual(future["opening_balance"], 6)
        self.assertEqual(future["closing_balance"], 6)

    def test_consumption_nets_rollback(self):
        material = self._material("اسفنج", stock=20, usage=Material.USAGE_FOAM, unit="عدد")
        InventoryTransaction.objects.create(
            material=material,
            quantity=Decimal("-10"),
            unit_cost=100,
            reason="production_consumption",
        )
        InventoryTransaction.objects.create(
            material=material,
            quantity=Decimal("3"),
            unit_cost=100,
            reason="production_rollback",
        )
        today = timezone.localdate().isoformat()
        report = warehouse_report(
            {"report": "consumption", "date_from": today, "date_to": today}
        )
        self.assertEqual(len(report["rows"]), 1)
        row = report["rows"][0]
        self.assertEqual(row["material_id"], material.id)
        self.assertEqual(row["consumed_quantity"], 10)
        self.assertEqual(row["returned_quantity"], 3)
        self.assertEqual(row["net_quantity"], 7)
        self.assertEqual(row["net_value"], 700)
        self.assertEqual(report["consumption_value"], 700)

    def test_stocktake_variance_posts_inventory_adjustment_draft(self):
        from backend.models import MaterialStocktake
        from logic.material_stocktake import close_stocktake, create_stocktake, stocktake_sheet, update_stocktake

        cloth = self._material("پارچه شمارش", stock=150, unit_cost=1000)
        extra = self._material("فیلتر شمارش", stock=80, unit_cost=100, unit="عدد")
        oil = self._material("روغن شمارش", stock=200, unit_cost=10, unit="لیتر")
        held = self._material("امانی شمارش", stock=10, unit_cost=50)
        created = create_stocktake({"count_type": "annual", "supervisor_name": "رضا"}, user=None)
        sheet = MaterialStocktake.objects.get(pk=created["id"])
        update_stocktake(sheet, {
            "lines": [
                {"material_id": cloth.id, "physical_qty": "145", "condition": "sound", "root_cause": "shrinkage"},
                {"material_id": extra.id, "physical_qty": "82", "condition": "sound", "root_cause": "entry_error"},
                {"material_id": oil.id, "physical_qty": "200", "condition": "sound", "root_cause": "shrinkage"},
                {"material_id": held.id, "physical_qty": "8", "condition": "consignment", "root_cause": "shrinkage"},
            ],
        })
        InventoryTransaction.objects.create(
            material=cloth,
            quantity=Decimal("10"),
            unit_cost=1000,
            reason="manual_adjustment",
        )
        data = stocktake_sheet(sheet)
        by_id = {row["material_id"]: row for row in data["rows"]}
        self.assertEqual(by_id[cloth.id]["system_qty"], 150)
        self.assertEqual(by_id[cloth.id]["variance_qty"], -5)
        self.assertEqual(by_id[cloth.id]["variance_value"], -5000)
        self.assertEqual(by_id[cloth.id]["status"], "shortage")
        self.assertEqual(by_id[extra.id]["variance_qty"], 2)
        self.assertEqual(by_id[extra.id]["status"], "overage")
        self.assertEqual(by_id[oil.id]["status"], "match")
        self.assertEqual(by_id[oil.id]["root_cause"], "")
        self.assertEqual(by_id[held.id]["condition"], "consignment")
        self.assertEqual(data["metrics"]["accuracy_percent"], 33.3)
        self.assertEqual(data["metrics"]["shrinkage_percent"], 3.1)
        self.assertEqual(data["metrics"]["shortage_value"], 5000)
        self.assertTrue(any("زیر ۹۵٪" in note for note in data["suggestions"]))
        before = InventoryTransaction.objects.count()
        close_stocktake(sheet)
        self.assertEqual(InventoryTransaction.objects.count(), before + 2)
        closed = MaterialStocktake.objects.get(pk=sheet.pk)
        self.assertEqual(closed.status, MaterialStocktake.STATUS_CLOSED)
        self.assertIsNotNone(closed.finished_at)
        self.assertIsNotNone(closed.journal_id)
        self.assertEqual(closed.journal.status, closed.journal.STATUS_DRAFT)
