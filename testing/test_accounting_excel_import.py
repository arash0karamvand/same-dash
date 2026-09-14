"""تست آپلود اکسل حسابداری."""

from decimal import Decimal
from io import BytesIO

from django.test import TestCase

from backend.models import Account, JournalEntry, JournalLine
from logic.accounting_excel_import import import_excel_file, parse_excel_file


def _trial_header_rows():
    return [
        ["", None, None, None, None, None, None, ""],
        ["از تاريخ :    1405/01/01", None, None, None, None, None, None, "از سند :    1/0"],
        ["تا تاريخ :    1405/04/31", None, None, None, None, None, None, "تا سند :    100/0"],
        ["", None, None, None, None, None, None, ""],
        ["", None, None, None, None, None, None, ""],
        ["کد حساب", "عنوان حساب", "افتتاحیه", None, "گردش", None, "مانده", None],
        [None, None, "بدهکار", "بستانکار", "بدهکار", "بستانکار", "بدهکار", "بستانکار"],
    ]


def _build_sample_workbook(*, balanced=True):
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)

    turnover_debit = 1000
    turnover_credit = 1000 if balanced else 900

    for title, rows in (
        (
            "تراز کل",
            [
                *_trial_header_rows(),
                ["7240", "فروش محصول", 0, 0, turnover_debit, turnover_credit, 0, turnover_credit],
                ["1210", "بانک", 0, 0, turnover_credit, turnover_debit, turnover_credit, 0],
                ["", "جمع", 0, 0, turnover_debit, turnover_credit, turnover_debit, turnover_credit],
            ],
        ),
        (
            "تراز معین",
            [
                *_trial_header_rows(),
                ["7240/1", "فروش", 0, 0, turnover_debit, turnover_credit, 0, turnover_credit],
                ["1210/1", "بانک", 0, 0, turnover_credit, turnover_debit, turnover_credit, 0],
                ["", "جمع", 0, 0, turnover_debit, turnover_credit, turnover_debit, turnover_credit],
            ],
        ),
        (
            "تراز تفصیلی",
            [
                *_trial_header_rows(),
                ["7240/1/1", "فروش", 0, 0, turnover_debit, turnover_credit, 0, turnover_credit],
                ["1210/1/6", "بانک ملی", 0, 0, turnover_credit, turnover_debit, turnover_credit, 0],
                ["", "جمع", 0, 0, turnover_debit, turnover_credit, turnover_debit, turnover_credit],
            ],
        ),
        (
            "ریز نمونه",
            [
                ["عنوان حساب کل :   بانک"],
                ["عنوان حساب معين :   بانک"],
                ["کد حساب تفصيلی :   1210/1/6      -      عنوان حساب تفصيلی :    بانک ملی"],
                [""],
                ["تاريخ", "شماره سند", "ع", "شرح", "بدهکار", "بستانکار", "مانده", "تش"],
                ["1405/01/01", 1, "", "افتتاحیه", 500, "", 500, "بد"],
                ["1405/01/02", 2, "1", "واریز", "", 500, 0, "بس"],
            ],
        ),
    ):
        ws = wb.create_sheet(title)
        for row in rows:
            ws.append(row)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


class AccountingExcelImportTest(TestCase):
    def test_parse_sample_workbook(self):
        parsed = parse_excel_file(_build_sample_workbook())
        self.assertEqual(len(parsed.errors), 0)
        self.assertEqual(len(parsed.general_rows), 2)
        self.assertEqual(len(parsed.subsidiary_rows), 2)
        self.assertEqual(len(parsed.detailed_rows), 2)
        self.assertEqual(len(parsed.detail_ledger_rows), 2)
        self.assertEqual(parsed.detail_ledger_account_code, "1210/1/6")
        self.assertEqual(parsed.metadata.get("date_from"), "1405/01/01")

    def test_dry_run_does_not_persist(self):
        before_accounts = Account.objects.count()
        before_entries = JournalLine.objects.count()
        report = import_excel_file(_build_sample_workbook(), dry_run=True)
        self.assertTrue(report["dry_run"])
        self.assertFalse(report["committed"])
        self.assertEqual(Account.objects.count(), before_accounts)
        self.assertEqual(JournalLine.objects.count(), before_entries)
        self.assertEqual(report["counts"]["general_rows"], 2)

    def test_import_creates_chart_and_entries(self):
        report = import_excel_file(_build_sample_workbook(), dry_run=False, approve=True)
        self.assertTrue(report["committed"])
        subsidiary = Account.objects.get(code="1", parent__code="1210")
        self.assertTrue(Account.objects.filter(code="6", parent=subsidiary).exists())
        self.assertFalse(JournalEntry.objects.filter(document_number__in=[1, 2]).exists())
        self.assertEqual(report["stats"]["entries_created"], 0)
        self.assertEqual(report["stats"]["entries_skipped"], 2)

    def test_unbalanced_workbook_still_commits(self):
        report = import_excel_file(_build_sample_workbook(balanced=False), dry_run=False)
        self.assertTrue(report["committed"])
        self.assertTrue(report["warnings"])
        self.assertTrue(Account.objects.filter(parent__isnull=False).exists())

    def test_unbalanced_workbook_commits_with_force(self):
        report = import_excel_file(
            _build_sample_workbook(balanced=False),
            dry_run=False,
            force=True,
        )
        self.assertTrue(report["committed"])

    def test_duplicate_import_skips_entries(self):
        import_excel_file(_build_sample_workbook(), dry_run=False, force=True)
        second = import_excel_file(_build_sample_workbook(), dry_run=False, force=True)
        self.assertGreater(second["stats"]["entries_skipped"], 0)
