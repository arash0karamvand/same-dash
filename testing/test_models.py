"""تست مدل‌های دامنه."""

from django.test import TestCase

from backend.models import Customer, LoyaltyLevel, Sale


class CustomerModelTest(TestCase):
    def test_str_representation(self):
        customer = Customer.objects.create(full_name="علی رضایی", phone="09120000001")
        self.assertIn("علی رضایی", str(customer))
        self.assertIn("09120000001", str(customer))

    def test_defaults(self):
        customer = Customer.objects.create(full_name="تست", phone="09120000009")
        self.assertEqual(customer.total_purchases, 0)
        self.assertIsNone(customer.level)
        self.assertIsNone(customer.last_purchase_at)
        self.assertTrue(customer.is_active)


class LoyaltyLevelModelTest(TestCase):
    def test_ordering_by_min_purchase_asc(self):
        LoyaltyLevel.objects.create(name="طلایی", min_purchase=30_000_000)
        LoyaltyLevel.objects.create(name="برنز", min_purchase=0)
        first = LoyaltyLevel.objects.first()
        self.assertEqual(first.name, "برنز")

    def test_optional_max_purchase(self):
        vip = LoyaltyLevel.objects.create(name="VIP", min_purchase=70_000_000, max_purchase=None)
        self.assertIsNone(vip.max_purchase)


class SaleModelTest(TestCase):
    def test_sale_belongs_to_customer(self):
        customer = Customer.objects.create(full_name="تست", phone="09120000002")
        sale = Sale.objects.create(customer=customer, amount=5000, final_amount=5000)
        self.assertEqual(sale.customer, customer)
        self.assertEqual(customer.sales.count(), 1)
