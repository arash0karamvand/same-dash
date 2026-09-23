from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from backend.models import (
    AccountingPeriod,
    Customer,
    FinancialEvent,
    InventoryTransaction,
    JournalEntry,
    Material,
    Product,
    ProductMaterial,
    Sale,
    SaleLineItem,
)
from logic.accounting_accounts import get_account
from logic.accounting_events import (
    FinancialEventConflict,
    finalize_event,
    issue_event_draft,
    register_event,
)
from logic.accounting_event_catalog import validate_event_catalog
from logic.accounts_payable import create_supplier, post_purchase_invoice
from logic.costing import save_wip_close
from logic.ledger import LEGAL_LEDGER
from logic.sales_accounting import finalize_sale_invoice
from testing.accounting_helpers import seed_accounts


class UnifiedAccountingCoreTest(TestCase):
    def setUp(self):
        seed_accounts(ledger=LEGAL_LEDGER)
        self.bank = get_account("bank", ledger=LEGAL_LEDGER)
        self.revenue = get_account("other_revenue", ledger=LEGAL_LEDGER)

    def _lines(self, value=1000):
        return [
            {"account": self.bank, "debit": value, "credit": 0, "description": "بدهکار"},
            {"account": self.revenue, "debit": 0, "credit": value, "description": "بستانکار"},
        ]

    def test_financial_event_catalog_is_complete(self):
        self.assertEqual(validate_event_catalog(), [])

    def test_financial_event_is_idempotent_and_detects_payload_conflict(self):
        event, created = register_event(
            source_module="tests",
            source_type="Order",
            source="42",
            event_type="approved",
            payload={"amount": 1000},
        )
        again, second_created = register_event(
            source_module="tests",
            source_type="Order",
            source="42",
            event_type="approved",
            payload={"amount": 1000},
        )
        self.assertTrue(created)
        self.assertFalse(second_created)
        self.assertEqual(event.pk, again.pk)
        with self.assertRaises(FinancialEventConflict):
            register_event(
                source_module="tests",
                source_type="Order",
                source="42",
                event_type="approved",
                payload={"amount": 2000},
            )

    def test_event_issues_draft_then_posts_only_after_explicit_finalize(self):
        event, _created = register_event(
            source_module="tests",
            source_type="Receipt",
            source="R-1",
            event_type="received",
            payload={"amount": 500},
        )
        journal = issue_event_draft(
            event,
            lines=self._lines(500),
            entry_type="payment",
            description="رسید آزمایشی",
        )
        self.assertEqual(journal.status, JournalEntry.STATUS_DRAFT)
        posted = finalize_event(event)
        posted.refresh_from_db()
        event.refresh_from_db()
        self.assertEqual(posted.status, JournalEntry.STATUS_POSTED)
        self.assertEqual(event.status, FinancialEvent.STATUS_POSTED)

    def test_closed_period_blocks_posting(self):
        event, _created = register_event(
            source_module="tests",
            source_type="Receipt",
            source="R-2",
            event_type="received",
            payload={"amount": 700},
        )
        journal = issue_event_draft(
            event,
            lines=self._lines(700),
            entry_type="payment",
            description="دوره بسته",
        )
        today = timezone.localdate(journal.entry_date)
        AccountingPeriod.objects.create(
            ledger=LEGAL_LEDGER.model,
            date_from=today - timedelta(days=1),
            date_to=today + timedelta(days=1),
            status=AccountingPeriod.STATUS_CLOSED,
        )
        with self.assertRaises(ValidationError):
            finalize_event(event)
        journal.refresh_from_db()
        self.assertEqual(journal.status, JournalEntry.STATUS_DRAFT)

    def test_wip_close_creates_finished_goods_draft(self):
        result = save_wip_close({
            "year": 1405,
            "month": 1,
            "completed_units": 10,
            "ending_wip_units": 2,
            "percent_complete": 50,
            "material_cost": 600,
            "labor_cost": 300,
            "overhead_cost": 100,
        })
        journal = JournalEntry.objects.get(document_code=result["document_code"])
        self.assertEqual(journal.status, JournalEntry.STATUS_DRAFT)
        self.assertEqual(journal.debit_total, Decimal(1000))
        self.assertEqual(journal.credit_total, Decimal(1000))

    def test_final_sale_creates_vat_and_cogs_draft(self):
        customer = Customer.objects.create(full_name="مشتری آزمون", phone="09121112233")
        material = Material.objects.create(
            name="مواد آزمون",
            unit="عدد",
            unit_cost=100,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        InventoryTransaction.objects.create(
            material=material,
            quantity=100,
            unit_cost=100,
            reason="initial_stock",
        )
        product = Product.objects.create(name="محصول آزمون", default_price=1000)
        ProductMaterial.objects.create(product=product, material=material, quantity=2)
        sale = Sale.objects.create(
            customer=customer,
            amount=1000,
            final_amount=1100,
            vat_rate=10,
            vat_amount=100,
            paid_amount=0,
            invoice_number="VAT-1",
        )
        SaleLineItem.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            quantity=3,
            unit_price=1000,
            line_total=3000,
        )
        result = finalize_sale_invoice(sale, user=None)
        journal = JournalEntry.objects.get(pk=result["journal"]["id"])
        self.assertEqual(journal.status, JournalEntry.STATUS_DRAFT)
        by_slug = {
            line.account.slug: (line.debit, line.credit)
            for line in journal.lines.select_related("account")
        }
        self.assertEqual(by_slug["vat_payable"][1], Decimal(100))
        self.assertEqual(by_slug["cogs"][0], Decimal(600))
        self.assertEqual(by_slug["finished_goods_inventory"][1], Decimal(600))

    def test_purchase_payable_posts_to_unified_ledger_as_draft(self):
        supplier = create_supplier({"name": "تأمین‌کننده آزمون", "credit_days": 30})
        material = Material.objects.create(
            name="خرید آزمون",
            unit="عدد",
            unit_cost=0,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        result = post_purchase_invoice({
            "supplier_id": supplier["id"],
            "invoice_number": "P-100",
            "warehouse_receipt": "W-100",
            "invoice_date": timezone.localdate().isoformat(),
            "vat_rate": 10,
            "lines": [{
                "material_id": material.id,
                "quantity": 2,
                "unit_price": 500,
                "trade_discount": 0,
            }],
        })
        journal = JournalEntry.objects.get(document_code=result["document_code"])
        self.assertEqual(journal.ledger.code, LEGAL_LEDGER.id)
        self.assertEqual(journal.status, JournalEntry.STATUS_DRAFT)
        self.assertEqual(journal.debit_total, journal.credit_total)
