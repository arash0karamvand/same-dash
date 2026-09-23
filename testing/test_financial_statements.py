import json
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import Max
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from auth import roles
from logic.accounting_accounts import create_subsidiary_account, get_account
from logic.accounting_documents import create_accounting_document
from logic.accounting_reports import trial_balance_for_level
from logic.financial_statements import management_statements
from logic.ledger import OFFICE_LEDGER
from testing.accounting_helpers import seed_accounts
from testing.role_helpers import ensure_legacy_test_roles


class FinancialStatementsTest(TestCase):
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

    def _post(self, pairs, description, *, when=None, approved=True):
        lines = []
        for account, debit, credit in pairs:
            depth = account.ancestor_paths.aggregate(value=Max("depth"))["value"] or 0
            row = {"debit": debit, "credit": credit, "description": description}
            if depth >= 2:
                row["detailed_id"] = account.id
            elif depth == 1:
                row["subsidiary_id"] = account.id
            else:
                row["account_id"] = account.id
            lines.append(row)
        return create_accounting_document(
            lines=lines,
            description=description,
            is_approved=approved,
            entry_date=when or timezone.make_aware(datetime(2026, 6, 1, 12, 0)),
        )

    def _sample(self):
        self._post([(self.bank, 1000, 0), (self.revenue, 0, 1000)], "فروش نقد")
        self._post([(self.expense, 300, 0), (self.bank, 0, 300)], "هزینه")
        self._post([(self.receivable, 200, 0), (self.revenue, 0, 200)], "فروش نسیه")
        self._post([(self.inventory, 150, 0), (self.payable, 0, 150)], "خرید نسیه")
        self._post([(self.investment, 100, 0), (self.bank, 0, 100)], "سرمایه‌گذاری")
        self._post([(self.bank, 50, 0), (self.loan, 0, 50)], "وام")

    def test_statements_match_posted_activity(self):
        self._sample()
        payload = management_statements(OFFICE_LEDGER)
        income = payload["income_statement"]
        sheet = payload["balance_sheet"]
        self.assertEqual(income["net_income"], 900)
        self.assertEqual(income["revenue_total"], 1200)
        self.assertEqual(income["expense_total"], 300)
        self.assertEqual(sheet["asset_total"], 1100)
        self.assertEqual(sheet["liability_total"], 200)
        self.assertTrue(sheet["balanced"])
        self.assertEqual(payload["cards"][0]["value"], 900)
        trial = {row["account_id"]: row for row in payload["trial_balance"]["results"]}
        self.assertEqual(trial[self.bank.id]["balance_debit"], 650)
        self.assertTrue(payload["trial_balance"]["totals"]["turnover_balanced"])

    def test_period_split_and_drafts_stay_out(self):
        june = timezone.make_aware(datetime(2026, 6, 15, 10, 0))
        july = timezone.make_aware(datetime(2026, 7, 2, 10, 0))
        self._post([(self.bank, 1000, 0), (self.revenue, 0, 1000)], "خرداد", when=june)
        self._post([(self.expense, 200, 0), (self.bank, 0, 200)], "تیر", when=july)
        self._post(
            [(self.bank, 500, 0), (self.revenue, 0, 500)],
            "پیش‌نویس",
            when=july,
            approved=False,
        )
        july_only = management_statements(
            OFFICE_LEDGER, date_from="2026-07-01", date_to="2026-07-31",
        )
        self.assertEqual(july_only["income_statement"]["net_income"], -200)
        self.assertEqual(july_only["balance_sheet"]["asset_total"], 800)
        self.assertEqual(july_only["balance_sheet"]["net_income"], 800)
        trial = trial_balance_for_level({
            "level": "general",
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
            "approved_only": "true",
        })
        bank = next(row for row in trial["results"] if row["account_id"] == self.bank.id)
        self.assertEqual(bank["opening_debit"], 1000)
        self.assertEqual(bank["turnover_credit"], 200)
        self.assertEqual(bank["balance_debit"], 800)

    def test_child_activity_rolls_into_general_account(self):
        subsidiary = create_subsidiary_account(
            account_id=self.bank.id, code="01", name="بانک ملت",
        )
        self._post([(subsidiary, 400, 0), (self.revenue, 0, 400)], "واریز معین")
        trial = trial_balance_for_level({"level": "general", "approved_only": "true"})
        bank = next(row for row in trial["results"] if row["account_id"] == self.bank.id)
        self.assertEqual(bank["balance_debit"], 400)
        detailed = trial_balance_for_level({
            "level": "subsidiary",
            "account_id": str(self.bank.id),
            "approved_only": "true",
        })
        self.assertEqual(detailed["results"][0]["subsidiary_id"], subsidiary.id)
        self.assertEqual(detailed["results"][0]["balance_debit"], 400)
        sheet = management_statements(OFFICE_LEDGER)["balance_sheet"]
        cash_rows = [
            row
            for section in sheet["sections"] if section["key"] == "assets"
            for group in section["groups"] if group["key"] == "cash"
            for row in group["rows"]
        ]
        self.assertEqual(cash_rows[0]["account_id"], self.bank.id)
        self.assertEqual(cash_rows[0]["balance"], 400)

    def test_query_count_stays_flat_as_documents_grow(self):
        self._post([(self.bank, 10, 0), (self.revenue, 0, 10)], "پایه")
        with CaptureQueriesContext(connection) as before:
            management_statements(OFFICE_LEDGER, date_from="2026-01-01", date_to="2026-12-31")
        for index in range(12):
            self._post([(self.expense, 1, 0), (self.bank, 0, 1)], f"سند {index}")
        with CaptureQueriesContext(connection) as after:
            payload = management_statements(
                OFFICE_LEDGER, date_from="2026-01-01", date_to="2026-12-31",
            )
        self.assertEqual(len(before), len(after))
        self.assertLessEqual(len(after), 3)
        self.assertEqual(payload["income_statement"]["net_income"], 10 - 12)

    def test_dashboard_endpoint_returns_structured_reports(self):
        ensure_legacy_test_roles()
        user = get_user_model().objects.create_user(username="stmt-admin", password="secret123")
        roles.assign_role(user, roles.ADMIN)
        self._sample()
        client = Client()
        client.login(username="stmt-admin", password="secret123")
        response = client.get("/api/accounting/statements/?date_to=2026-12-31")
        body = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["income_statement"]["net_income"], 900)
        self.assertTrue(body["data"]["balance_sheet"]["balanced"])
        self.assertIn("trial_balance", body["data"])
        income = client.get("/api/accounting/statements/income/")
        sheet = client.get("/api/accounting/statements/balance-sheet/")
        trial = client.get("/api/accounting/statements/trial-balance/?level=general")
        self.assertEqual(json.loads(income.content)["data"]["net_income"], 900)
        self.assertTrue(json.loads(sheet.content)["data"]["balanced"])
        self.assertGreater(json.loads(trial.content)["data"]["total"], 0)
        denied = Client().get("/api/accounting/statements/")
        self.assertEqual(denied.status_code, 401)
