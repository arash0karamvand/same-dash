from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from auth import roles
from backend.models import Customer, FinancialEvent, InventoryTransaction, Material, Sale
from logic.accounting_accounts import get_account
from logic.accounting_controls import discrepancy_scan
from logic.accounting_events import register_event
from logic.accounts_payable import create_supplier, post_purchase_invoice
from logic.document_issuance import DocumentIssuanceService
from testing.accounting_helpers import seed_accounts
from testing.role_helpers import ensure_legacy_test_roles


class AccountingDiscrepancyScanTest(TestCase):
    def setUp(self):
        seed_accounts()
        self.today = timezone.localdate()
        self.params = {
            "date_from": (self.today - timedelta(days=1)).isoformat(),
            "date_to": (self.today + timedelta(days=1)).isoformat(),
            "limit": 100,
        }

    def _seed_issues(self):
        service = DocumentIssuanceService()
        bank = get_account("bank")
        revenue = get_account("other_revenue")
        service.issue(
            lines=[
                {"account": bank, "debit": 1000, "credit": 0, "description": "بدهکار"},
                {"account": revenue, "debit": 0, "credit": 1000, "description": "بستانکار"},
            ],
            description="پیش‌نویس نیازمند بررسی",
            finalize=False,
        )

        event, _created = register_event(
            source_module="sales",
            source_type="Sale",
            source="scan-failed-1",
            event_type="finalized",
            payload={"amount": 1200},
        )
        event.status = FinancialEvent.STATUS_FAILED
        event.error = "حساب مبدأ پیدا نشد"
        event.save(update_fields=["status", "error", "updated_at"])

        material = Material.objects.create(
            name="متریال اسکن",
            unit="عدد",
            unit_cost=100,
            approval_status=Material.APPROVAL_APPROVED,
        )
        InventoryTransaction.objects.create(
            material=material,
            quantity=10,
            unit_cost=100,
            reason="initial_stock",
        )

        customer = Customer.objects.create(full_name="مشتری اسکن", phone="09120000991")
        Sale.objects.create(
            customer=customer,
            amount=2500,
            final_amount=2500,
            paid_amount=0,
            invoice_number="SCAN-SALE-1",
            accounting_mode=Sale.ACCOUNTING_MODE_AUTOMATIC,
        )

        supplier_data = create_supplier({"name": "تأمین‌کننده اسکن"})
        post_purchase_invoice({
            "supplier_id": supplier_data["id"],
            "invoice_number": "SCAN-BUY-1",
            "warehouse_receipt": "SCAN-REC-1",
            "invoice_date": self.today.isoformat(),
            "due_date": (self.today + timedelta(days=30)).isoformat(),
            "vat_rate": 0,
            "lines": [{
                "material_id": material.id,
                "quantity": 2,
                "unit_price": 100,
                "trade_discount": 0,
            }],
        })

    def test_scan_finds_all_selected_domains(self):
        self._seed_issues()
        report = discrepancy_scan(self.params)

        domains = {item["domain"] for item in report["items"]}
        self.assertTrue(
            {"journal", "event", "inventory", "receivable", "payable"} <= domains,
            report["items"],
        )
        self.assertGreater(report["summary"]["issue_count"], 0)
        self.assertGreater(report["summary"]["blocking_count"], 0)
        self.assertIn("pagination", report)

    def test_domain_severity_search_and_pagination_filters(self):
        self._seed_issues()
        report = discrepancy_scan({
            **self.params,
            "domains": "event",
            "severity": "critical",
            "search": "حساب مبدأ",
            "limit": 1,
        })

        self.assertEqual(report["pagination"]["total"], 1, report)
        self.assertEqual(len(report["items"]), 1)
        self.assertEqual(report["items"][0]["kind"], "event_failed")
        self.assertEqual(report["summary"]["by_domain"]["event"], 1)

    def test_scan_rejects_invalid_date_range(self):
        with self.assertRaisesMessage(ValueError, "بازه تاریخ معتبر"):
            discrepancy_scan({"date_from": "2026-02-02", "date_to": "2026-02-01"})


class AccountingDiscrepancyScanApiTest(TestCase):
    def setUp(self):
        ensure_legacy_test_roles()
        seed_accounts()
        user = get_user_model().objects.create_user(username="scan-admin", password="secret123")
        roles.assign_role(user, roles.ADMIN)
        self.client = Client()
        self.client.force_login(user)

    def test_scan_requires_valid_dates(self):
        response = self.client.get(
            "/api/accounting/controls/scan/",
            {"date_from": "2026-02-02", "date_to": "2026-02-01"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_scan_and_csv_export_succeed(self):
        params = {"date_from": "2026-02-01", "date_to": "2026-02-02"}
        response = self.client.get("/api/accounting/controls/scan/", params)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertIn("summary", response.json()["data"])

        exported = self.client.get("/api/accounting/controls/scan/export/", params)
        self.assertEqual(exported.status_code, 200)
        self.assertTrue(exported["Content-Type"].startswith("text/csv"))

    def test_export_requires_authentication(self):
        response = Client().get(
            "/api/accounting/controls/scan/export/",
            {"date_from": "2026-02-01", "date_to": "2026-02-02"},
        )
        self.assertEqual(response.status_code, 401)
