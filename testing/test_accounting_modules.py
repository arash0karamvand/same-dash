from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.models import Customer, JournalEntry, JournalRevision, Material, WipClose
from logic.accounting_accounts import get_account
from testing.accounting_helpers import seed_accounts
from logic.accounting_documents import (
    create_accounting_document,
    submit_accounting_document,
    update_accounting_document,
)
from logic.costing import allocate_overhead, save_cost_center, save_overhead_period, save_wip_close
from logic.inventory_costing import issue_cost, receive_stock
from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER
from logic.sales import record_sale
from logic.treasury import allocate_deposit, create_deposit


class AccountingWorkflowTest(TestCase):
    def setUp(self):
        seed_accounts()

    def _document(self, debit_account, credit_account, amount=100):
        return create_accounting_document(
            lines=[
                {"account_id": debit_account, "debit": amount, "credit": 0, "description": "a"},
                {"account_id": credit_account, "debit": 0, "credit": amount, "description": "a"},
            ],
            description="workflow",
            is_approved=False,
        )

    def test_pending_edit_requires_reason_and_marks_override(self):
        bank = get_account("bank")
        revenue = get_account("other_revenue")
        created = self._document(bank.id, revenue.id)
        code = created["document_code"]
        submit_accounting_document(code)
        journal = JournalEntry.objects.get(document_code=code)
        self.assertEqual(journal.status, JournalEntry.STATUS_PENDING)
        with self.assertRaises(ValueError):
            update_accounting_document(
                code,
                lines=[
                    {"account_id": bank.id, "debit": 120, "credit": 0, "description": "a"},
                    {"account_id": revenue.id, "debit": 0, "credit": 120, "description": "a"},
                ],
                description="workflow",
            )
        update_accounting_document(
            code,
            lines=[
                {"account_id": bank.id, "debit": 120, "credit": 0, "description": "a"},
                {"account_id": revenue.id, "debit": 0, "credit": 120, "description": "a"},
            ],
            description="workflow",
            override_reason="اصلاح مبلغ",
        )
        journal.refresh_from_db()
        self.assertIsNotNone(journal.overridden_at)
        self.assertEqual(journal.override_reason, "اصلاح مبلغ")
        self.assertTrue(journal.revisions.filter(action=JournalRevision.ACTION_OVERRIDE).exists())
        self.assertNotEqual(journal.status, JournalEntry.STATUS_POSTED)


class FactoryCostingTest(TestCase):
    def setUp(self):
        seed_accounts(ledger=FACTORY_LEDGER)

    def test_overhead_allocation_balances(self):
        save_cost_center({
            "code": "cut", "name": "برش", "allocation_base": "machine_hours", "base_quantity": 1,
        }, ledger=FACTORY_LEDGER)
        save_cost_center({
            "code": "paint", "name": "رنگ", "allocation_base": "machine_hours", "base_quantity": 3,
        }, ledger=FACTORY_LEDGER)
        period = save_overhead_period({"year": 1404, "month": 6, "amount": 1000}, ledger=FACTORY_LEDGER)
        allocated = allocate_overhead(period["id"], ledger=FACTORY_LEDGER)
        shares = sorted(line["share_amount"] for line in allocated["lines"])
        self.assertEqual(shares, [250, 750])
        journal = JournalEntry.objects.get(document_code=allocated["document_code"])
        self.assertEqual(journal.status, JournalEntry.STATUS_DRAFT)
        self.assertEqual(
            sum(line.debit for line in journal.lines.all()),
            sum(line.credit for line in journal.lines.all()),
        )

    def test_equivalent_units(self):
        row = save_wip_close({
            "year": 1404,
            "month": 6,
            "completed_units": 10,
            "ending_wip_units": 4,
            "percent_complete": 50,
        }, ledger=FACTORY_LEDGER)
        self.assertEqual(Decimal(str(row["equivalent_units"])), Decimal("12"))
        self.assertEqual(WipClose.objects.get(pk=row["id"]).equivalent_units, Decimal("12.000"))


class InventoryValuationTest(TestCase):
    def test_weighted_average_and_fifo(self):
        average = Material.objects.create(name="میانگین", unit="عدد", unit_cost=0)
        receive_stock(average, 10, 100, previous_unit_cost=0)
        receive_stock(average, 10, 300, previous_unit_cost=average.unit_cost)
        average.refresh_from_db()
        self.assertEqual(average.unit_cost, Decimal("200"))

        fifo = Material.objects.create(
            name="فیفو", unit="عدد", unit_cost=0, valuation_method=Material.VALUATION_FIFO,
        )
        receive_stock(fifo, 10, 100, previous_unit_cost=0)
        receive_stock(fifo, 10, 300, previous_unit_cost=0)
        self.assertEqual(issue_cost(fifo, 10), Decimal("100"))


class CreditAndTreasuryTest(TestCase):
    def setUp(self):
        seed_accounts()
        self.customer = Customer.objects.create(
            full_name="خریدار", phone="09120000111", credit_limit=Decimal("1000"),
        )

    def test_check_sale_over_limit_is_rejected_without_override(self):
        with self.assertRaises(ValueError):
            record_sale(
                self.customer,
                Decimal("5000"),
                payment_method="check",
                payment_status="unpaid",
                paid_amount=0,
            )

    def test_override_requires_approve_permission(self):
        User = get_user_model()
        plain = User.objects.create_user(username="plain", password="x")
        with self.assertRaises(ValueError):
            record_sale(
                self.customer,
                Decimal("5000"),
                payment_method="check",
                payment_status="unpaid",
                paid_amount=0,
                credit_override_reason="مشتری قدیمی",
                recorded_by=plain,
            )
        boss = User.objects.create_superuser(username="boss", password="x", email="b@example.com")
        sale = record_sale(
            self.customer,
            Decimal("5000"),
            payment_method="check",
            payment_status="unpaid",
            paid_amount=0,
            credit_override_reason="تایید مدیر",
            recorded_by=boss,
        )
        self.assertEqual(sale.credit_override_reason, "تایید مدیر")

    def test_unidentified_deposit_stays_draft_until_posted(self):
        bank = get_account("bank")
        row = create_deposit({
            "deposit_date": "2026-09-01",
            "amount": 2500,
            "bank_account_id": bank.id,
            "description": "واریز نامشخص",
        })
        allocated = allocate_deposit(row["id"], self.customer)
        journal = JournalEntry.objects.get(document_code=allocated["document_code"])
        self.assertEqual(journal.status, JournalEntry.STATUS_DRAFT)
        self.assertEqual(allocated["status"], "allocated")
        self.assertEqual(
            sum(line.debit for line in journal.lines.all()),
            sum(line.credit for line in journal.lines.all()),
        )
