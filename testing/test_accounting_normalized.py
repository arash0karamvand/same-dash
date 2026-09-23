from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.test import TestCase

from backend.models import Customer, JournalEntry, JournalLine
from logic.accounting_accounts import get_account
from logic.accounting_documents import create_accounting_document
from logic.accounting_transfer import transfer_factory_document_to_office
from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER
from logic.sales import record_sale
from testing.accounting_helpers import seed_accounts


class NormalizedAccountingTest(TestCase):
    def setUp(self):
        seed_accounts()

    def test_posted_journal_is_balanced_and_has_two_lines(self):
        bank = get_account("bank")
        revenue = get_account("other_revenue")
        result = create_accounting_document(
            lines=[
                {"account_id": bank.id, "debit": 100, "credit": 0, "description": "test"},
                {"account_id": revenue.id, "debit": 0, "credit": 100, "description": "test"},
            ],
            description="test",
            is_approved=True,
        )
        journal = result["journal"]
        self.assertEqual(journal.status, JournalEntry.STATUS_POSTED)
        self.assertEqual(journal.lines.count(), 2)
        self.assertEqual(
            sum(line.debit for line in journal.lines.all()),
            sum(line.credit for line in journal.lines.all()),
        )

    def test_post_rejects_unbalanced_journal(self):
        journal = JournalEntry.objects.create(
            ledger=OFFICE_LEDGER.model,
            document_number=999,
            document_code="TEST-999",
        )
        JournalLine.objects.create(
            journal=journal,
            account=get_account("bank"),
            debit=100,
            line_number=1,
        )
        with self.assertRaises(ValidationError):
            journal.post()

    def test_sale_creates_one_balanced_journal(self):
        customer = Customer.objects.create(full_name="Test", phone="09120000999")
        sale = record_sale(
            customer,
            Decimal("1000"),
            payment_status="paid",
            payment_method="cash",
        )
        journal = JournalEntry.objects.get(order_links__order=sale, entry_type="sale")
        self.assertEqual(journal.lines.count(), 2)
        totals = journal.lines.aggregate(
            debit=Sum("debit"),
            credit=Sum("credit"),
        )
        self.assertEqual(totals["debit"], totals["credit"])

    def test_cross_ledger_accounts_are_rejected(self):
        seed_accounts(ledger=FACTORY_LEDGER)
        with self.assertRaises(ValueError):
            create_accounting_document(
                lines=[
                    {"account_id": get_account("bank").id, "debit": 100, "credit": 0},
                    {"account_id": get_account("other_revenue", ledger=FACTORY_LEDGER).id,
                     "debit": 0, "credit": 100},
                ],
                ledger=OFFICE_LEDGER,
            )

    def test_factory_transfer_creates_relational_office_journal(self):
        seed_accounts(ledger=FACTORY_LEDGER)
        source = create_accounting_document(
            lines=[
                {"account_id": get_account("bank", ledger=FACTORY_LEDGER).id,
                 "debit": 100, "credit": 0},
                {"account_id": get_account("other_revenue", ledger=FACTORY_LEDGER).id,
                 "debit": 0, "credit": 100},
            ],
            ledger=FACTORY_LEDGER,
            is_approved=True,
        )["journal"]
        transfer_factory_document_to_office(document_code=source.document_code)
        target = source.transferred_journal
        self.assertEqual(target.ledger.code, "office")
        self.assertEqual(target.transfer_source_id, source.id)
        self.assertEqual(target.lines.count(), 2)
