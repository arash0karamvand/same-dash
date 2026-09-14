"""Tests for product catalog."""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from auth import roles
from backend.models import Material, Product, ProductCategory, ProductMaterial, ProductVariant
from logic.materials import sync_product_materials
from logic.products import create_product, product_to_dict
from testing.role_helpers import ensure_legacy_test_roles, ensure_test_role

User = get_user_model()


class ProductCatalogTests(TestCase):
    def setUp(self):
        ensure_legacy_test_roles()
        self.client = Client()
        self.user = User.objects.create_user(username="mgr", password="testpass123")
        roles.assign_role(self.user, roles.SALES_MANAGER)
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
        self.assertEqual(payload["material_cost_total"], 22)

        created = create_product(
            {"name": "کمربند", "materials": [{"material_id": material.id, "quantity": 1}]},
            allow_sales_price=False,
            allow_materials=True,
        )
        data = product_to_dict(created, audience="factory")
        self.assertEqual(len(data["materials"]), 1)


class ProductStockSaleTests(TestCase):
    def setUp(self):
        from backend.models import Customer, InventoryTransaction
        from logic.sales import record_sale

        self.InventoryTransaction = InventoryTransaction
        self.record_sale = record_sale
        self.customer = Customer.objects.create(full_name="خریدار", phone="09120000001")
        self.product = Product.objects.create(name="کفش ورزشی", default_price=100000)
        self.variant = ProductVariant.objects.create(
            product=self.product, color_name="مشکی", color_hex="#111111"
        )
        InventoryTransaction.objects.create(
            variant=self.variant,
            quantity=10,
            reason="catalog_stock_adjustment",
            reference=f"product:{self.product.pk}",
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

    def test_sale_reduces_variant_stock(self):
        sale = self._sell(3)
        self.assertEqual(self.variant.stock, Decimal("7"))
        self.assertEqual(sale.line_items.get().quantity, Decimal("3"))

    def test_insufficient_stock_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self._sell(11)
        self.assertIn("موجودی", str(ctx.exception))
        self.assertEqual(self.variant.stock, Decimal("10"))

    def test_second_sale_sees_remaining_stock(self):
        self._sell(6)
        with self.assertRaises(ValueError):
            self._sell(6)
        self.assertEqual(self.variant.stock, Decimal("4"))

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
        self.assertEqual(self.variant.stock, Decimal("6"))
        delete_sale(sale)
        self.assertEqual(self.variant.stock, Decimal("10"))

    def test_update_line_items_restores_and_rededucts(self):
        from logic.sales import update_sale

        sale = self._sell(4)
        self.assertEqual(self.variant.stock, Decimal("6"))
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
        self.assertEqual(self.variant.stock, Decimal("8"))

