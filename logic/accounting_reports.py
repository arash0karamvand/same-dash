"""Accounting reports over hierarchical accounts and journal lines."""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from backend.models import Account, AccountClosure, Customer, JournalEntry, JournalLine, Sale
from logic.accounting_ledger import ledger_for_accounts, ledger_totals
from logic.chart_of_accounts import ACCOUNT_SLUGS, PAYMENT_ACCOUNT_SLUGS
from logic.ledger import OFFICE_LEDGER


def _lines(ledger, approved_only=False):
    qs = JournalLine.objects.filter(journal__ledger__code=ledger.id).exclude(
        journal__status_ref_id=JournalEntry.STATUS_VOID
    )
    return qs.filter(journal__status_ref_id=JournalEntry.STATUS_POSTED) if approved_only else qs


def _day_start(value):
    if not value:
        return None
    if isinstance(value, datetime):
        day = timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    elif hasattr(value, "year"):
        day = value
    else:
        day = parse_date(str(value)[:10])
    if day is None:
        return None
    start = datetime.combine(day, time.min)
    if timezone.is_naive(start):
        start = timezone.make_aware(start)
    return start


def _balance_for(account, base, date_from=None, date_to=None):
    ids = AccountClosure.objects.filter(ancestor=account).values("descendant_id")
    qs = base.filter(account_id__in=ids)
    start = _day_start(date_from)
    end = _day_start(date_to)
    opening = qs.filter(journal__entry_date__lt=start) if start else qs.none()
    turnover = qs
    if start:
        turnover = turnover.filter(journal__entry_date__gte=start)
    if end:
        turnover = turnover.filter(journal__entry_date__lt=end + timedelta(days=1))
    op, turn = opening.aggregate(d=Sum("debit"), c=Sum("credit")), turnover.aggregate(d=Sum("debit"), c=Sum("credit"))
    net_open = Decimal(op["d"] or 0) - Decimal(op["c"] or 0)
    net = net_open + Decimal(turn["d"] or 0) - Decimal(turn["c"] or 0)
    return {
        "opening_debit": int(max(net_open, 0)), "opening_credit": int(max(-net_open, 0)),
        "turnover_debit": int(turn["d"] or 0), "turnover_credit": int(turn["c"] or 0),
        "balance_debit": int(max(net, 0)), "balance_credit": int(max(-net, 0)),
    }


def _trial(depth, *, date_from=None, date_to=None, account_class=None,
           account_id=None, subsidiary_id=None, approved_only=False, ledger=OFFICE_LEDGER):
    accounts = ledger.accounts().filter(is_active=True)
    if depth == 0:
        accounts = accounts.filter(parent__isnull=True)
    elif depth == 1:
        accounts = accounts.filter(parent__isnull=False, parent__parent__isnull=True)
    else:
        accounts = accounts.filter(
            parent__parent__isnull=False, parent__parent__parent__isnull=True
        )
    if account_class:
        accounts = accounts.filter(account_class=account_class)
    if account_id:
        accounts = accounts.filter(ancestor_paths__ancestor_id=account_id)
    if subsidiary_id:
        accounts = accounts.filter(ancestor_paths__ancestor_id=subsidiary_id)
    base = _lines(ledger, approved_only)
    rows = []
    for account in accounts.order_by("sort_order", "code"):
        amounts = _balance_for(account, base, date_from, date_to)
        row = {
            "account_code": account.full_code, "account_name": account.name,
            "account_class": account.account_class,
            "account_class_label": account.get_account_class_display(), **amounts,
        }
        if depth == 0:
            row["account_id"] = account.id
        elif depth == 1:
            row.update(subsidiary_id=account.id, account_id=account.parent_id)
        else:
            row.update(detailed_id=account.id, subsidiary_id=account.parent_id,
                       account_id=account.parent.parent_id)
        rows.append(row)
    totals = ledger_totals(rows)
    turnover = base
    start = _day_start(date_from)
    end = _day_start(date_to)
    if start:
        turnover = turnover.filter(journal__entry_date__gte=start)
    if end:
        turnover = turnover.filter(journal__entry_date__lt=end + timedelta(days=1))
    raw = turnover.aggregate(d=Sum("debit"), c=Sum("credit"))
    totals.update(raw_turnover_debit=int(raw["d"] or 0), raw_turnover_credit=int(raw["c"] or 0),
                  turnover_balanced=(raw["d"] or 0) == (raw["c"] or 0))
    return rows, totals


