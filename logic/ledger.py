"""پیکربندی دفتر حسابداری — اداری و کارخانه جدا."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LedgerConfig:
    id: str
    label: str
    Account: type
    SubsidiaryAccount: type
    DetailedAccount: type
    AccountingEntry: type
    document_prefix: str = "S"
    entity_type: str = "AccountingEntry"
    syncs_sales: bool = True


def _office_ledger():
    from backend.models import Account, AccountingEntry, DetailedAccount, SubsidiaryAccount

    return LedgerConfig(
        id="office",
        label="اداری",
        Account=Account,
        SubsidiaryAccount=SubsidiaryAccount,
        DetailedAccount=DetailedAccount,
        AccountingEntry=AccountingEntry,
        document_prefix="S",
        entity_type="AccountingEntry",
        syncs_sales=True,
    )


def _factory_ledger():
    from backend.models import (
        FactoryAccount,
        FactoryAccountingEntry,
        FactoryDetailedAccount,
        FactorySubsidiaryAccount,
    )

    return LedgerConfig(
        id="factory",
        label="کارخانه",
        Account=FactoryAccount,
        SubsidiaryAccount=FactorySubsidiaryAccount,
        DetailedAccount=FactoryDetailedAccount,
        AccountingEntry=FactoryAccountingEntry,
        document_prefix="F",
        entity_type="FactoryAccountingEntry",
        syncs_sales=False,
    )


OFFICE_LEDGER = _office_ledger()
FACTORY_LEDGER = _factory_ledger()
