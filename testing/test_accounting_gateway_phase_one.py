import json
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase

from backend.models import Account, AccountingSourceReference, PostingAccountMapping, TransactionSource
from logic.accounting_accounts import get_account
from logic.accounting_events import issue_through_gateway
from logic.ledger import LEGAL_LEDGER
from logic.posting import build_journal_lines
from testing.accounting_helpers import seed_accounts


class AccountingGatewayPhaseOneTest(TestCase):
    def setUp(self):
        seed_accounts(ledger=LEGAL_LEDGER)
        self.ledger = LEGAL_LEDGER.model
        self.bank = get_account("bank", ledger=LEGAL_LEDGER)
        self.receivables = get_account("receivables", ledger=LEGAL_LEDGER)
        self.alternative = Account.objects.create(
            ledger=self.ledger,
            slug="mapped-inventory",
            code="M01",
            name="موجودی نگاشت‌شده",
            account_class="asset",
            normal_balance="debit",
        )

    def test_mapping_rejects_non_leaf_and_wrong_ledger_accounts(self):
        child = Account.objects.create(
            ledger=self.ledger,
            parent=self.alternative,
            slug="mapped-inventory-leaf",
            code="01",
            name="برگ موجودی",
            account_class="asset",
            normal_balance="debit",
        )
        mapping = PostingAccountMapping(
            ledger=self.ledger,
            event_key="material_receipt",
            role="raw_materials_inventory",
            side="debit",
            account=self.alternative,
        )
        with self.assertRaises(ValidationError):
            mapping.full_clean()
        mapping.account = child
        mapping.full_clean()

    def test_mapping_takes_precedence_and_missing_mapping_falls_back(self):
        PostingAccountMapping.objects.create(
            ledger=self.ledger,
            event_key="material_receipt",
            role="raw_materials_inventory",
            side="debit",
            account=self.alternative,
            priority=10,
        )
        mapped = build_journal_lines(
            "material_receipt",
            amounts={"value": 100},
            ledger=LEGAL_LEDGER,
        )
        self.assertEqual(mapped[0]["account"], self.alternative)

        fallback = build_journal_lines(
            "material_consumption",
            amounts={"cost": 100},
            ledger=LEGAL_LEDGER,
        )
        self.assertEqual(fallback[1]["account"].slug, "raw_materials_inventory")

    def test_gateway_is_idempotent(self):
        first_event, first_journal, created = issue_through_gateway(
            source_module="tests",
            source_type="receipt",
            source="gateway-1",
            event_type="received",
            rule_name="payment",
            amounts={"amount": 250},
            accounts={"payment_account": self.bank},
            entry_type="payment",
            description="درگاه آزمایشی",
            ledger=LEGAL_LEDGER,
        )
        second_event, second_journal, second_created = issue_through_gateway(
            source_module="tests",
            source_type="receipt",
            source="gateway-1",
            event_type="received",
            rule_name="payment",
            amounts={"amount": 250},
            accounts={"payment_account": self.bank},
            entry_type="payment",
            description="درگاه آزمایشی",
            ledger=LEGAL_LEDGER,
        )
        self.assertTrue(created)
        self.assertFalse(second_created)
        self.assertEqual(first_event.pk, second_event.pk)
        self.assertEqual(first_journal.pk, second_journal.pk)

    def test_gateway_links_extensible_uuid_source(self):
        source_uuid = uuid.uuid4()
        event, journal, _created = issue_through_gateway(
            source_module="procurement",
            source_type="reservation",
            source=str(source_uuid),
            source_uuid=source_uuid,
            event_type="reserved",
            rule_name="payment",
            amounts={"amount": 125},
            accounts={"payment_account": self.bank},
            entry_type="payment",
            description="رزرو آزمایشی",
            ledger=LEGAL_LEDGER,
        )
        reference = AccountingSourceReference.objects.get(
            source_type="reservation",
            source_uuid=source_uuid,
        )
        self.assertEqual(event.source_reference, reference)
        self.assertTrue(
            TransactionSource.objects.filter(
                transaction=journal,
                source_reference=reference,
                origin__isnull=True,
            ).exists()
        )

    def test_mapping_api_permissions_and_coverage(self):
        User = get_user_model()
        plain = User.objects.create_user(username="mapping-plain", password="secret123")
        denied_client = Client()
        denied_client.force_login(plain)
        self.assertEqual(
            denied_client.get("/api/accounting/account-mappings/coverage/").status_code,
            403,
        )

        admin = User.objects.create_superuser(
            username="mapping-admin",
            email="admin@example.test",
            password="secret123",
        )
        client = Client()
        client.force_login(admin)
        coverage = client.get("/api/accounting/account-mappings/coverage/")
        self.assertEqual(coverage.status_code, 200)
        self.assertGreater(coverage.json()["data"]["total"], 0)

        response = client.post(
            "/api/accounting/account-mappings/",
            data=json.dumps(
                {
                    "event_key": "material_receipt",
                    "role": "raw_materials_inventory",
                    "side": "debit",
                    "account_id": self.alternative.id,
                    "priority": 50,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