def trial_balance_general(**kwargs):
    return _trial(0, **kwargs)


def trial_balance_subsidiary(**kwargs):
    return _trial(1, **kwargs)


def trial_balance_detailed(**kwargs):
    return _trial(2, **kwargs)


def report_params_from_dict(params):
    number = lambda key: int(params[key]) if str(params.get(key) or "").isdigit() else None
    return {
        "date_from": (params.get("date_from") or "").strip() or None,
        "date_to": (params.get("date_to") or "").strip() or None,
        "account_class": (params.get("account_class") or "").strip() or None,
        "approved_only": (params.get("approved_only") or "").strip().lower() in {"true", "1"},
        "account_id": number("account_id"), "subsidiary_id": number("subsidiary_id"),
    }


def trial_balance_for_level(params, *, ledger=OFFICE_LEDGER):
    level = (params.get("level") or "general").strip()
    common = report_params_from_dict(params)
    account_id, subsidiary_id = common.pop("account_id"), common.pop("subsidiary_id")
    if level == "subsidiary":
        rows, totals = trial_balance_subsidiary(**common, account_id=account_id, ledger=ledger)
    elif level == "detailed":
        rows, totals = trial_balance_detailed(**common, account_id=account_id,
                                              subsidiary_id=subsidiary_id, ledger=ledger)
    else:
        rows, totals = trial_balance_general(**common, ledger=ledger)
    return {"level": level, "results": rows, "totals": totals, "total": len(rows)}


def detail_ledger_from_params(params, *, user=None, ledger=OFFICE_LEDGER):
    selected = next((int(params[k]) for k in ("detailed_id", "subsidiary_id", "account_id")
                     if str(params.get(k) or "").isdigit()), None)
    if not selected:
        raise ValueError("حساب تفصیلی، معین یا کل را انتخاب کنید.")
    account = ledger.accounts().get(pk=selected)
    base = _lines(ledger, (params.get("approved_only") or "").lower() in {"true", "1"})
    ids = AccountClosure.objects.filter(ancestor=account).values("descendant_id")
    qs = base.filter(account_id__in=ids).select_related("journal", "account")
    date_from, date_to = params.get("date_from"), params.get("date_to")
    opening = qs.filter(journal__entry_date__date__lt=date_from) if date_from else qs.none()
    op = opening.aggregate(d=Sum("debit"), c=Sum("credit"))
    running = Decimal(op["d"] or 0) - Decimal(op["c"] or 0)
    if date_from:
        qs = qs.filter(journal__entry_date__date__gte=date_from)
    if date_to:
        qs = qs.filter(journal__entry_date__date__lte=date_to)
    lines = []
    from logic.accounting import entry_permissions
    for line in qs.order_by("journal__entry_date", "journal__document_number", "line_number"):
        running += line.debit - line.credit
        perms = entry_permissions(line, user=user, ledger=ledger)
        lines.append({
            "id": line.id, "entry_date": line.entry_date.date().isoformat(),
            "document_number": line.document_number, "document_code": line.document_code,
            "attach_code": "", "description": line.description,
            "debit": int(line.debit), "credit": int(line.credit),
            "balance": int(abs(running)), "balance_side": "debit" if running >= 0 else "credit",
            "balance_side_label": "بد" if running >= 0 else "بس", "is_opening": False,
            "entry_type": line.entry_type, "is_approved": line.is_approved,
            "can_edit": perms["can_edit"], "can_delete": perms["can_delete"],
            "account_id": line.account_id, "subsidiary_id": None, "detailed_id": None,
            "transferred_to_office_at": line.transferred_to_office_at.isoformat() if line.transferred_to_office_at else None,
            "office_document_code": line.office_document_code,
        })
    return {"header": {"general_name": account.name, "subsidiary_name": account.name,
                       "detailed_code": account.full_code, "detailed_name": account.name},
            "lines": lines, "opening_balance": int(abs(running))}


