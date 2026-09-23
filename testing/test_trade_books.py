from decimal import Decimal

from django.test import TestCase

from backend.models import JournalEntry, Material
from testing.accounting_helpers import seed_accounts
from logic.trade_books import (
    kardex,
    post_purchase,
    post_purchase_return,
    post_sale,
    take_purchase_discount,
)


class TradeCycleTest(TestCase):
    def setUp(self):
        seed_accounts()
        self.material = Material.objects.create(
            name="پارچه", unit="متر", unit_cost=0, reorder_point=Decimal("20"),
        )

    def test_perpetual_purchase_sale_return_and_kardex(self):
        purchased = post_purchase({
            "material_id": self.material.id,
            "quantity": 10,
            "unit_price": 1000,
            "trade_discount": 1000,
            "freight": 500,
            "insurance": 200,
            "vat_rate": 10,
            "settlement": "credit",
            "invoice_number": "B-1",
            "warehouse_receipt": "W-1",
        })
        self.assertEqual(purchased["inventory_amount"], 9700)
        self.assertEqual(purchased["vat_amount"], 900)
        self.assertIn("نقطه سفارش", purchased["warning"])
        self.material.refresh_from_db()
        self.assertEqual(self.material.stock, Decimal("10"))
        self.assertEqual(self.material.unit_cost, Decimal("970"))

        sold = post_sale({
            "material_id": self.material.id,
            "quantity": 4,
            "unit_price": 2000,
            "vat_rate": 10,
            "settlement": "credit",
            "invoice_number": "S-1",
        })
        self.assertEqual(sold["cogs_amount"], 3880)
        self.assertEqual(sold["goods_net"], 8000)
        self.assertEqual(sold["vat_amount"], 800)
        self.material.refresh_from_db()
        self.assertEqual(self.material.stock, Decimal("6"))

        returned = post_purchase_return({
            "document_id": purchased["id"],
            "quantity": 2,
            "warehouse_receipt": "W-2",
        })
        self.assertEqual(returned["inventory_amount"], 1940)
        self.assertEqual(returned["vat_amount"], 180)
        self.material.refresh_from_db()
        self.assertEqual(self.material.stock, Decimal("4"))

        card = kardex(self.material.id)
        self.assertEqual(Decimal(card["stock"]), Decimal("4"))
        self.assertEqual(card["lines"][-1]["balance_value"], 3880)
        self.assertTrue(JournalEntry.objects.filter(document_code=purchased["document_code"]).exists())

    def test_source_document_and_gross_cash_discount(self):
        with self.assertRaises(ValueError):
            post_purchase({
                "material_id": self.material.id,
                "quantity": 1,
                "unit_price": 1000,
                "warehouse_receipt": "W-9",
            })
        purchased = post_purchase({
            "material_id": self.material.id,
            "quantity": 1,
            "unit_price": 1000,
            "vat_rate": 10,
            "settlement": "credit",
            "invoice_number": "B-2",
            "warehouse_receipt": "W-3",
        })
        discounted = take_purchase_discount({"document_id": purchased["id"], "amount": 100})
        self.assertEqual(discounted["cash_discount"], 100)
        self.assertEqual(discounted["vat_amount"], 10)
        self.material.refresh_from_db()
        self.assertEqual(self.material.unit_cost, Decimal("900"))
        card = kardex(self.material.id)
        self.assertEqual(card["balance_value"], 900)
