from decimal import Decimal

from django.test import TestCase

from backend.models import Account
from logic.chart_of_accounts import (
    ACCOUNT_SLUGS,
    PAYMENT_ACCOUNT_SLUGS,
    POSTING_RULES,
    code_for_slug,
    infer_account_class,
    infer_normal_balance,
    slug_for_code,
    validate_chart_integrity,
)
from logic.posting import build_journal_lines


class ChartOfAccountsTest(TestCase):
    def test_empty_chart_is_valid_before_first_excel_import(self):
        self.assertFalse(Account.objects.exists())
        errors = validate_chart_integrity()
        self.assertEqual(errors, [])

    def test_slug_and_code_lookup(self):
        self.assertEqual(slug_for_code("1210"), ACCOUNT_SLUGS.BANK)
        self.assertIsNone(code_for_slug(ACCOUNT_SLUGS.BANK))
        self.assertTrue(slug_for_code("9999").startswith("excel_"))

    def test_infer_class_and_balance(self):
        self.assertEqual(infer_account_class("1310"), "asset")
        self.assertEqual(infer_account_class("4311"), "liability")
        self.assertEqual(infer_account_class("6320"), "equity")
        self.assertEqual(infer_account_class("7240"), "revenue")
        self.assertEqual(infer_account_class("8211"), "expense")
        self.assertEqual(infer_normal_balance("revenue"), "credit")
        self.assertEqual(infer_normal_balance("asset"), "debit")

    def test_payment_slugs_in_chart(self):
        from testing.accounting_helpers import seed_accounts

        seed_accounts()
        for slug in PAYMENT_ACCOUNT_SLUGS:
            self.assertIsNotNone(code_for_slug(slug))

    def test_posting_rules_reference_valid_slugs(self):
        from testing.accounting_helpers import seed_accounts

        seed_accounts()
        for rule_name, rules in POSTING_RULES.items():
            for rule in rules:
                slug = rule.get("slug")
                if slug:
                    self.assertIsNotNone(code_for_slug(slug), msg=f"{rule_name}: {slug}")


class PostingRulesTest(TestCase):
    def setUp(self):
        from testing.accounting_helpers import seed_accounts

        seed_accounts()

    def test_sale_rule_is_balanced(self):
        from logic.accounting_accounts import payment_account_for_sale
        from backend.models import Sale, Customer

        customer = Customer.objects.create(full_name="Test", phone="09120000001")
        sale = Sale.objects.create(
            customer=customer,
            amount=1000,
            final_amount=1000,
            paid_amount=600,
            payment_method="cash",
        )
        lines = build_journal_lines(
            "sale",
            amounts={"final_amount": 1000, "outstanding": 400, "paid": 600},
            accounts={"payment_account": payment_account_for_sale(sale)},
            description="test",
        )
        debit = sum(line["debit"] for line in lines)
        credit = sum(line["credit"] for line in lines)
        self.assertEqual(debit, credit)
        self.assertEqual(debit, Decimal(1000))

    def test_payment_rule_is_balanced(self):
        from logic.accounting_accounts import get_account

        lines = build_journal_lines(
            "payment",
            amounts={"amount": 500},
            accounts={"payment_account": get_account("bank")},
            description="test",
        )
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["debit"], Decimal(500))
        self.assertEqual(lines[1]["credit"], Decimal(500))
