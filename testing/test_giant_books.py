from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from logic.accounting_accounts import get_account
from logic.accounting_documents import create_accounting_document
from logic.giant_books import build_books, close_books, push_books
from logic.giant_books.beancount_book import render_beancount, validate_beancount
from logic.giant_books.bridges import erpnext_entries, odoo_moves
from logic.giant_books.frames import lines_frame
from testing.accounting_helpers import seed_accounts
from logic.ledger import OFFICE_LEDGER


class GiantBooksTest(TestCase):
    def setUp(self):
        seed_accounts()
        self.bank = get_account("bank")
        self.revenue = get_account("other_revenue")
        self.expense = get_account("admin_overhead")
        self.receivable = get_account("receivables")
        self.inventory = get_account("raw_materials_inventory")
        self.payable = get_account("accounts_payable")
        self.investment = get_account("investment_projects")
        self.loan = get_account("long_term_loans")

    def _post(self, pairs, description):
        lines = []
        for account, debit, credit in pairs:
            lines.append({
                "account_id": account.id,
                "debit": debit,
                "credit": credit,
                "description": description,
            })
        return create_accounting_document(
            lines=lines,
            description=description,
            is_approved=True,
            entry_date=timezone.make_aware(datetime(2026, 6, 1, 12, 0)),
        )

    def test_statements_balance_and_cash_flow_ties(self):
        self._post([(self.bank, 1000, 0), (self.revenue, 0, 1000)], "فروش نقد")
        self._post([(self.expense, 300, 0), (self.bank, 0, 300)], "هزینه")
        self._post([(self.receivable, 200, 0), (self.revenue, 0, 200)], "فروش نسیه")
        self._post([(self.inventory, 150, 0), (self.payable, 0, 150)], "خرید نسیه")
        self._post([(self.investment, 100, 0), (self.bank, 0, 100)], "سرمایه‌گذاری")
        self._post([(self.bank, 50, 0), (self.loan, 0, 50)], "وام")

        books = build_books(OFFICE_LEDGER)
        self.assertEqual(books["income_statement"]["net_income"], 900)
        self.assertEqual(books["balance_sheet"]["asset_total"], 1100)
        self.assertEqual(books["balance_sheet"]["liability_total"], 200)
        self.assertTrue(books["balance_sheet"]["balanced"])
        self.assertEqual(books["cash_flow"]["net_change"], 650)
        self.assertEqual(books["cash_flow"]["cash_change"], 650)
        self.assertTrue(books["cash_flow"]["reconciled"])
        self.assertTrue(books["hordak"]["balanced"])
        self.assertEqual(books["hordak"]["transaction_count"], 6)
        self.assertTrue(books["beancount"]["valid"], books["beancount"]["errors"])
        self.assertEqual(books["odoo"]["move_count"], 6)
        self.assertEqual(books["ratios"][2]["value"], 0.75)

        frame = lines_frame(OFFICE_LEDGER)
        source = render_beancount(OFFICE_LEDGER, frame)
        self.assertIn("operating_currency", source)
        self.assertIn("1000 IRR", source)
        self.assertTrue(validate_beancount(source)["valid"])
        self.assertEqual(odoo_moves(frame)[0]["move_type"], "entry")
        self.assertEqual(erpnext_entries(frame)[0]["doctype"], "Journal Entry")

    def test_closing_draft_and_external_push_need_config(self):
        self._post([(self.bank, 500, 0), (self.revenue, 0, 500)], "فروش")
        self._post([(self.expense, 200, 0), (self.bank, 0, 200)], "هزینه")
        closed = close_books(OFFICE_LEDGER)
        self.assertEqual(closed["net_income"], 300)
        self.assertTrue(closed["document_code"])
        with self.assertRaises(ValueError):
            push_books(OFFICE_LEDGER, "odoo")
        with self.assertRaises(ValueError):
            push_books(OFFICE_LEDGER, "erpnext")
