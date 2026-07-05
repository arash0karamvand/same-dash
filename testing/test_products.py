"""Tests for product catalog."""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from auth import roles
from backend.models import Product, ProductCategory, ProductVariant
from testing.role_helpers import ensure_legacy_test_roles

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
