"""Tests for product catalog."""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from auth import roles
from backend.models import Material, Product, ProductCategory, ProductMaterial, ProductVariant
from logic.materials import sync_product_materials
from logic.products import create_product, product_to_dict, update_product
from testing.role_helpers import ensure_legacy_test_roles, ensure_test_role
from testing.sale_test_mixin import OfficeLedgerTestMixin

User = get_user_model()


class ProductCatalogTests(TestCase):
    def setUp(self):
        ensure_legacy_test_roles()
        self.client = Client()
        self.user = User.objects.create_user(username="mgr", password="testpass123")
        roles.assign_role(self.user, roles.CATALOG_OFFICE)
        self.client.login(username="mgr", password="testpass123")

    def test_create_category_and_product_with_variants(self):
        cat_resp = self.client.post(
            "/api/products/categories/",
            data=json.dumps({"name": "کفش", "icon": "👟", "color": "#3b82f6"}),
            content_type="application/json",
        )
        self.assertEqual(cat_resp.status_code, 201)
        cat_id = cat_resp.json()["data"]["id"]

        prod_resp = self.client.post(
            "/api/products/",
            data=json.dumps({
                "name": "کفش ورزشی",
                "category_id": cat_id,
                "default_price": 500000,
                "variants": [
                    {"color_name": "مشکی", "color_hex": "#1f2937", "price": 500000},
                    {"color_name": "سفید", "color_hex": "#f8fafc", "price": 520000},
                ],
            }),
            content_type="application/json",
        )
        self.assertEqual(prod_resp.status_code, 201)
        data = prod_resp.json()["data"]
        self.assertEqual(len(data["variants"]), 2)
        self.assertEqual(ProductVariant.objects.count(), 2)

    def test_list_products_by_category(self):
        cat = ProductCategory.objects.create(name="لباس")
        product = Product.objects.create(name="پیراهن", category=cat, default_price=300000)
        ProductVariant.objects.create(product=product, color_name="آبی", color_hex="#3b82f6", price=300000)

        resp = self.client.get(f"/api/products/?category_id={cat.id}")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "پیراهن")

    def test_serialize_product_with_materials_audience(self):
        product = Product.objects.create(name="کت", default_price=1000)
        data = product_to_dict(product, audience="full")
        self.assertEqual(data["materials"], [])
        self.assertEqual(data["material_cost_total"], 0)

        material = Material.objects.create(
            name="پارچه",
            unit_cost=10,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        ProductMaterial.objects.create(product=product, material=material, quantity=2)
        data = product_to_dict(product, audience="full")
        self.assertEqual(len(data["materials"]), 1)
        self.assertEqual(data["materials"][0]["material_id"], material.id)
        self.assertEqual(data["materials"][0]["quantity"], 2.0)
        self.assertEqual(data["material_cost_total"], 20)

    def test_admin_cost_pricing_supports_percent_and_fixed_profit(self):
        product = Product.objects.create(name="محصول قیمت‌گذاری", default_price=0)
        material = Material.objects.create(
            name="متریال قیمت‌گذاری",
            unit_cost=10,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        ProductMaterial.objects.create(product=product, material=material, quantity=2)

        update_product(
            product,
            {
                "profit_mode": "percent",
                "target_margin_percent": 25,
                "cost_override": None,
            },
            allow_sales_price=True,
            allow_cost_pricing=True,
        )
        self.assertEqual(product.default_price, Decimal("25"))

        update_product(
            product,
            {
                "profit_mode": "fixed",
                "target_profit_amount": 7,
                "cost_override": 30,
            },
            allow_sales_price=True,
            allow_cost_pricing=True,
        )
        self.assertEqual(product.default_price, Decimal("37"))
        data = product_to_dict(product, audience="full")
        self.assertEqual(data["calculated_cost"], 20)
        self.assertEqual(data["effective_cost"], 30)
        self.assertEqual(data["profit_amount"], 7)
        self.assertEqual(data["suggested_sales_price"], 37)

    def test_non_admin_cannot_submit_cost_pricing(self):
        product = Product.objects.create(name="محصول محدود", default_price=0)
        with self.assertRaisesRegex(ValueError, "فقط در بخش اداری"):
            update_product(
                product,
                {"profit_mode": "fixed", "target_profit_amount": 10},
                allow_sales_price=True,
                allow_cost_pricing=False,
            )
        product.suite_config = [{"piece_kind": "sofa_3", "arm_style": "two", "quantity": 1}]
        product.save(update_fields=["suite_config"])
        with self.assertRaisesRegex(ValueError, "فقط توسط اداری"):
            update_product(
                product,
                {"default_price": 1000},
                allow_sales_price=True,
                allow_cost_pricing=False,
            )

    def test_sync_product_materials_uses_composite_key(self):
        product = Product.objects.create(name="شلوار", default_price=2000)
        first = Material.objects.create(
            name="نخ",
            unit_cost=5,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        second = Material.objects.create(
            name="دکمه",
            unit_cost=2,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        sync_product_materials(
            product,
            [{"id": "stale-row-id", "material_id": first.id, "quantity": 3}],
        )
        self.assertEqual(ProductMaterial.objects.filter(product=product).count(), 1)

        sync_product_materials(
            product,
            [{"material_id": second.id, "quantity": 4}],
        )
        rows = list(ProductMaterial.objects.filter(product=product))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].material_id, second.id)
        self.assertEqual(rows[0].quantity, Decimal("4"))

    def test_factory_user_can_create_product_with_materials(self):
        ensure_test_role(
            "factory_catalog",
            [
                "view_factory_products",
                "manage_factory_products",
                "view_materials",
                "manage_materials",
            ],
            label="کاتالوگ کارخانه",
        )
        factory_user = User.objects.create_user(username="factory", password="testpass123")
        roles.assign_role(factory_user, "factory_catalog")
        client = Client()
        client.login(username="factory", password="testpass123")

        material = Material.objects.create(
            name="چرم",
            unit_cost=15,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        resp = client.post(
            "/api/products/",
            data=json.dumps({
                "name": "کیف",
                "materials": [{"material_id": material.id, "quantity": 1.5}],
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        payload = resp.json()["data"]
        self.assertEqual(payload["name"], "کیف")
        self.assertEqual(len(payload["materials"]), 1)
        self.assertEqual(payload["materials"][0]["material_id"], material.id)
        self.assertNotIn("material_cost_total", payload)
        self.assertNotIn("line_cost", payload["materials"][0])
        self.assertNotIn("unit_cost", payload["materials"][0]["material"])

        created = create_product(
            {"name": "کمربند", "materials": [{"material_id": material.id, "quantity": 1}]},
            allow_sales_price=False,
            allow_materials=True,
        )
        data = product_to_dict(created, audience="factory")
        self.assertEqual(len(data["materials"]), 1)

    def test_office_cannot_create_factory_suite_payload(self):
        from logic.furniture_worksets import create_workset
        from backend.models import Frame

        workset = create_workset({
            "name": "تست مجوز",
            "pieces": [{"piece_kind": Frame.PIECE_POUF, "arm_style": Frame.ARM_NONE, "quantity": 1}],
        })
        resp = self.client.post(
            "/api/products/",
            data=json.dumps({
                "name": "نباید ثبت شود",
                "furniture_workset_id": workset.id,
                "suite_config": [{
                    "piece_kind": Frame.PIECE_POUF,
                    "arm_style": Frame.ARM_NONE,
                    "quantity": 1,
                    "unit_price": 1000,
                }],
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_office_updates_suite_prices_without_changing_factory_shape(self):
        from logic.furniture_worksets import create_workset
        from backend.models import Frame

        ensure_test_role(
            "factory_suite",
            ["view_factory_products", "manage_factory_products", "view_materials", "manage_materials"],
            label="کارخانه سرویس",
        )
        workset = create_workset({
            "name": "قیمت اداری",
            "pieces": [{"piece_kind": Frame.PIECE_POUF, "arm_style": Frame.ARM_NONE, "quantity": 1}],
        })
        product = create_product(
            {
                "name": "سرویس قیمت",
                "furniture_workset_id": workset.id,
                "suite_config": [{
                    "piece_kind": Frame.PIECE_POUF,
                    "arm_style": Frame.ARM_NONE,
                    "quantity": 1,
                    "needs_paint": False,
                    "unit_price": 1_000_000,
                }],
            },
            allow_sales_price=True,
            allow_materials=True,
        )
        update_product(
            product,
            {
                "suite_config": [{
                    "piece_kind": Frame.PIECE_POUF,
                    "arm_style": Frame.ARM_NONE,
                    "quantity": 1,
                    "unit_price": 2_500_000,
                }],
            },
            allow_sales_price=True,
            allow_materials=False,
        )
        product.refresh_from_db()
        self.assertEqual(int(product.default_price), 2_500_000)
        piece = product.suite_config[0]
        self.assertEqual(piece["unit_price"], "2500000")
        self.assertFalse(piece["needs_paint"])


class ProductStockSaleTests(OfficeLedgerTestMixin, TestCase):
    def setUp(self):
        self.seed_office_chart()
        from backend.models import Customer, InventoryTransaction
        from logic.sales import record_sale
        from logic.stock_locations import LOCATION_WAREHOUSE, default_warehouse, location_transaction_kwargs, parse_location

        self.InventoryTransaction = InventoryTransaction
        self.record_sale = record_sale
        self.customer = Customer.objects.create(full_name="خریدار", phone="09120000001")
        self.product = Product.objects.create(name="کفش ورزشی", default_price=100000)
        self.variant = ProductVariant.objects.create(
            product=self.product, color_name="مشکی", color_hex="#111111"
        )
        self.warehouse = default_warehouse()
        self.location = parse_location(
            {"kind": LOCATION_WAREHOUSE, "warehouse_id": self.warehouse.id}, required=True
        )
        InventoryTransaction.objects.create(
            variant=self.variant,
            quantity=10,
            reason="catalog_stock_adjustment",
            reference=f"product:{self.product.pk}",
            **location_transaction_kwargs(self.location),
        )

    def _sell(self, quantity, **kwargs):
        return self.record_sale(
            self.customer,
            0,
            line_items=[
                {
                    "product_id": self.product.id,
                    "variant_id": self.variant.id,
                    "quantity": quantity,
                }
            ],
            **kwargs,
        )

    def test_sale_creation_does_not_reduce_variant_stock(self):
        sale = self._sell(3)
        self.assertEqual(self.variant.stock, Decimal("10"))
        self.assertEqual(sale.line_items.get().quantity, Decimal("3"))

    def test_sale_shortage_is_deferred_to_fulfillment_planning(self):
        self._sell(11)
        self.assertEqual(self.variant.stock, Decimal("10"))

    def test_multiple_sales_do_not_compete_before_planning(self):
        self._sell(6)
        self._sell(6)
        self.assertEqual(self.variant.stock, Decimal("10"))

    def test_untracked_product_can_still_be_sold(self):
        made_to_order = Product.objects.create(name="سفارشی", default_price=200000)
        variant = ProductVariant.objects.create(product=made_to_order, color_name="سفید")
        self.record_sale(
            self.customer,
            0,
            line_items=[{"product_id": made_to_order.id, "variant_id": variant.id, "quantity": 2}],
        )
        self.assertEqual(variant.stock, Decimal("0"))

    def test_delete_sale_restores_stock(self):
        from logic.sales import delete_sale

        sale = self._sell(4)
        self.assertEqual(self.variant.stock, Decimal("10"))
        delete_sale(sale)
        self.assertEqual(self.variant.stock, Decimal("10"))

    def test_update_line_items_has_no_stock_side_effect(self):
        from logic.sales import update_sale

        sale = self._sell(4)
        self.assertEqual(self.variant.stock, Decimal("10"))
        update_sale(
            sale,
            paid_amount=200000,
            line_items=[
                {
                    "product_id": self.product.id,
                    "variant_id": self.variant.id,
                    "quantity": 2,
                }
            ],
        )
        self.assertEqual(self.variant.stock, Decimal("10"))

    def test_sale_source_selection_does_not_deduct_before_planning(self):
        from backend.models import Branch, InventoryTransaction
        from logic.stock_locations import LOCATION_BRANCH, location_transaction_kwargs, parse_location, stock_for_variant_at

        branch, _ = Branch.objects.get_or_create(
            code="branch_1",
            defaults={"label": "کمرد", "sort_order": 0, "is_active": True},
        )
        loc = parse_location({"kind": LOCATION_BRANCH, "branch": branch.code}, required=True)
        InventoryTransaction.objects.create(
            variant=self.variant,
            quantity=4,
            reason="catalog_stock_adjustment",
            **location_transaction_kwargs(loc),
        )
        self._sell(
            3,
            stock_source={"kind": LOCATION_BRANCH, "branch": branch.code},
        )
        self.assertEqual(stock_for_variant_at(self.variant, loc), Decimal("4"))
        self.assertEqual(stock_for_variant_at(self.variant, self.location), Decimal("10"))

    def test_transfer_moves_stock_between_locations(self):
        from backend.models import Branch
        from logic.stock_locations import LOCATION_BRANCH, parse_location, stock_for_variant_at, transfer_variant_stock

        branch, _ = Branch.objects.get_or_create(
            code="branch_1",
            defaults={"label": "کمرد", "sort_order": 0, "is_active": True},
        )
        dest = parse_location({"kind": LOCATION_BRANCH, "branch": branch.code}, required=True)
        transfer_variant_stock(self.variant, self.location, dest, 2)
        self.assertEqual(stock_for_variant_at(self.variant, self.location), Decimal("8"))
        self.assertEqual(stock_for_variant_at(self.variant, dest), Decimal("2"))

    def test_catalog_rejects_negative_location_stock(self):
        from logic.products import update_product

        with self.assertRaises(ValueError):
            update_product(
                self.product,
                {
                    "variants": [
                        {
                            "id": self.variant.id,
                            "color_name": self.variant.color_name,
                            "color_hex": self.variant.color_hex,
                            "stock_by_location": [
                                {
                                    "kind": "warehouse",
                                    "warehouse_id": self.warehouse.id,
                                    "quantity": -1,
                                }
                            ],
                        }
                    ]
                },
            )


class ManualStockLockTests(OfficeLedgerTestMixin, TestCase):
    def setUp(self):
        self.seed_office_chart()
        from backend.models import Customer, InventoryTransaction
        from logic.inventory_settings import set_manual_stock_locked
        from logic.stock_locations import LOCATION_WAREHOUSE, default_warehouse, location_transaction_kwargs, parse_location

        ensure_legacy_test_roles()
        set_manual_stock_locked(False)
        self.addCleanup(lambda: set_manual_stock_locked(False))

        self.client = Client()
        self.user = User.objects.create_user(username="catalog", password="testpass123")
        roles.assign_role(self.user, roles.CATALOG_OFFICE)
        self.client.login(username="catalog", password="testpass123")

        self.product = Product.objects.create(name="کفش قفل", default_price=100000)
        self.variant = ProductVariant.objects.create(
            product=self.product, color_name="مشکی", color_hex="#111111"
        )
        self.warehouse = default_warehouse()
        self.location = parse_location(
            {"kind": LOCATION_WAREHOUSE, "warehouse_id": self.warehouse.id}, required=True
        )
        InventoryTransaction.objects.create(
            variant=self.variant,
            quantity=10,
            reason="catalog_stock_adjustment",
            reference=f"product:{self.product.pk}",
            **location_transaction_kwargs(self.location),
        )
        self.customer = Customer.objects.create(full_name="خریدار قفل", phone="09120000099")

    def test_locked_catalog_stock_adjustment_is_rejected(self):
        from logic.inventory_settings import MANUAL_STOCK_LOCKED_MESSAGE, set_manual_stock_locked
        from logic.products import update_product

        set_manual_stock_locked(True)
        with self.assertRaises(ValueError) as ctx:
            update_product(
                self.product,
                {
                    "variants": [
                        {
                            "id": self.variant.id,
                            "color_name": self.variant.color_name,
                            "color_hex": self.variant.color_hex,
                            "stock_by_location": [
                                {
                                    "kind": "warehouse",
                                    "warehouse_id": self.warehouse.id,
                                    "quantity": 20,
                                }
                            ],
                        }
                    ]
                },
            )
        self.assertIn(MANUAL_STOCK_LOCKED_MESSAGE, str(ctx.exception))
        self.assertEqual(self.variant.stock, Decimal("10"))

    def test_locked_same_stock_save_is_allowed(self):
        from logic.inventory_settings import set_manual_stock_locked
        from logic.products import update_product

        set_manual_stock_locked(True)
        update_product(
            self.product,
            {
                "name": "کفش قفل ویرایش",
                "variants": [
                    {
                        "id": self.variant.id,
                        "color_name": self.variant.color_name,
                        "color_hex": self.variant.color_hex,
                        "stock_by_location": [
                            {
                                "kind": "warehouse",
                                "warehouse_id": self.warehouse.id,
                                "quantity": 10,
                            }
                        ],
                    }
                ],
            },
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "کفش قفل ویرایش")
        self.assertEqual(self.variant.stock, Decimal("10"))

    def test_sale_still_records_without_stock_deduction_when_manual_stock_locked(self):
        from logic.inventory_settings import set_manual_stock_locked
        from logic.sales import record_sale

        set_manual_stock_locked(True)
        record_sale(
            self.customer,
            0,
            line_items=[
                {
                    "product_id": self.product.id,
                    "variant_id": self.variant.id,
                    "quantity": 3,
                }
            ],
        )
        self.assertEqual(self.variant.stock, Decimal("10"))

    def test_transfer_rejected_when_locked(self):
        from backend.models import Branch
        from logic.inventory_settings import MANUAL_STOCK_LOCKED_MESSAGE, set_manual_stock_locked

        set_manual_stock_locked(True)
        branch, _ = Branch.objects.get_or_create(
            code="branch_1",
            defaults={"label": "کمرد", "sort_order": 0, "is_active": True},
        )
        resp = self.client.post(
            "/api/products/stock-transfer/",
            data=json.dumps({
                "variant_id": self.variant.id,
                "source": {"kind": "warehouse", "warehouse_id": self.warehouse.id},
                "destination": {"kind": "branch", "branch": branch.code},
                "quantity": 2,
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], MANUAL_STOCK_LOCKED_MESSAGE)
        self.assertEqual(self.variant.stock, Decimal("10"))

    def test_unauthorized_user_cannot_toggle_lock(self):
        ensure_test_role(
            "catalog_only",
            ["view_products", "manage_products"],
            label="فقط کاتالوگ",
        )
        clerk = User.objects.create_user(username="clerk", password="testpass123")
        roles.assign_role(clerk, "catalog_only")
        client = Client()
        client.login(username="clerk", password="testpass123")
        resp = client.put(
            "/api/config/inventory-settings/",
            data=json.dumps({"manual_stock_locked": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        from logic.inventory_settings import is_manual_stock_locked
        self.assertFalse(is_manual_stock_locked())

    def test_managers_portal_user_can_toggle_lock(self):
        from logic.inventory_settings import is_manual_stock_locked

        admin = User.objects.create_user(username="boss", password="testpass123", is_superuser=True)
        client = Client()
        client.login(username="boss", password="testpass123")
        resp = client.put(
            "/api/config/inventory-settings/",
            data=json.dumps({"manual_stock_locked": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()["data"]["manual_stock_locked"])
        self.assertTrue(is_manual_stock_locked())

        cfg = client.get("/api/config/")
        self.assertEqual(cfg.status_code, 200)
        self.assertTrue(cfg.json()["data"]["inventory_settings"]["manual_stock_locked"])


