"""صدور سند: تراز بدهکار و بستانکار، قفل سند نهایی، و درخواست فروش و انبار."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from backend.models import JournalEntry, JournalLine
from logic.accounting_accounts import get_account
from logic.document_issuance import DocumentBalanceError, DocumentIssuanceService, PostedDocumentError
from logic.ledger import OFFICE_LEDGER
from testing.accounting_helpers import seed_accounts


class DocumentIssuanceServiceTest(TestCase):
    def setUp(self):
        seed_accounts(ledger=OFFICE_LEDGER)
        self.service = DocumentIssuanceService()
        self.bank = get_account("bank")
        self.revenue = get_account("other_revenue")

    def _lines(self, amount=1000, *, debit=None, credit=None):
        return [
            {"account": self.bank, "debit": debit if debit is not None else amount, "credit": 0, "description": "بدهکار"},
            {"account": self.revenue, "debit": 0, "credit": credit if credit is not None else amount, "description": "بستانکار"},
        ]

    def test_unbalanced_request_is_rejected_before_insert(self):
        before = JournalEntry.objects.count()
        with self.assertRaises(DocumentBalanceError):
            self.service.issue(lines=self._lines(debit=1000, credit=900), description="نامتوازن")
        self.assertEqual(JournalEntry.objects.count(), before)

    def test_sales_and_warehouse_requests_post_balanced_documents(self):
        sale_journal = self.service.receive_sales_request(
            lines=self._lines(2500),
            description="فروش آزمایشی",
            finalize=True,
        )
        warehouse_journal = self.service.receive_warehouse_request(
            lines=self._lines(1800),
            description="رسید انبار آزمایشی",
            finalize=True,
        )
        self.assertEqual(sale_journal.entry_type, "sale")
        self.assertEqual(warehouse_journal.entry_type, "adjustment")
        for journal, amount in ((sale_journal, 2500), (warehouse_journal, 1800)):
            journal.refresh_from_db()
            self.assertEqual(journal.status, JournalEntry.STATUS_POSTED)
            debit = sum((line.debit for line in journal.lines.all()), Decimal(0))
            credit = sum((line.credit for line in journal.lines.all()), Decimal(0))
            self.assertEqual(debit, credit)
            self.assertEqual(debit, Decimal(amount))

    def test_posted_document_cannot_be_edited_or_deleted(self):
        journal = self.service.receive_sales_request(lines=self._lines(400), description="قطعی", finalize=True)
        journal.description = "دستکاری"
        with self.assertRaises(ValidationError):
            journal.save(update_fields=["description"])
        with self.assertRaises(ValidationError):
            journal.delete()
        with self.assertRaises(ValidationError):
            JournalEntry.objects.filter(pk=journal.pk).update(description="دستکاری")
        with self.assertRaises(ValidationError):
            JournalLine.objects.filter(journal=journal).update(description="دستکاری")
        with self.assertRaises(ValidationError):
            JournalLine.objects.filter(journal=journal).delete()
        journal.refresh_from_db()
        self.assertEqual(journal.status, JournalEntry.STATUS_POSTED)
        self.assertEqual(journal.description, "قطعی")

    def test_correction_reverses_posted_document_without_mutating_it(self):
        journal = self.service.receive_warehouse_request(lines=self._lines(700), description="انبار", finalize=True)
        correction = self.service.issue_correction(journal, reason="برگشت رسید")
        journal.refresh_from_db()
        self.assertEqual(journal.status, JournalEntry.STATUS_POSTED)
        self.assertEqual(journal.description, "انبار")
        self.assertEqual(correction.corrects_id, journal.pk)
        self.assertEqual(correction.status, JournalEntry.STATUS_POSTED)
        signed = Decimal(0)
        for line in JournalLine.objects.filter(journal__in=[journal, correction]):
            signed += line.debit - line.credit
        self.assertEqual(signed, Decimal(0))
        with self.assertRaises(PostedDocumentError):
            self.service.retire_draft(journal, reason="حذف")
        with self.assertRaises(PostedDocumentError):
            self.service.issue_correction(journal, reason="دوباره")

    def test_draft_is_voided_instead_of_removed(self):
        journal = self.service.issue(lines=self._lines(300), description="پیش‌نویس", finalize=False)
        code = journal.document_code
        self.service.retire_draft(journal, reason="انصراف")
        journal.refresh_from_db()
        self.assertEqual(journal.status, JournalEntry.STATUS_VOID)
        self.assertTrue(JournalEntry.objects.filter(document_code=code).exists())
