"""General ledger calculated from posted or draft journal lines."""

from decimal import Decimal
from django.db.models import Q, Sum

from backend.models import AccountClosure, JournalEntry, JournalLine
from logic.accounting_accounts import account_to_dict
from logic.ledger import OFFICE_LEDGER


def _split(debit, credit):
    net = Decimal(debit or 0) - Decimal(credit or 0)
    return (int(net), 0) if net >= 0 else (0, int(-net))


def ledger_for_accounts(*, date_from=None, date_to=None, account_class=None,
                        approved_only=False, ledger=OFFICE_LEDGER):
    accounts = ledger.accounts().filter(parent__isnull=True, is_active=True)
    if account_class:
        accounts = accounts.filter(account_class=account_class)
    base = JournalLine.objects.filter(journal__ledger__code=ledger.id)
    if approved_only:
        base = base.filter(journal__status_ref_id=JournalEntry.STATUS_POSTED)
    rows = []
    for account in accounts.order_by("sort_order", "name"):
        descendants = AccountClosure.objects.filter(ancestor=account).values("descendant_id")
        lines = base.filter(account_id__in=descendants)
        opening = lines.filter(journal__entry_date__date__lt=date_from) if date_from else lines.none()
        turnover = lines
        if date_from:
            turnover = turnover.filter(journal__entry_date__date__gte=date_from)
        if date_to:
            turnover = turnover.filter(journal__entry_date__date__lte=date_to)
        op = opening.aggregate(d=Sum("debit"), c=Sum("credit"))
        turn = turnover.aggregate(d=Sum("debit"), c=Sum("credit"))
        opening_debit, opening_credit = _split(op["d"], op["c"])
        balance_debit, balance_credit = _split(
            Decimal(op["d"] or 0) + Decimal(turn["d"] or 0),
            Decimal(op["c"] or 0) + Decimal(turn["c"] or 0),
        )
        info = account_to_dict(account)
        rows.append({
            "account_id": account.id, "account_code": account.code,
            "account_name": account.name, "account_class": info["account_class"],
            "account_class_label": info["account_class_label"],
            "opening_debit": opening_debit, "opening_credit": opening_credit,
            "turnover_debit": int(turn["d"] or 0), "turnover_credit": int(turn["c"] or 0),
            "balance_debit": balance_debit, "balance_credit": balance_credit,
        })
    return rows


def ledger_totals(rows):
    keys = ("opening_debit", "opening_credit", "turnover_debit", "turnover_credit",
            "balance_debit", "balance_credit")
    return {key: sum(row.get(key, 0) for row in rows) for key in keys}
