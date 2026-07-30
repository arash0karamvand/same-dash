"""محاسبه دفتر کل — افتتاحیه، گردش و مانده هر حساب."""

from decimal import Decimal

from django.db.models import Q, Sum

from logic.accounting_accounts import account_to_dict, seed_accounts
from logic.ledger import OFFICE_LEDGER


def _money(value):
    return int(value or 0)


def _split_balance(debit_sum, credit_sum):
    """خالص بدهکار/بستانکار را به دو ستون نمایشی تبدیل می‌کند."""
    net = Decimal(debit_sum or 0) - Decimal(credit_sum or 0)
    if net >= 0:
        return _money(net), 0
    return 0, _money(-net)


def _entry_base_qs(*, approved_only=False, ledger=OFFICE_LEDGER):
    EntryModel = ledger.AccountingEntry
    qs = EntryModel.objects.filter(account__isnull=False)
    if ledger.syncs_sales:
        qs = qs.filter(Q(sale__isnull=True) | Q(sale__is_deleted=False))
    if approved_only:
        qs = qs.filter(is_approved=True)
    return qs


def ledger_for_accounts(*, date_from=None, date_to=None, account_class=None, approved_only=False, ledger=OFFICE_LEDGER):
    """ردیف دفتر کل برای هر حساب فعال."""
    seed_accounts(ledger=ledger)
    AccountModel = ledger.Account

    accounts = AccountModel.objects.filter(is_active=True).order_by("sort_order", "name")
    if account_class:
        accounts = accounts.filter(account_class=account_class)

    base = _entry_base_qs(approved_only=approved_only, ledger=ledger)

    rows = []
    for account in accounts:
        account_entries = base.filter(account_id=account.id)

        opening_qs = account_entries
        if date_from:
            opening_qs = opening_qs.filter(entry_date__date__lt=date_from)

        turnover_qs = account_entries
        if date_from:
            turnover_qs = turnover_qs.filter(entry_date__date__gte=date_from)
        if date_to:
            turnover_qs = turnover_qs.filter(entry_date__date__lte=date_to)

        opening_agg = opening_qs.aggregate(debit=Sum("debit"), credit=Sum("credit"))
        turnover_agg = turnover_qs.aggregate(debit=Sum("debit"), credit=Sum("credit"))

        opening_debit_raw = opening_agg["debit"] or 0
        opening_credit_raw = opening_agg["credit"] or 0
        turnover_debit = _money(turnover_agg["debit"])
        turnover_credit = _money(turnover_agg["credit"])

        opening_debit, opening_credit = _split_balance(opening_debit_raw, opening_credit_raw)

        total_debit_raw = Decimal(opening_debit_raw) + Decimal(turnover_agg["debit"] or 0)
        total_credit_raw = Decimal(opening_credit_raw) + Decimal(turnover_agg["credit"] or 0)
        balance_debit, balance_credit = _split_balance(total_debit_raw, total_credit_raw)

        info = account_to_dict(account)
        rows.append(
            {
                "account_id": account.id,
                "account_code": account.code or str(account.sort_order).zfill(4),
                "account_name": account.name,
                "account_class": info["account_class"],
                "account_class_label": info["account_class_label"],
                "opening_debit": opening_debit,
                "opening_credit": opening_credit,
                "turnover_debit": turnover_debit,
                "turnover_credit": turnover_credit,
                "balance_debit": balance_debit,
                "balance_credit": balance_credit,
            }
        )

    return rows


def ledger_totals(rows):
    keys = (
        "opening_debit",
        "opening_credit",
        "turnover_debit",
        "turnover_credit",
        "balance_debit",
        "balance_credit",
    )
    totals = {key: 0 for key in keys}
    for row in rows:
        for key in keys:
            totals[key] += row.get(key) or 0
    return totals
