"""Explicit chart fixture for tests only.

Production code never creates accounts from this helper. Runtime account rows
must come from an uploaded workbook or manual chart CRUD.
"""

from backend.models import Account
from logic.catalog_defaults import ACCOUNT_ROLE_BY_CODE
from logic.chart_of_accounts import infer_account_class, infer_normal_balance
from logic.ledger import OFFICE_LEDGER


def seed_accounts(*, ledger=OFFICE_LEDGER):
    ledger_row = ledger.model
    for sort_order, (code, slug) in enumerate(ACCOUNT_ROLE_BY_CODE.items(), 1):
        account_class = infer_account_class(code)
        Account.objects.update_or_create(
            ledger=ledger_row,
            slug=slug,
            defaults={
                "code": code,
                "name": slug,
                "account_class": account_class,
                "normal_balance": infer_normal_balance(account_class),
                "sort_order": sort_order,
                "is_active": True,
                "parent": None,
            },
        )
