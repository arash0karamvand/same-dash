"""Ledger selectors backed by the unified accounting tables."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LedgerConfig:
    id: str
    label: str
    document_prefix: str = "S"
    syncs_sales: bool = True

    @property
    def entity_type(self):
        return "JournalEntry"

    @property
    def model(self):
        from backend.models import Ledger

        return Ledger.objects.get(code=self.id)

    def accounts(self):
        from backend.models import Account

        return Account.objects.filter(ledger__code=self.id)

    def journals(self):
        from backend.models import JournalEntry

        return JournalEntry.objects.filter(ledger__code=self.id)

    def lines(self):
        from backend.models import JournalLine

        return JournalLine.objects.filter(journal__ledger__code=self.id)

    @property
    def Account(self):
        """Legacy model-like adapter; callers should still scope through this ledger."""
        from backend.models import Account

        config = self

        class ScopedAccount:
            objects = config.accounts()

        return ScopedAccount

    @property
    def AccountingEntry(self):
        """Legacy line adapter backed by the unified journal tables."""
        from backend.models import AccountingEntry

        config = self

        class ScopedEntry:
            objects = AccountingEntry.objects.filter(journal__ledger__code=config.id)

        return ScopedEntry


OFFICE_LEDGER = LedgerConfig("office", "اداری", "S", True)
FACTORY_LEDGER = LedgerConfig("factory", "کارخانه", "F", False)
