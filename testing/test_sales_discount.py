"""Tests for sale discount types and wallet."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.models import Customer, Sale
from logic.sales import delete_sale, record_sale, resolve_discount_amount
from logic.wallet import adjust_wallet

User = get_user_model()


class SaleDiscountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="seller", password="testpass123")
        self.customer = Customer.objects.create(full_name="Ali", phone="09121111111")

    def test_percent_discount(self):
        discount = resolve_discount_amount(Decimal("1000000"), "percent", Decimal("10"))
        self.assertEqual(discount, Decimal("100000"))

    def test_amount_discount(self):
        discount = resolve_discount_amount(Decimal("1000000"), "amount", Decimal("50000"))
        self.assertEqual(discount, Decimal("50000"))

    def test_wallet_discount(self):
        adjust_wallet(self.customer, Decimal("200000"), user=self.user)
        discount = resolve_discount_amount(
            Decimal("1000000"), "wallet", Decimal("150000"), customer=self.customer
        )
        self.assertEqual(discount, Decimal("150000"))

    def test_record_sale_with_wallet_deducts_balance(self):
        adjust_wallet(self.customer, Decimal("300000"), user=self.user)
        sale = record_sale(
            self.customer,
            Decimal("1000000"),
            discount_type="wallet",
            discount_value=Decimal("200000"),
            recorded_by=self.user,
        )
        self.customer.refresh_from_db()
        self.assertEqual(sale.discount, Decimal("200000"))
        self.assertEqual(sale.final_amount, Decimal("800000"))
        self.assertEqual(self.customer.wallet_balance, Decimal("100000"))

    def test_delete_sale_refunds_wallet(self):
        adjust_wallet(self.customer, Decimal("300000"), user=self.user)
        sale = record_sale(
            self.customer,
            Decimal("500000"),
            discount_type="wallet",
            discount_value=Decimal("100000"),
            recorded_by=self.user,
        )
        delete_sale(sale, user=self.user)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.wallet_balance, Decimal("300000"))
        self.assertTrue(Sale.all_objects.get(pk=sale.pk).is_deleted)
