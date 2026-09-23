"""قوس انحصاری مبدأ سند: UUID فروش، کارخانه و انبار با کلید خارجی واقعی."""

import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, connection, transaction
from django.test import TestCase

from backend.models import (
    AccountingOrigin,
    Customer,
    InventoryTransaction,
    JournalEntry,
    Material,
    ProductionOrder,
    Sale,
    Transaction,
)
from logic.accounting_accounts import get_account
from logic.document_issuance import DocumentIssuanceService
from logic.ledger import OFFICE_LEDGER
from testing.accounting_helpers import seed_accounts


class AccountingOriginIntegrityTest(TestCase):
    def setUp(self):
        seed_accounts(ledger=OFFICE_LEDGER)
        self.service = DocumentIssuanceService()
        self.bank = get_account("bank")
        self.revenue = get_account("other_revenue")
        self.customer = Customer.objects.create(full_name="مبدأ فروش", phone="09120000881")
        self.user = get_user_model().objects.create_user(username="origin_user", password="secret123")

    def _lines(self, amount=1000):
        return [
            {"account": self.bank, "debit": amount, "credit": 0, "description": "بدهکار"},
            {"account": self.revenue, "debit": 0, "credit": amount, "description": "بستانکار"},
        ]

    def _sale(self):
        return Sale.objects.create(
            customer=self.customer,
            amount=1000,
            final_amount=1000,
            paid_amount=0,
        )

    def _inventory(self):
        material = Material.objects.create(name="چوب مبدأ", unit="متر", unit_cost=10)
        return InventoryTransaction.objects.create(
            material=material,
            quantity=4,
            unit_cost=10,
            reason="receipt",
        )

    def _production_order(self):
        return ProductionOrder.objects.create(
            created_by=self.user,
            delivery_date=date.today(),
            customer_name="کارخانه",
        )

    def test_modules_link_by_real_foreign_key_and_uuid(self):
        sale = self._sale()
        inventory = self._inventory()
        production = self._production_order()
        journal = self.service.issue(
            lines=self._lines(),
            description="سند یکپارچه",
            finalize=True,
            sale=sale,
            inventory_transaction=inventory,
            production_order=production,
        )

        self.assertIsInstance(Transaction.objects.get(pk=journal.pk), Transaction)
        linked = {
            row.origin.module: row.origin
            for row in journal.sources.select_related(
                "origin__sale", "origin__inventory_transaction", "origin__production_order"
            )
        }
        self.assertEqual(linked["sales"].source_uuid, sale.uuid)
        self.assertEqual(linked["sales"].resolve().pk, sale.pk)
        self.assertEqual(linked["warehouse"].source_uuid, inventory.uuid)
        self.assertEqual(linked["warehouse"].inventory_transaction_id, inventory.pk)
        self.assertEqual(linked["factory"].source_uuid, production.uuid)
        self.assertEqual(linked["factory"].resolve().pk, production.pk)
        self.assertEqual(journal.status, JournalEntry.STATUS_POSTED)

    def test_same_sale_can_anchor_sales_and_factory(self):
        sale = self._sale()
        sales_origin = AccountingOrigin.register(sale, module=AccountingOrigin.MODULE_SALES)
        factory_origin = AccountingOrigin.register(sale, module=AccountingOrigin.MODULE_FACTORY)
        self.assertNotEqual(sales_origin.pk, factory_origin.pk)
        self.assertEqual(sales_origin.source_uuid, sale.uuid)
        self.assertEqual(factory_origin.source_uuid, sale.uuid)
        again = AccountingOrigin.register(sale, module=AccountingOrigin.MODULE_SALES)
        self.assertEqual(again.pk, sales_origin.pk)

    def test_several_warehouse_origins_can_coexist(self):
        first = AccountingOrigin.register(self._inventory(), module=AccountingOrigin.MODULE_WAREHOUSE)
        second = AccountingOrigin.register(self._inventory(), module=AccountingOrigin.MODULE_WAREHOUSE)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(
            AccountingOrigin.objects.filter(module=AccountingOrigin.MODULE_WAREHOUSE).count(),
            2,
        )

    def test_duplicate_sales_origin_is_rejected(self):
        sale = self._sale()
        AccountingOrigin.register(sale, module=AccountingOrigin.MODULE_SALES)
        duplicate = AccountingOrigin(module=AccountingOrigin.MODULE_SALES, sale=sale)
        with self.assertRaises(ValidationError):
            duplicate.save()

    def test_database_rejects_mismatched_uuid(self):
        sale = self._sale()
        with self.assertRaises((IntegrityError, OperationalError)):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO backend_accountingorigin
                            (module, source_uuid, sale_id, production_order_id, inventory_transaction_id)
                        VALUES ('sales', %s, %s, NULL, NULL)
                        """,
                        [uuid.uuid4().hex, sale.id],
                    )

    def test_database_rejects_two_targets(self):
        sale = self._sale()
        inventory = self._inventory()
        with self.assertRaises((IntegrityError, OperationalError)):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO backend_accountingorigin
                            (module, source_uuid, sale_id, production_order_id, inventory_transaction_id)
                        VALUES ('sales', %s, %s, NULL, %s)
                        """,
                        [sale.uuid.hex, sale.id, inventory.id],
                    )

    def test_database_rejects_unbalanced_posted_journal(self):
        journal = self.service.issue(lines=self._lines(800), description="پیش‌نویس", finalize=False)
        with self.assertRaises((IntegrityError, OperationalError)):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE backend_journalentry
                        SET status = %s, debit_total = %s, credit_total = %s
                        WHERE id = %s
                        """,
                        ["posted", 10, 4, journal.id],
                    )
