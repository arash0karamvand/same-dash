"""تست منطق کسب‌وکار: سطح‌بندی، فروش، حسابداری و پیامک."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.models import (
    AccountingEntry,
    Customer,
    CustomerLevelHistory,
    LoyaltyLevel,
    OfficeOrder,
    SMSLog,
)
from logic.accounting import delete_accounting_entry
from logic.levels import find_level_for_amount, recalculate_customer_level
from logic.order_queues import create_factory_order_from_office, create_office_order_from_sale
from logic.sale_workflow import (
    approve_office_order,
    get_office_workflow_snapshot,
    recall_factory_order_to_office,
    receive_factory_order,
    reject_office_order,
    rollback_factory_receive,
)
from logic.sales import delete_sale, record_payment, record_sale, update_sale
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

    def test_delete_sale_soft_deletes_office_and_factory_orders(self):
        user = User.objects.create_user(username="wfuser", password="secret123")
        sale = record_sale(self.customer, Decimal("5000000"), payment_status="paid")
        office = create_office_order_from_sale(sale, user)
        factory = create_factory_order_from_office(office, user)

        delete_sale(sale)
        office.refresh_from_db()
        factory.refresh_from_db()
        sale.refresh_from_db()
        self.assertTrue(sale.is_deleted)
        self.assertTrue(office.is_deleted)
        self.assertTrue(factory.is_deleted)

    def test_update_sale_syncs_office_order_amounts(self):
        user = User.objects.create_user(username="wfuser2", password="secret123")
        sale = record_sale(
            self.customer,
            Decimal("5000000"),
            payment_status="installment",
            paid_amount=Decimal("2000000"),
        )
        office = create_office_order_from_sale(sale, user)
        update_sale(sale, amount=Decimal("6000000"), paid_amount=Decimal("3000000"))
        office.refresh_from_db()
        self.assertEqual(office.final_amount, Decimal("6000000"))
        self.assertEqual(office.paid_amount, Decimal("3000000"))

    def test_reject_office_order_returns_sale_to_branch_queue(self):
        user = User.objects.create_user(username="wfuser4", password="secret123")
        sale = record_sale(self.customer, Decimal("5000000"), payment_status="paid")
        office = create_office_order_from_sale(sale, user)

        reject_office_order(office, user, reason="اطلاعات ناقص")
        sale.refresh_from_db()
        office.refresh_from_db()

        self.assertTrue(office.is_deleted)
        self.assertEqual(sale.workflow_stage, "pending_branch")
        self.assertIsNone(sale.transferred_to_office_at)
        self.assertIn("عدم تایید اداری", sale.description)

        office2 = create_office_order_from_sale(sale, user)
        self.assertFalse(office2.is_deleted)
        self.assertEqual(office2.id, office.id)
        self.assertEqual(office2.status, OfficeOrder.STATUS_PENDING)

    def test_recall_factory_order_to_office(self):
        user = User.objects.create_user(username="wfuser5", password="secret123")
        sale = record_sale(self.customer, Decimal("5000000"), payment_status="paid")
        office = create_office_order_from_sale(sale, user)
        approve_office_order(office, user)

        office.refresh_from_db()
        snapshot = get_office_workflow_snapshot(office)
        self.assertEqual(snapshot["workflow_stage"], "accounting_approved")
        self.assertTrue(snapshot["can_rollback"])
        self.assertEqual(snapshot["rollback_action"], "to_office")

        recall_factory_order_to_office(office, user, reason="ارسال اشتباه")
        office.refresh_from_db()
        sale.refresh_from_db()

        self.assertEqual(office.status, OfficeOrder.STATUS_PENDING)
        self.assertIn("برگشت اداری", sale.description)

    def test_rollback_factory_receive(self):
        user = User.objects.create_user(username="wfuser6", password="secret123")
        sale = record_sale(self.customer, Decimal("5000000"), payment_status="paid")
        office = create_office_order_from_sale(sale, user)
        approve_office_order(office, user)
        factory = office.factory_order
        receive_factory_order(factory, user)
        rollback_factory_receive(factory, user, reason="اشتباه دریافت")

        factory.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual(factory.workflow_stage, factory.WORKFLOW_STAGE_ACCOUNTING_APPROVED)
        self.assertEqual(sale.workflow_stage, "accounting_approved")

    def test_delete_payment_entry_reverses_sale_paid_amount(self):
        sale = record_sale(
            self.customer,
            Decimal("8000000"),
            payment_status="installment",
            paid_amount=Decimal("3000000"),
        )
        record_payment(sale, Decimal("2000000"))
        payment = AccountingEntry.objects.filter(entry_type="payment", sale=sale).order_by("-id").first()
        delete_accounting_entry(payment)
        sale.refresh_from_db()
        self.assertEqual(sale.paid_amount, Decimal("3000000"))

    def test_delete_sale_entry_soft_deletes_invoice_everywhere(self):
        user = User.objects.create_user(username="wfuser3", password="secret123")
        sale = record_sale(self.customer, Decimal("5000000"), payment_status="paid")
        office = create_office_order_from_sale(sale, user)
        sale_entry = AccountingEntry.objects.get(entry_type="sale", sale=sale)
        result = delete_accounting_entry(sale_entry)
        office.refresh_from_db()
        sale.refresh_from_db()
        self.assertTrue(result["sale_deleted"])
        self.assertTrue(sale.is_deleted)
        self.assertTrue(office.is_deleted)


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
