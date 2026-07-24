"""گزارش‌های حسابداری — تراز کل/معین/تفصیلی و دفتر ریز."""

from decimal import Decimal

from django.db.models import Q, Sum

from backend.models import Account, AccountingEntry, DetailedAccount, SubsidiaryAccount

from logic.accounting_accounts import seed_accounts


def _money(value):
    return int(value or 0)


def _split_balance(debit_sum, credit_sum):
    net = Decimal(debit_sum or 0) - Decimal(credit_sum or 0)
    if net >= 0:
        return _money(net), 0
    return 0, _money(-net)


def _entry_base_qs(*, approved_only=False):
    qs = AccountingEntry.objects.filter(
        Q(sale__isnull=True) | Q(sale__is_deleted=False),
    )
    if approved_only:
        qs = qs.filter(is_approved=True)
    return qs


def _aggregate_period(qs, *, date_from=None, date_to=None):
    opening_qs = qs
    if date_from:
        opening_qs = opening_qs.filter(entry_date__date__lt=date_from)

    turnover_qs = qs
    if date_from:
        turnover_qs = turnover_qs.filter(entry_date__date__gte=date_from)
    if date_to:
        turnover_qs = turnover_qs.filter(entry_date__date__lte=date_to)

    opening_agg = opening_qs.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    turnover_agg = turnover_qs.aggregate(debit=Sum("debit"), credit=Sum("credit"))

    opening_debit_raw = opening_agg["debit"] or 0
    opening_credit_raw = opening_agg["credit"] or 0
    opening_debit, opening_credit = _split_balance(opening_debit_raw, opening_credit_raw)

    turnover_debit = _money(turnover_agg["debit"])
    turnover_credit = _money(turnover_agg["credit"])

    total_debit_raw = Decimal(opening_debit_raw) + Decimal(turnover_agg["debit"] or 0)
    total_credit_raw = Decimal(opening_credit_raw) + Decimal(turnover_agg["credit"] or 0)
    balance_debit, balance_credit = _split_balance(total_debit_raw, total_credit_raw)

    return {
        "opening_debit": opening_debit,
        "opening_credit": opening_credit,
        "turnover_debit": turnover_debit,
        "turnover_credit": turnover_credit,
        "balance_debit": balance_debit,
        "balance_credit": balance_credit,
    }


def _totals_row(rows):
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


def _period_raw_totals(base, *, date_from=None, date_to=None):
    turnover_qs = base
    if date_from:
        turnover_qs = turnover_qs.filter(entry_date__date__gte=date_from)
    if date_to:
        turnover_qs = turnover_qs.filter(entry_date__date__lte=date_to)
    agg = turnover_qs.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    debit = _money(agg["debit"])
    credit = _money(agg["credit"])
    return debit, credit, debit == credit


def _totals_with_balance(rows, base, *, date_from=None, date_to=None):
    totals = _totals_row(rows)
    raw_debit, raw_credit, balanced = _period_raw_totals(base, date_from=date_from, date_to=date_to)
    totals["raw_turnover_debit"] = raw_debit
    totals["raw_turnover_credit"] = raw_credit
    totals["turnover_balanced"] = balanced
    return totals


def _filter_base_by_class(base, account_class):
    if not account_class:
        return base
    return base.filter(account__account_class=account_class)


def trial_balance_general(*, date_from=None, date_to=None, account_class=None, approved_only=False):
    seed_accounts()
    base = _entry_base_qs(approved_only=approved_only)
    if account_class:
        base = base.filter(account__account_class=account_class)

    accounts = Account.objects.filter(is_active=True).order_by("sort_order", "name")
    if account_class:
        accounts = accounts.filter(account_class=account_class)

    rows = []
    for account in accounts:
        amounts = _aggregate_period(base.filter(account_id=account.id), date_from=date_from, date_to=date_to)
        rows.append(
            {
                "account_id": account.id,
                "account_code": account.code or str(account.sort_order).zfill(4),
                "account_name": account.name,
                "account_class": account.account_class,
                "account_class_label": account.get_account_class_display(),
                **amounts,
            }
        )
    return rows, _totals_with_balance(rows, base, date_from=date_from, date_to=date_to)


def trial_balance_subsidiary(*, date_from=None, date_to=None, account_class=None, account_id=None, approved_only=False):
    seed_accounts()
    base = _entry_base_qs(approved_only=approved_only)

    subsidiaries = SubsidiaryAccount.objects.filter(is_active=True).select_related("account").order_by(
        "account__sort_order", "code"
    )
    if account_class:
        subsidiaries = subsidiaries.filter(account__account_class=account_class)
    if account_id:
        subsidiaries = subsidiaries.filter(account_id=account_id)

    rows = []
    for sub in subsidiaries:
        amounts = _aggregate_period(base.filter(subsidiary_id=sub.id), date_from=date_from, date_to=date_to)
        if not account_id and not any(amounts.values()):
            continue
        rows.append(
            {
                "subsidiary_id": sub.id,
                "account_id": sub.account_id,
                "account_code": sub.full_code,
                "account_name": sub.name,
                "account_class": sub.account.account_class,
                "account_class_label": sub.account.get_account_class_display(),
                **amounts,
            }
        )
    sub_base = base.filter(subsidiary__isnull=False)
    if account_class:
        sub_base = sub_base.filter(account__account_class=account_class)
    if account_id:
        sub_base = sub_base.filter(account_id=account_id)
    return rows, _totals_with_balance(rows, sub_base, date_from=date_from, date_to=date_to)


