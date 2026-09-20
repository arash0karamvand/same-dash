"""Tests for frame catalog and material requirements."""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from auth import roles
from backend.models import (
    Customer,
    FrameServiceComponent,
    Material,
    Product,
    ProductVariant,
    Sale,
    SaleLineItem,
)
from logic.frame_materials import compute_frame_line_requirements, preview_frame_requirements
from logic.frames import create_frame, frame_to_dict
from logic.materials import compute_factory_order_material_requirements
from testing.role_helpers import ensure_legacy_test_roles

User = get_user_model()


class FrameCatalogTests(TestCase):
    def setUp(self):
        ensure_legacy_test_roles()
        self.client = Client()
        self.user = User.objects.create_user(username="frame_mgr", password="testpass123")
        roles.assign_role(self.user, roles.ADMIN)
        self.client.login(username="frame_mgr", password="testpass123")

        self.wood_material = Material.objects.create(
            name="چوب راش",
            unit="متر",
            unit_cost=100,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        self.fabric_material = Material.objects.create(
            name="پارچه پشت",
            unit="متر",
            unit_cost=50,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        self.wood_back_material = Material.objects.create(
            name="چوب پشت",
            unit="متر",
            unit_cost=80,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )

    def _sample_payload(self):
        return {
            "name": "کلاف لونا",
            "design_style": "modern",
            "wood_type": "ash_georgian_g1",
            "models": [
                {
                    "name": "مدل A",
                    "wood_requirements": [
                        {
                            "label": "قاب اصلی",
                            "quantity": 2.5,
                            "unit": "متر",
                            "material_id": self.wood_material.id,
                        }
                    ],
                }
            ],
            "service_template": {
                "name": "سرویس ۸ نفره",
                "default_seat_count": 8,
                "components": [
                    {
                        "component_type": "three_seater",
                        "default_quantity": 1,
                        "material_rules": [
                            {
                                "rule_key": "back_fabric",
                                "material_id": self.fabric_material.id,
                                "quantity": 3,
                                "unit": "متر",
                            },
                            {
                                "rule_key": "back_wood",
                                "material_id": self.wood_back_material.id,
                                "quantity": 1.5,
                                "unit": "متر",
                            },
                        ],
                    },
                    {"component_type": "armchair", "default_quantity": 2, "material_rules": []},
                    {"component_type": "side_table", "default_quantity": 2, "material_rules": []},
                    {"component_type": "coffee_table", "default_quantity": 1, "material_rules": []},
                ],
            },
        }

    def test_create_frame_with_nested_data(self):
        resp = self.client.post(
            "/api/frames/",
            data=json.dumps(self._sample_payload()),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["name"], "کلاف لونا")
        self.assertEqual(len(data["models"]), 1)
        self.assertEqual(len(data["models"][0]["wood_requirements"]), 1)
        self.assertEqual(len(data["service_template"]["components"]), 4)

    def test_frame_requirements_fabric_vs_wood_back(self):
        frame = create_frame(self._sample_payload())
        frame_model = frame.models.first()
        template = frame.service_template
        three_seater = template.components.get(component_type=FrameServiceComponent.TYPE_THREE_SEATER)

        fabric_reqs = preview_frame_requirements(
            frame,
            frame_model_id=frame_model.id,
            frame_config={
                "seat_count": 8,
                "components": [{"type": "three_seater", "qty": 1, "back_type": "fabric"}],
            },
            quantity=1,
        )
        wood_reqs = preview_frame_requirements(
            frame,
            frame_model_id=frame_model.id,
            frame_config={
                "seat_count": 8,
                "components": [{"type": "three_seater", "qty": 1, "back_type": "wood"}],
            },
            quantity=1,
        )
        fabric_qty = sum(r["required_quantity"] for r in fabric_reqs if r["material_id"] == self.fabric_material.id)
        wood_back_qty = sum(r["required_quantity"] for r in wood_reqs if r["material_id"] == self.wood_back_material.id)
        wood_frame_qty = sum(r["required_quantity"] for r in wood_reqs if r["material_id"] == self.wood_material.id)
        self.assertEqual(fabric_qty, 3.0)
        self.assertEqual(wood_back_qty, 1.5)
        self.assertEqual(wood_frame_qty, 2.5)

    def test_factory_order_includes_frame_materials(self):
        frame = create_frame(self._sample_payload())
        frame_model = frame.models.first()
        product = Product.objects.create(name="مبل لونا", default_price=1000000)
        ProductVariant.objects.create(product=product, color_name="کرم", color_hex="#eee", price=1000000)
        product.frame = frame
        product.save()

        customer = Customer.objects.create(full_name="تست", phone="09120000000")
        sale = Sale.objects.create(
            customer=customer,
            amount=1000000,
            final_amount=1000000,
            paid_amount=1000000,
        )
        SaleLineItem.objects.create(
            sale=sale,
            product=product,
            frame=frame,
            frame_model=frame_model,
            frame_config={
                "seat_count": 8,
                "components": [{"type": "three_seater", "qty": 1, "back_type": "wood"}],
            },
            product_name=product.name,
            quantity=1,
            unit_price=1000000,
            line_total=1000000,
        )

        requirements = compute_factory_order_material_requirements(sale)
        material_ids = {item["material_id"] for item in requirements}
        self.assertIn(self.wood_material.id, material_ids)
        self.assertIn(self.wood_back_material.id, material_ids)

    def test_sale_line_stores_frame_config(self):
        frame = create_frame(self._sample_payload())
        frame_model = frame.models.first()
        product = Product.objects.create(name="مبل", default_price=500000, frame=frame)
        ProductVariant.objects.create(product=product, color_name="مشکی", color_hex="#111", price=500000)

        from logic.products import resolve_line_item_from_catalog

        resolved = resolve_line_item_from_catalog(
            {
                "product_id": product.id,
                "quantity": 1,
                "frame_model_id": frame_model.id,
                "frame_config": {
                    "seat_count": 8,
                    "components": [{"type": "three_seater", "qty": 1, "back_type": "fabric"}],
                },
            }
        )
        self.assertEqual(resolved["frame"].id, frame.id)
        self.assertEqual(resolved["frame_model"].id, frame_model.id)
        self.assertEqual(resolved["frame_config"]["seat_count"], 8)

    def test_frame_to_dict_serialization(self):
        frame = create_frame(self._sample_payload())
        data = frame_to_dict(frame)
        self.assertEqual(data["design_style_display"], "مدرن")
        self.assertEqual(data["wood_type_display"], "راش گرجستان درجه ۱")
