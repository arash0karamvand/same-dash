"""تست منطق کسب‌وکار: سطح‌بندی، فروش، حسابداری و پیامک."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.models import (
    AccountingEntry,
    Customer,
    CustomerLevelHistory,
    CustomerRfmScore,
    FactoryOrder,
    JournalEntry,
    JournalLine,
    LoyaltyLevel,
    OfficeOrder,
    RfmSegment,
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
from logic.checks_excel_export import checks_excel_bytes
from logic.installments import pay_installment
from logic.sales import delete_sale, record_payment, record_sale, update_sale
from logic.rfm import seed_rfm_defaults
from logic.sms import (
    is_valid_phone,
    send_sms,
    send_sms_to_all_active_customers,
    send_sms_to_segment,
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
        customer = Customer.objects.create(full_name="تست", phone="09120000003")
        record_sale(customer, Decimal("15000000"), payment_status="paid")
        recalculate_customer_level(customer)
        self.assertEqual(customer.level.name, "نقره‌ای")
        self.assertEqual(CustomerLevelHistory.objects.filter(customer=customer).count(), 1)


class SalesLogicTest(TestCase):
    def setUp(self):
        seed_rfm_defaults()
        self.customer = Customer.objects.create(full_name="تست", phone="09120000005")

    def test_record_sale_updates_totals_level_and_accounting_when_paid(self):
        record_sale(self.customer, Decimal("12000000"), discount=Decimal("2000000"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_purchases, Decimal("10000000"))
        score = CustomerRfmScore.objects.get(customer=self.customer)
        self.assertEqual(score.segment.slug, "newcomers")
        journal = JournalEntry.objects.get(entry_type="sale")
        entry = journal.lines.get(account__slug="product_sales")
        self.assertEqual(entry.credit, Decimal("10000000"))
        payment = journal.lines.get(account__slug="cash_documents")
        self.assertEqual(payment.debit, Decimal("10000000"))

    def test_unpaid_sale_does_not_update_customer_totals(self):
        record_sale(self.customer, Decimal("5000000"), payment_status="unpaid")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_purchases, Decimal("0"))
        self.assertFalse(CustomerRfmScore.objects.filter(customer=self.customer).exists())
        self.assertEqual(JournalLine.objects.filter(account__slug="receivables").count(), 1)

    def test_partial_payment_updates_customer_and_receivable(self):
        sale = record_sale(
            self.customer,
            Decimal("10000000"),
            payment_status="installment",
            paid_amount=Decimal("4000000"),
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_purchases, Decimal("4000000"))
        receivable = JournalLine.objects.get(
            journal__order_links__order=sale, account__slug="receivables"
        )
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
        receivable_lines = JournalLine.objects.filter(
            journal__order_links__order=sale, account__slug="receivables"
        )
        self.assertEqual(
            sum(line.debit - line.credit for line in receivable_lines),
            Decimal("0"),
        )

    def test_delete_sale_reverses_customer_totals_and_level(self):
        sale = record_sale(self.customer, Decimal("12000000"), discount=Decimal("2000000"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_purchases, Decimal("10000000"))
        self.assertTrue(CustomerRfmScore.objects.filter(customer=self.customer).exists())

        deleted = delete_sale(sale)
        self.assertGreater(deleted, 0)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_purchases, Decimal("0"))
        self.assertFalse(CustomerRfmScore.objects.filter(customer=self.customer).exists())
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

        self.assertFalse(office.is_deleted)
        self.assertEqual(sale.workflow_stage, "pending_branch")
        self.assertIsNone(sale.office_released_at)
        self.assertIn("عدم تایید اداری", sale.description)

        office2 = create_office_order_from_sale(sale, user)
        self.assertFalse(office2.is_deleted)
        self.assertEqual(office2.id, office.id)
        self.assertEqual(office2.status, OfficeOrder.STATUS_PENDING)

    def test_automatic_accounting_draft_when_sent_to_office(self):
        from backend.models import AccountingEntry
        from logic.accounting_accounts import get_account

        user = User.objects.create_user(username="wfauto", password="secret123")
        sale = record_sale(
            self.customer,
            Decimal("5000000"),
            payment_status="paid",
            payment_method="card",
            accounting_mode="automatic",
            recorded_by=user,
        )
        office = create_office_order_from_sale(sale, user)
        self.assertIsNotNone(office)
        journal = JournalEntry.objects.get(order_links__order=sale, entry_type="sale")
        self.assertEqual(journal.status, JournalEntry.STATUS_DRAFT)
        payment = journal.lines.filter(account__slug="bank").first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.account_id, get_account("bank").id)

    def test_manual_accounting_skips_entries_until_manual_posting(self):
        from backend.models import AccountingEntry

        user = User.objects.create_user(username="wfmanual", password="secret123")
        sale = record_sale(
            self.customer,
            Decimal("5000000"),
            payment_status="paid",
            accounting_mode="manual",
            recorded_by=user,
        )
        office = create_office_order_from_sale(sale, user)
        self.assertFalse(JournalEntry.objects.filter(order_links__order=sale).exists())
        approve_office_order(office, user)
        self.assertFalse(JournalEntry.objects.filter(order_links__order=sale).exists())

    def test_automatic_office_approve_approves_accounting_entries(self):
        from backend.models import AccountingEntry

        user = User.objects.create_user(username="wfauto2", password="secret123")
        sale = record_sale(
            self.customer,
            Decimal("5000000"),
            payment_status="paid",
            accounting_mode="automatic",
            recorded_by=user,
        )
        office = create_office_order_from_sale(sale, user)
        approve_office_order(office, user)
        self.assertFalse(
            JournalEntry.objects.filter(order_links__order=sale, status="draft").exists()
        )
        self.assertTrue(
            JournalEntry.objects.filter(order_links__order=sale, status="posted").exists()
        )

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
        factory = FactoryOrder.objects.get(pk=office.pk)
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
        sale_entry = AccountingEntry.objects.filter(entry_type="sale", sale=sale).first()
        result = delete_accounting_entry(sale_entry)
        office.refresh_from_db()
        sale.refresh_from_db()
        self.assertTrue(result["sale_deleted"])
        self.assertTrue(sale.is_deleted)
        self.assertTrue(office.is_deleted)


class CheckAccountingLogicTest(TestCase):
    def setUp(self):
        LoyaltyLevel.objects.create(name="برنز", min_purchase=0, max_purchase=10_000_000)
        self.customer = Customer.objects.create(full_name="چک", phone="09120000099")
        self.user = User.objects.create_user(username="checkuser", password="secret123")

    def test_office_approve_registers_checks_in_selected_account(self):
        from datetime import date, timedelta

        from logic.accounting_accounts import get_account
        from logic.check_accounting import get_user_accounting_preference

        due = (date.today() + timedelta(days=30)).isoformat()
        sale = record_sale(
            self.customer,
            Decimal("10000000"),
            payment_status="installment",
            payment_method="check",
            paid_amount=Decimal("0"),
            accounting_mode="automatic",
            installments=[
                {
                    "amount": 10000000,
                    "due_date": due,
                    "payment_method": "check",
                    "check_number": "998877",
                    "bank_name": "ملی",
                }
            ],
            recorded_by=self.user,
        )
        office = create_office_order_from_sale(sale, self.user)
        reg = get_account("collection_at_bank")
        dep = get_account("bank")
        approve_office_order(
            office,
            self.user,
            check_registration_account_id=reg.id,
            check_deposit_account_id=dep.id,
            save_check_accounts_as_default=True,
        )
        inst = sale.installments.first()
        self.assertIsNotNone(inst.accounting_registered_at)
        self.assertEqual(inst.registration_account_id, reg.id)
        payment = AccountingEntry.objects.filter(
            sale=sale,
            entry_type="payment",
            account=reg,
            debit=Decimal("10000000"),
        ).exists()
        self.assertTrue(payment)
        prefs = get_user_accounting_preference(self.user)
        self.assertEqual(prefs["default_check_registration_account_id"], reg.id)

    def test_pay_registered_check_transfers_to_deposit_account(self):
        from datetime import date, timedelta

        from logic.accounting_accounts import get_account

        due = (date.today() + timedelta(days=30)).isoformat()
        sale = record_sale(
            self.customer,
            Decimal("5000000"),
            payment_status="installment",
            payment_method="check",
            paid_amount=Decimal("0"),
            accounting_mode="automatic",
            installments=[
                {
                    "amount": 5000000,
                    "due_date": due,
                    "payment_method": "check",
                    "check_number": "111",
                    "bank_name": "صادرات",
                }
            ],
            recorded_by=self.user,
        )
        office = create_office_order_from_sale(sale, self.user)
        reg = get_account("collection_at_bank")
        dep = get_account("bank")
        approve_office_order(
            office,
            self.user,
            check_registration_account_id=reg.id,
            check_deposit_account_id=dep.id,
        )
        inst = sale.installments.first()
        pay_installment(inst, recorded_by=self.user)
        sale.refresh_from_db()
        inst.refresh_from_db()
        self.assertEqual(inst.status, "paid")
        self.assertEqual(sale.paid_amount, Decimal("5000000"))
        self.assertTrue(
            AccountingEntry.objects.filter(
                sale=sale,
                entry_type="payment",
                account=dep,
                debit=Decimal("5000000"),
            ).exists()
        )

    def test_checks_excel_export_bytes(self):
        from datetime import date, timedelta

        due = (date.today() + timedelta(days=15)).isoformat()
        sale = record_sale(
            self.customer,
            Decimal("3000000"),
            payment_status="installment",
            payment_method="check",
            paid_amount=Decimal("0"),
            installments=[
                {
                    "amount": 3000000,
                    "due_date": due,
                    "payment_method": "check",
                    "check_number": "555",
                    "bank_name": "ملت",
                    "receiver_name": "علی",
                }
            ],
        )
        inst = sale.installments.first()
        content = checks_excel_bytes([inst])
        self.assertTrue(content.startswith(b"PK"))


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

    def test_send_to_segment_only_active_customers(self):
        seed_rfm_defaults()
        segment = RfmSegment.objects.get(slug="newcomers")
        active = Customer.objects.create(full_name="Active", phone="09120000009", is_active=True)
        inactive = Customer.objects.create(full_name="Inactive", phone="09120000010", is_active=False)
        CustomerRfmScore.objects.create(
            customer=active, segment=segment, rfm_code="511", r_score=5, f_score=1, m_score=1
        )
        CustomerRfmScore.objects.create(
            customer=inactive, segment=segment, rfm_code="511", r_score=5, f_score=1, m_score=1
        )
        result = send_sms_to_segment(segment.id, "پیشنهاد ویژه", user=self.user)
        self.assertEqual(len(result["results"]), 1)


class FactoryAccountingTransferTest(TestCase):
    def setUp(self):
        from testing.accounting_helpers import seed_accounts
        from logic.accounting_documents import create_accounting_document
        from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER

        seed_accounts(ledger=OFFICE_LEDGER)
        seed_accounts(ledger=FACTORY_LEDGER)
        self.office_bank = OFFICE_LEDGER.Account.objects.get(slug="bank")
        self.factory_bank = FACTORY_LEDGER.Account.objects.get(slug="bank")
        self.factory_admin = FACTORY_LEDGER.Account.objects.get(slug="admin_overhead")

        factory_doc = create_accounting_document(
            lines=[
                {
                    "account_id": self.factory_bank.id,
                    "debit": 100000,
                    "credit": 0,
                    "description": "بدهکار بانک",
                },
                {
                    "account_id": self.factory_admin.id,
                    "debit": 0,
                    "credit": 100000,
                    "description": "بستانکار سربار",
                },
            ],
            description="سند تست کارخانه",
            is_approved=True,
            ledger=FACTORY_LEDGER,
        )
        self.factory_document_code = factory_doc["document_code"]
        self.factory_entries = list(
            FACTORY_LEDGER.AccountingEntry.objects.filter(document_code=self.factory_document_code)
        )

    def test_preview_marks_shared_general_accounts(self):
        from logic.accounting_transfer import preview_transfer

        preview = preview_transfer(document_code=self.factory_document_code)
        self.assertEqual(preview["mappable_count"], 2)
        self.assertEqual(preview["unmappable_count"], 0)
        self.assertTrue(preview["can_transfer"])

    def test_transfer_creates_office_document_and_locks_factory(self):
        from logic.accounting import entry_permissions
        from logic.accounting_transfer import preview_transfer, transfer_factory_document_to_office
        from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER

        result = transfer_factory_document_to_office(document_code=self.factory_document_code)
        self.assertTrue(result["office_document_code"].startswith("S-"))
        self.assertEqual(result["lines_transferred"], 2)

        office_entries = OFFICE_LEDGER.AccountingEntry.objects.filter(
            document_code=result["office_document_code"]
        )
        self.assertEqual(office_entries.count(), 2)
        self.assertEqual(office_entries.first().attach_code, self.factory_document_code)

        factory_entries = FACTORY_LEDGER.AccountingEntry.objects.filter(
            document_code=self.factory_document_code
        )
        for entry in factory_entries:
            self.assertIsNotNone(entry.transferred_to_office_at)
            self.assertEqual(entry.office_document_code, result["office_document_code"])
            perms = entry_permissions(entry, user=None, ledger=FACTORY_LEDGER)
            self.assertFalse(perms["can_edit"])
            self.assertFalse(perms["can_delete"])

        preview = preview_transfer(document_code=self.factory_document_code)
        self.assertTrue(preview["already_transferred"])

    def test_duplicate_transfer_rejected(self):
        from logic.accounting_transfer import transfer_factory_document_to_office

        transfer_factory_document_to_office(document_code=self.factory_document_code)
        with self.assertRaises(ValueError) as ctx:
            transfer_factory_document_to_office(document_code=self.factory_document_code)
        self.assertIn("قبلاً", str(ctx.exception))

    def test_unshared_subsidiary_blocks_transfer(self):
        from backend.models import FactorySubsidiaryAccount, SubsidiaryAccount
        from logic.accounting_documents import create_accounting_document
        from logic.accounting_transfer import preview_transfer, transfer_factory_document_to_office
        from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER

        office_sub = SubsidiaryAccount.objects.create(
            account=self.office_bank,
            code="99",
            name="معین اداری",
        )
        factory_sub = FactorySubsidiaryAccount.objects.create(
            account=self.factory_bank,
            code="88",
            name="معین کارخانه",
        )
        doc = create_accounting_document(
            lines=[
                {
                    "account_id": self.factory_bank.id,
                    "subsidiary_id": factory_sub.id,
                    "debit": 50000,
                    "credit": 0,
                    "description": "با معین",
                },
                {
                    "account_id": self.factory_admin.id,
                    "debit": 0,
                    "credit": 50000,
                    "description": "طرف",
                },
            ],
            description="سند با معین غیرمشترک",
            ledger=FACTORY_LEDGER,
        )
        preview = preview_transfer(document_code=doc["document_code"])
        self.assertEqual(preview["unmappable_count"], 1)
        self.assertFalse(preview["can_transfer"])
        with self.assertRaises(ValueError) as ctx:
            transfer_factory_document_to_office(document_code=doc["document_code"])
        self.assertIn("غیرمشترک", str(ctx.exception))
        self.assertFalse(
            OFFICE_LEDGER.AccountingEntry.objects.filter(description__contains="سند با معین").exists()
        )
        _ = office_sub


class AccountingDocumentCrudTest(TestCase):
    def setUp(self):
        from testing.accounting_helpers import seed_accounts
        from logic.accounting_documents import create_accounting_document
        from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER

        seed_accounts(ledger=OFFICE_LEDGER)
        seed_accounts(ledger=FACTORY_LEDGER)
        self.office_ledger = OFFICE_LEDGER
        self.factory_ledger = FACTORY_LEDGER
        self.office_bank = OFFICE_LEDGER.Account.objects.get(slug="bank")
        self.office_admin = OFFICE_LEDGER.Account.objects.get(slug="admin_overhead")
        self.factory_bank = FACTORY_LEDGER.Account.objects.get(slug="bank")
        self.factory_admin = FACTORY_LEDGER.Account.objects.get(slug="admin_overhead")

        office_doc = create_accounting_document(
            lines=[
                {"account_id": self.office_bank.id, "debit": 200000, "credit": 0, "description": "بدهکار"},
                {"account_id": self.office_admin.id, "debit": 0, "credit": 200000, "description": "بستانکار"},
            ],
            description="سند اداری تست",
            ledger=OFFICE_LEDGER,
        )
        self.office_document_code = office_doc["document_code"]

        factory_doc = create_accounting_document(
            lines=[
                {"account_id": self.factory_bank.id, "debit": 150000, "credit": 0, "description": "بدهکار کارخانه"},
                {"account_id": self.factory_admin.id, "debit": 0, "credit": 150000, "description": "بستانکار کارخانه"},
            ],
            description="سند کارخانه تست",
            ledger=FACTORY_LEDGER,
        )
        self.factory_document_code = factory_doc["document_code"]

    def test_list_and_get_office_document(self):
        from logic.accounting_documents import get_accounting_document, list_accounting_documents

        listed = list_accounting_documents({}, ledger=self.office_ledger)
        self.assertGreaterEqual(listed["total"], 1)
        codes = [row["document_code"] for row in listed["results"]]
        self.assertIn(self.office_document_code, codes)

        doc = get_accounting_document(self.office_document_code, ledger=self.office_ledger)
        self.assertEqual(doc["line_count"], 2)
        self.assertEqual(doc["total_debit"], 200000)
        self.assertTrue(doc["can_edit"])

    def test_update_office_document(self):
        from logic.accounting_documents import get_accounting_document, update_accounting_document

        doc = get_accounting_document(self.office_document_code, ledger=self.office_ledger)
        lines = [
            {
                "id": line["id"],
                "account_id": line["account_id"],
                "subsidiary_id": line.get("subsidiary_id"),
                "detailed_id": line.get("detailed_id"),
                "debit": line["debit"],
                "credit": line["credit"],
                "description": line["description"],
            }
            for line in doc["lines"]
        ]
        lines[0]["debit"] = 300000
        lines[0]["description"] = "سند ویرایش‌شده"
        lines[1]["credit"] = 300000
        lines[1]["description"] = "سند ویرایش‌شده"

        updated = update_accounting_document(
            self.office_document_code,
            lines=lines,
            description="سند ویرایش‌شده",
            ledger=self.office_ledger,
        )
        self.assertEqual(updated["total_debit"], 300000)
        self.assertEqual(updated["description"], "سند ویرایش‌شده")

    def test_delete_office_document(self):
        from logic.accounting_documents import delete_accounting_document, get_accounting_document

        result = delete_accounting_document(self.office_document_code, ledger=self.office_ledger)
        self.assertTrue(result["deleted"])
        with self.assertRaises(LookupError):
            get_accounting_document(self.office_document_code, ledger=self.office_ledger)

    def test_transferred_factory_document_blocked(self):
        from logic.accounting import entry_permissions
        from logic.accounting_documents import delete_accounting_document, update_accounting_document
        from logic.accounting_transfer import transfer_factory_document_to_office

        transfer_factory_document_to_office(document_code=self.factory_document_code)
        entries = list(
            self.factory_ledger.AccountingEntry.objects.filter(document_code=self.factory_document_code)
        )
        for entry in entries:
            perms = entry_permissions(entry, user=None, ledger=self.factory_ledger)
            self.assertFalse(perms["can_edit"])
            self.assertFalse(perms["can_delete"])

        with self.assertRaises(ValueError):
            update_accounting_document(
                self.factory_document_code,
                lines=[{"account_id": self.factory_bank.id, "debit": 1, "credit": 0, "description": "x"}],
                ledger=self.factory_ledger,
            )
        with self.assertRaises(ValueError):
            delete_accounting_document(self.factory_document_code, ledger=self.factory_ledger)