def accounting_summary(params, *, ledger=OFFICE_LEDGER):
    from logic.accounting_entries import apply_entry_filters
    qs = apply_entry_filters(_lines(ledger), params, ledger=ledger)
    agg = qs.aggregate(total_debit=Sum("debit"), total_credit=Sum("credit"), count=Count("id"))
    journals = JournalEntry.objects.filter(ledger__code=ledger.id)
    due = Sale.objects.filter(final_amount__gt=F("paid_amount")).aggregate(
        total=Sum(F("final_amount") - F("paid_amount")), count=Count("id")
    ) if ledger.syncs_sales else {"total": 0, "count": 0}
    return {
        "total_debit": int(agg["total_debit"] or 0), "total_credit": int(agg["total_credit"] or 0),
        "total_amount": int((agg["total_debit"] or 0) + (agg["total_credit"] or 0)),
        "total_receivables": int(qs.filter(account__slug=ACCOUNT_SLUGS.RECEIVABLES).aggregate(v=Sum("debit"))["v"] or 0),
        "total_payments": int(qs.filter(account__slug__in=PAYMENT_ACCOUNT_SLUGS).aggregate(v=Sum("debit"))["v"] or 0),
        "total_refunds": int(qs.filter(journal__entry_type_ref_id="refund").aggregate(v=Sum("debit"))["v"] or 0),
        "total_balance_due": int(due["total"] or 0), "open_invoices_count": due["count"] or 0,
        "entry_count": agg["count"] or 0,
        "approved_count": journals.filter(status_ref_id=JournalEntry.STATUS_POSTED).count(),
        "pending_count": journals.filter(status_ref_id=JournalEntry.STATUS_DRAFT).count(),
    }


def sales_report_data(params):
    qs = Sale.objects.select_related("customer")
    if params.get("payment_status"):
        qs = qs.filter(payment_status_ref_id=params["payment_status"])
    agg = qs.aggregate(count=Count("id"), total_amount=Sum("amount"),
                       total_discount=Sum("discount"), total_final=Sum("final_amount"))
    return {"count": agg["count"] or 0, "total_amount": int(agg["total_amount"] or 0),
            "total_discount": int(agg["total_discount"] or 0), "total_final": int(agg["total_final"] or 0),
            "sales": list(qs[:100])}


def customer_accounting_data(customer_id):
    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist as exc:
        raise LookupError("Customer not found") from exc
    sales = Sale.objects.filter(customer=customer)
    entries = JournalLine.objects.filter(journal__order_links__order__in=sales).distinct()
    agg = sales.aggregate(total=Sum("final_amount"), count=Count("id"), paid=Sum("paid_amount"))
    return {"customer_id": customer.id, "customer_name": customer.full_name,
            "sales_count": agg["count"] or 0, "sales_total": int(agg["total"] or 0),
            "paid_total": int(agg["paid"] or 0),
            "balance_due": int((agg["total"] or 0) - (agg["paid"] or 0)),
            "accounting_entries_count": entries.count(),
            "accounting_total": int(entries.aggregate(v=Sum("debit"))["v"] or 0),
            "sales": list(sales), "entries": list(entries)}


def profit_center_report():
    from backend.models import Branch

    rows = []
    branches = Branch.objects.filter(is_profit_center=True).order_by("sort_order", "label")
    for branch in branches:
        journals = JournalEntry.objects.filter(status_ref_id=JournalEntry.STATUS_POSTED).filter(
            Q(branch=branch)
            | Q(
                branch__isnull=True,
                order_links__relation_type="sale",
                order_links__order__branch=branch,
            )
        ).distinct()
        lines = JournalLine.objects.filter(journal__in=journals)
        revenue = lines.filter(account__account_class="revenue").aggregate(d=Sum("debit"), c=Sum("credit"))
        expense = lines.filter(account__account_class="expense").aggregate(d=Sum("debit"), c=Sum("credit"))
        revenue_net = int(Decimal(revenue["c"] or 0) - Decimal(revenue["d"] or 0))
        expense_net = int(Decimal(expense["d"] or 0) - Decimal(expense["c"] or 0))
        rows.append({
            "branch": branch.code,
            "label": branch.label,
            "revenue": revenue_net,
            "expense": expense_net,
            "profit": revenue_net - expense_net,
        })
    return {"results": rows}
