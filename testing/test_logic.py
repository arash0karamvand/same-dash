"""تست منطق کسب‌وکار: سطح‌بندی، فروش، حسابداری و پیامک."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.models import (
    AccountingEntry,
    Customer,
    CustomerLevelHistory,
    LoyaltyLevel,
    SMSLog,
)
from logic.levels import find_level_for_amount, recalculate_customer_level
from logic.sales import delete_sale, record_payment, record_sale
from logic.sms import (
    is_valid_phone,
    send_sms,
    send_sms_to_all_active_customers,
    send_sms_to_level,
)

User = get_user_model()


class LevelLogicTest(TestCase):
    def setUp(self):
        LoyaltyLevel.objects.create(name="برنز", min_purchase=0, max_purchase=10_000_000)
        LoyaltyLevel.objects.create(name="نقره‌ای", min_purchase=10_000_000, max_purchase=30_000_000)
        LoyaltyLevel.objects.create(name="VIP", min_purchase=70_000_000, max_purchase=None)

    def test_selects_correct_range(self):
        self.assertEqual(find_level_for_amount(Decimal("5000000")).name, "برنز")
        self.assertEqual(find_level_for_amount(Decimal("10000000")).name, "نقره‌ای")
        self.assertEqual(find_level_for_amount(Decimal("90000000")).name, "VIP")

    def test_amount_between_defined_ranges_returns_none(self):
        self.assertIsNone(find_level_for_amount(Decimal("50000000")))

    def test_recalculate_creates_history_on_change(self):
        customer = Customer.objects.create(
            full_name="تست", phone="09120000003", total_purchases=Decimal("15000000")
        )
        recalculate_customer_level(customer)
        self.assertEqual(customer.level.name, "نقره‌ای")
        self.assertEqual(CustomerLevelHistory.objects.filter(customer=customer).count(), 1)


class SalesLogicTest(TestCase):
    def setUp(self):
        LoyaltyLevel.objects.create(name="برنز", min_purchase=0, max_purchase=10_000_000)
        LoyaltyLevel.objects.create(name="نقره‌ای", min_purchase=10_000_000, max_purchase=30_000_000)
        self.customer = Customer.objects.create(full_name="تست", phone="09120000005")

    def test_record_sale_updates_totals_level_and_accounting_when_paid(self):
        record_sale(self.customer, Decimal("12000000"), discount=Decimal("2000000"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_purchases, Decimal("10000000"))
        self.assertEqual(self.customer.level.name, "نقره‌ای")
        entry = AccountingEntry.objects.get()
        self.assertEqual(entry.credit, Decimal("10000000"))

    def test_unpaid_sale_does_not_update_customer_totals(self):
        record_sale(self.customer, Decimal("5000000"), payment_status="unpaid")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_purchases, Decimal("0"))
        self.assertIsNone(self.customer.level)
        self.assertEqual(AccountingEntry.objects.filter(entry_type="receivable").count(), 1)

    def test_partial_payment_updates_customer_and_receivable(self):
        sale = record_sale(
            self.customer,
            Decimal("10000000"),
            payment_status="installment",
            paid_amount=Decimal("4000000"),
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_purchases, Decimal("4000000"))
        receivable = AccountingEntry.objects.get(entry_type="receivable", sale=sale)
        self.assertEqual(receivable.debit, Decimal("6000000"))

    def test_record_payment_settles_balance(self):
        sale = record_sale(
            self.customer,
            Decimal("8000000"),
            payment_status="installment",
            paid_amount=Decimal("3000000"),
        )
        record_payment(sale, Decimal("5000000"))
        sale.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(sale.payment_status, "paid")
        self.assertEqual(sale.paid_amount, Decimal("8000000"))
        self.assertEqual(self.customer.total_purchases, Decimal("8000000"))
        self.assertFalse(AccountingEntry.objects.filter(entry_type="receivable", sale=sale).exists())

    def test_delete_sale_reverses_customer_totals_and_level(self):
        silver = LoyaltyLevel.objects.get(name="نقره‌ای")
        bronze = LoyaltyLevel.objects.get(name="برنز")
        sale = record_sale(self.customer, Decimal("12000000"), discount=Decimal("2000000"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_purchases, Decimal("10000000"))
        self.assertEqual(self.customer.level_id, silver.id)

        deleted = delete_sale(sale)
        self.assertGreater(deleted, 0)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_purchases, Decimal("0"))
        self.assertEqual(self.customer.level_id, bronze.id)
        self.assertIsNone(self.customer.last_purchase_at)
        sale.refresh_from_db()
        self.assertTrue(sale.is_deleted)

    def test_delete_sale_keeps_other_sales_in_totals(self):
        sale1 = record_sale(self.customer, Decimal("3000000"), payment_status="paid")
        record_sale(self.customer, Decimal("5000000"), payment_status="paid")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_purchases, Decimal("8000000"))

        delete_sale(sale1)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_purchases, Decimal("5000000"))
        self.assertIsNotNone(self.customer.last_purchase_at)

    def test_negative_amount_rejected(self):
        with self.assertRaises(ValueError):
            record_sale(self.customer, Decimal("-100"))

    def test_discount_greater_than_amount_rejected(self):
        with self.assertRaises(ValueError):
            record_sale(self.customer, Decimal("1000"), discount=Decimal("2000"))


class SmsLogicTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="smsuser", password="secret123")

    def test_phone_validation(self):
        self.assertTrue(is_valid_phone("09120000006"))
        self.assertFalse(is_valid_phone("123"))
        self.assertFalse(is_valid_phone(""))

    def test_mock_gateway_does_not_claim_real_send(self):
        log = send_sms("09120000006", "سلام", user=self.user)
        self.assertEqual(log.status, "mock_sent")
        self.assertIsNone(log.sent_at)
        self.assertEqual(log.sms_type, "manual")
        self.assertEqual(log.created_by, self.user)
        self.assertEqual(SMSLog.objects.count(), 1)

    def test_generic_gateway_pending_without_config(self):
        with self.settings(SMS_GATEWAY="logic.sms.GenericHttpSmsGateway", SMS_API_KEY="", SMS_SENDER=""):
            log = send_sms("09120000007", "سلام")
        self.assertEqual(log.status, "pending_provider_config")
        self.assertIsNone(log.sent_at)

    def test_invalid_phone_is_logged_and_skipped(self):
        Customer.objects.create(full_name="Bad", phone="invalid", is_active=True)
        Customer.objects.create(full_name="Good", phone="09120000008", is_active=True)
        result = send_sms_to_all_active_customers("سلام", user=self.user)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["successful"], 0)
        self.assertEqual(SMSLog.objects.count(), 2)

    def test_send_to_level_only_active_customers(self):
        level = LoyaltyLevel.objects.create(name="Gold", min_purchase=0)
        Customer.objects.create(full_name="Active", phone="09120000009", level=level, is_active=True)
        Customer.objects.create(full_name="Inactive", phone="09120000010", level=level, is_active=False)
        result = send_sms_to_level(level.id, "پیشنهاد ویژه", user=self.user)
        self.assertEqual(len(result["results"]), 1)
