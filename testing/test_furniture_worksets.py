"""تست دست با تعداد قطعات و محصول چندرنگه."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.models import Branch, Customer, Frame, Product, Sale
from logic.furniture_worksets import (
    create_product_from_workset,
    create_workset,
    validate_piece_arm,
)
from logic.sales import record_sale
from logic.workshop_recipes import create_recipe, fabric_named_ids


class FurnitureWorksetTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="suite_user", password="secret123")
        Branch.objects.get_or_create(code="branch_1", defaults={"label": "کمرد", "is_active": True})
        self.customer = Customer.objects.create(full_name="خریدار دست", phone="09121112233")
        self.fabric_cream = create_recipe({
            "kind": "fabric",
            "name": "مخمل کرم",
            **fabric_named_ids(color="کرم"),
        })
        self.fabric_gray = create_recipe({
            "kind": "fabric",
            "name": "مخمل طوسی",
            **fabric_named_ids(brand="منسوجات آریا", color="دودی"),
        })
        self.paint_walnut = create_recipe(
            {"kind": "paint", "name": "گردویی", "paint_category": "paint", "stock_unit": "لیتر"}
        )
        self.luna = create_workset({
            "name": "لونا",
            "seat_count": 8,
            "pieces": [
                {"piece_kind": Frame.PIECE_SOFA_3, "arm_style": Frame.ARM_TWO, "quantity": 1},
                {"piece_kind": Frame.PIECE_ARMCHAIR, "arm_style": Frame.ARM_NONE, "quantity": 2},
            ],
        })
        self.nova = create_workset({
            "name": "نوا",
            "seat_count": 6,
            "pieces": [
                {"piece_kind": Frame.PIECE_POUF, "arm_style": Frame.ARM_NONE, "quantity": 1},
            ],
        })

    def test_invalid_arm_combination_rejected(self):
        with self.assertRaises(ValueError):
            validate_piece_arm(Frame.PIECE_SOFA_3, Frame.ARM_NONE)
        with self.assertRaises(ValueError):
            create_workset({
                "name": "غلط",
                "pieces": [
                    {"piece_kind": Frame.PIECE_CHAISE, "arm_style": Frame.ARM_TWO, "quantity": 1},
                ],
            })

    def test_workset_keeps_piece_quantities_and_product_finishes(self):
        self.assertEqual(self.luna.pieces.count(), 2)
        sofa = self.luna.pieces.get(piece_kind=Frame.PIECE_SOFA_3)
        chair = self.luna.pieces.get(piece_kind=Frame.PIECE_ARMCHAIR)
        self.assertEqual(sofa.quantity, 1)
        self.assertEqual(chair.arm_style, Frame.ARM_NONE)
        self.assertEqual(chair.quantity, 2)

        product = create_product_from_workset(self.luna, {
            "name": "لونا کرم",
            "pieces": [
                {
                    "piece_kind": Frame.PIECE_SOFA_3,
                    "arm_style": Frame.ARM_TWO,
                    "fabric_recipe_id": self.fabric_cream.id,
                    "needs_paint": False,
                    "unit_price": 12000000,
                },
                {
                    "piece_kind": Frame.PIECE_ARMCHAIR,
                    "arm_style": Frame.ARM_NONE,
                    "fabric_recipe_id": self.fabric_gray.id,
                    "paint_recipe_id": self.paint_walnut.id,
                    "needs_paint": True,
                    "unit_price": 5000000,
                },
            ],
        })
        self.assertEqual(product.furniture_workset_id, self.luna.id)
        self.assertEqual(len(product.suite_config), 2)
        sofa_cfg = next(row for row in product.suite_config if row["piece_kind"] == Frame.PIECE_SOFA_3)
        chair_cfg = next(row for row in product.suite_config if row["piece_kind"] == Frame.PIECE_ARMCHAIR)
        self.assertFalse(sofa_cfg["needs_paint"])
        self.assertEqual(sofa_cfg["fabric"]["name"], "مخمل کرم")
        self.assertEqual(chair_cfg["fabric"]["name"], "مخمل طوسی")
        self.assertEqual(chair_cfg["paint"]["name"], "گردویی")
        self.assertEqual(int(product.default_price), 12000000 + 5000000 * 2)
        self.assertEqual(Product.objects.filter(furniture_workset=self.luna).count(), 1)

    def test_sale_sums_suite_products_from_two_worksets(self):
        luna = create_product_from_workset(self.luna, {
            "pieces": [
                {
                    "piece_kind": Frame.PIECE_SOFA_3,
                    "arm_style": Frame.ARM_TWO,
                    "fabric_recipe_id": self.fabric_cream.id,
                    "needs_paint": False,
                    "unit_price": 12000000,
                },
                {
                    "piece_kind": Frame.PIECE_ARMCHAIR,
                    "arm_style": Frame.ARM_NONE,
                    "fabric_recipe_id": self.fabric_cream.id,
                    "needs_paint": False,
                    "unit_price": 5000000,
                },
            ],
        })
        nova = create_product_from_workset(self.nova, {
            "pieces": [
                {
                    "piece_kind": Frame.PIECE_POUF,
                    "arm_style": Frame.ARM_NONE,
                    "fabric_recipe_id": self.fabric_gray.id,
                    "needs_paint": False,
                    "unit_price": 2000000,
                },
            ],
        })
        sale = record_sale(
            self.customer,
            0,
            line_items=[
                {"product_id": luna.id, "quantity": 1, "furniture_workset_id": self.luna.id},
                {"product_id": nova.id, "quantity": 2, "furniture_workset_id": self.nova.id},
            ],
            branch="branch_1",
            seat_count=8,
        )
        self.assertEqual(sale.receive_kind, Sale.RECEIVE_KIND_CUSTOMER)
        self.assertEqual(int(sale.amount), 22000000 + 4000000)
        self.assertEqual(sale.seat_count, 8)
        kinds = set(sale.line_items.values_list("furniture_workset_id", flat=True))
        self.assertEqual(kinds, {self.luna.id, self.nova.id})
        self.assertEqual(sale.line_items.count(), 2)
        luna_line = sale.line_items.get(product=luna)
        self.assertEqual(len(luna_line.workset_config.get("pieces") or []), 2)
