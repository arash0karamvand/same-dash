"""Mixin for tests that call record_sale or office-order accounting."""

from logic.ledger import OFFICE_LEDGER
from testing.accounting_helpers import seed_accounts


class OfficeLedgerTestMixin:
    def seed_office_chart(self):
        seed_accounts(ledger=OFFICE_LEDGER)
