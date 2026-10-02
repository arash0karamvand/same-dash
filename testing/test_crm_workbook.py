"""تست خواندن فایل CRM 1405 و اسکیما."""

from pathlib import Path

from django.test import TestCase

from logic.crm_workbook_io import read_xlsx_workbook
from logic.crm_workbook_schema import CRM_SHEETS, schema_payload

CRM_SAMPLE = Path(__file__).resolve().parents[1] / "agents" / "CRM 1405 (2).xlsb"


class CrmWorkbookSchemaTests(TestCase):
    def test_schema_has_eight_tabs(self):
        payload = schema_payload()
        self.assertEqual(len(payload["tabs"]), len(CRM_SHEETS))


class CrmWorkbookImportTests(TestCase):
    def test_read_xlsb_sample(self):
        if not CRM_SAMPLE.is_file():
            self.skipTest("CRM sample file missing")
        from logic.crm_workbook_io import read_xlsb_workbook

        with CRM_SAMPLE.open("rb") as f:
            data = read_xlsb_workbook(f, password="1999")
        self.assertGreater(len(data["customers"]), 10)
        first = data["customers"][0]
        self.assertIn("شماره فاکتور", first)
        self.assertIn("نام مشتری", first)