def trial_balance_detailed(*, date_from=None, date_to=None, account_class=None, account_id=None, subsidiary_id=None, approved_only=False):
    seed_accounts()
    base = _entry_base_qs(approved_only=approved_only)

    details = DetailedAccount.objects.filter(is_active=True).select_related(
        "subsidiary", "subsidiary__account"
    ).order_by("subsidiary__account__sort_order", "subsidiary__code", "code")
    if account_class:
        details = details.filter(subsidiary__account__account_class=account_class)
    if account_id:
        details = details.filter(subsidiary__account_id=account_id)
    if subsidiary_id:
        details = details.filter(subsidiary_id=subsidiary_id)

    rows = []
    for detail in details:
        amounts = _aggregate_period(base.filter(detailed_id=detail.id), date_from=date_from, date_to=date_to)
        if not subsidiary_id and not any(amounts.values()):
            continue
        rows.append(
            {
                "detailed_id": detail.id,
                "subsidiary_id": detail.subsidiary_id,
                "account_id": detail.subsidiary.account_id,
                "account_code": detail.full_code,
                "account_name": detail.name,
                "account_class": detail.subsidiary.account.account_class,
                "account_class_label": detail.subsidiary.account.get_account_class_display(),
                **amounts,
            }
        )
    det_base = base.filter(detailed__isnull=False)
    if account_class:
        det_base = det_base.filter(account__account_class=account_class)
    if account_id:
        det_base = det_base.filter(account_id=account_id)
    if subsidiary_id:
        det_base = det_base.filter(subsidiary_id=subsidiary_id)
    return rows, _totals_with_balance(rows, det_base, date_from=date_from, date_to=date_to)


def detail_ledger(
    *,
    detailed_id=None,
    subsidiary_id=None,
    account_id=None,
    date_from=None,
    date_to=None,
    doc_from=None,
    doc_to=None,
    approved_only=False,
):
    """دفتر ریز — مانده جاری برای هر سطر."""
    base = _entry_base_qs(approved_only=approved_only).select_related(
        "account", "subsidiary", "detailed", "detailed__subsidiary", "detailed__subsidiary__account"
    )

    if detailed_id:
        qs = base.filter(detailed_id=detailed_id)
        detail = DetailedAccount.objects.select_related("subsidiary", "subsidiary__account").get(pk=detailed_id)
        header = {
            "general_name": detail.subsidiary.account.name,
            "subsidiary_name": detail.subsidiary.name,
            "detailed_code": detail.full_code,
            "detailed_name": detail.name,
        }
    elif subsidiary_id:
        qs = base.filter(subsidiary_id=subsidiary_id)
        sub = SubsidiaryAccount.objects.select_related("account").get(pk=subsidiary_id)
        header = {
            "general_name": sub.account.name,
            "subsidiary_name": sub.name,
            "detailed_code": sub.full_code,
            "detailed_name": sub.name,
        }
    elif account_id:
        qs = base.filter(account_id=account_id, subsidiary__isnull=True, detailed__isnull=True)
        account = Account.objects.get(pk=account_id)
        header = {
            "general_name": account.name,
            "subsidiary_name": account.name,
            "detailed_code": account.code or str(account.sort_order).zfill(4),
            "detailed_name": account.name,
        }
    else:
        raise ValueError("حساب برای دفتر ریز مشخص نشده است.")

    if date_from:
        qs = qs.filter(entry_date__date__gte=date_from)
    if date_to:
        qs = qs.filter(entry_date__date__lte=date_to)
    if doc_from:
        qs = qs.filter(document_number__gte=doc_from)
    if doc_to:
        qs = qs.filter(document_number__lte=doc_to)

    opening_qs = _entry_base_qs(approved_only=approved_only)
    if detailed_id:
        opening_qs = opening_qs.filter(detailed_id=detailed_id)
    elif subsidiary_id:
        opening_qs = opening_qs.filter(subsidiary_id=subsidiary_id)
    else:
        opening_qs = opening_qs.filter(account_id=account_id, subsidiary__isnull=True, detailed__isnull=True)
    if date_from:
        opening_qs = opening_qs.filter(entry_date__date__lt=date_from)

    opening_agg = opening_qs.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    running = Decimal(opening_agg["debit"] or 0) - Decimal(opening_agg["credit"] or 0)

    lines = []
    if running != 0 and date_from:
        opening_side = "debit" if running >= 0 else "credit"
        lines.append(
            {
                "id": None,
                "entry_date": date_from,
                "document_number": None,
                "document_code": "",
                "attach_code": "",
                "description": "افتتاحیه",
                "debit": _money(running) if running > 0 else 0,
                "credit": _money(-running) if running < 0 else 0,
                "balance": _money(abs(running)),
                "balance_side": opening_side,
                "balance_side_label": "بد" if opening_side == "debit" else "بس",
                "is_opening": True,
            }
        )

    entries = qs.order_by("entry_date", "document_number", "id")
    for entry in entries:
        running += Decimal(entry.debit or 0) - Decimal(entry.credit or 0)
        balance_side = "debit" if running >= 0 else "credit"
        lines.append(
            {
                "id": entry.id,
                "entry_date": entry.entry_date.date().isoformat(),
                "document_number": entry.document_number,
                "document_code": entry.document_code or "",
                "attach_code": entry.attach_code or "",
                "description": entry.description,
                "debit": _money(entry.debit),
                "credit": _money(entry.credit),
                "balance": _money(abs(running)),
                "balance_side": balance_side,
                "balance_side_label": "بد" if balance_side == "debit" else "بس",
                "is_opening": False,
                "entry_type": entry.entry_type,
                "is_approved": entry.is_approved,
            }
        )

    opening_balance = _money(abs(Decimal(opening_agg["debit"] or 0) - Decimal(opening_agg["credit"] or 0)))
    return {"header": header, "lines": lines, "opening_balance": opening_balance}
