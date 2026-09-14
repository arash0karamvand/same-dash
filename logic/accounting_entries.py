"""Legacy row API adapted to JournalLine + JournalEntry."""

from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from backend.models import JournalEntry, JournalLine, Sale
from logic.accounting import create_accounting_entry, entry_permissions
from logic.accounting_accounts import accounts_grouped, resolve_account_for_entry
from logic.ledger import OFFICE_LEDGER

VALID_ENTRY_TYPES = {value for value, _ in JournalEntry.ENTRY_TYPE_CHOICES}


def parse_entry_date(value):
    parsed = parse_datetime(str(value).strip())
    if parsed is None:
        date = parse_date(str(value).strip())
        if date is None:
            raise ValueError("تاریخ سند نامعتبر است.")
        parsed = datetime.combine(date, time.min)
    return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed


def parse_money(value, label):
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"مقدار {label} نامعتبر است.") from exc
    if amount < 0:
        raise ValueError(f"مقدار {label} نمی‌تواند منفی باشد.")
    return amount


def entry_base_queryset(*, ledger=OFFICE_LEDGER):
    return JournalLine.objects.filter(journal__ledger__code=ledger.id).exclude(
        journal__status_ref_id=JournalEntry.STATUS_VOID
    ).select_related(
        "account", "journal", "journal__ledger"
    ).prefetch_related("journal__order_links__order")


def apply_entry_filters(qs, params, *, ledger=OFFICE_LEDGER):
    if value := (params.get("type") or "").strip():
        qs = qs.filter(journal__entry_type_ref_id=value)
    if str(params.get("account_id") or "").isdigit():
        account_id = int(params["account_id"])
        qs = qs.filter(account__ancestor_paths__ancestor_id=account_id)
    if value := (params.get("account_class") or "").strip():
        qs = qs.filter(account__account_class=value)
    approved = (params.get("approved") or "").strip().lower()
    if approved in {"true", "1"}:
        qs = qs.filter(journal__status_ref_id=JournalEntry.STATUS_POSTED)
    elif approved in {"false", "0"}:
        qs = qs.exclude(journal__status_ref_id=JournalEntry.STATUS_POSTED)
    if value := (params.get("date_from") or "").strip():
        qs = qs.filter(journal__entry_date__date__gte=value)
    if value := (params.get("date_to") or "").strip():
        qs = qs.filter(journal__entry_date__date__lte=value)
    if str(params.get("sale_id") or "").isdigit():
        qs = qs.filter(journal__order_links__order_id=int(params["sale_id"]), journal__order_links__relation_type="sale")
    if value := (params.get("search") or "").strip():
        qs = qs.filter(
            Q(description__icontains=value) | Q(journal__description__icontains=value)
            | Q(journal__document_code__icontains=value) | Q(account__name__icontains=value)
        )
    if value := (params.get("document_code") or "").strip():
        qs = qs.filter(journal__document_code=value)
    if str(params.get("document_number") or "").isdigit():
        qs = qs.filter(journal__document_number=int(params["document_number"]))
    for field in ("debit", "credit"):
        for suffix in ("min", "max"):
            raw = params.get(f"{field}_{suffix}")
            if raw not in (None, ""):
                lookup = "gte" if suffix == "min" else "lte"
                qs = qs.filter(**{f"{field}__{lookup}": parse_money(raw, field)})
    return qs.distinct()


def list_entries(params, *, ledger=OFFICE_LEDGER):
    qs = apply_entry_filters(entry_base_queryset(ledger=ledger), params, ledger=ledger)
    agg = qs.aggregate(
        total=Count("journal_id", distinct=True),
        total_debit=Sum("debit"),
        total_credit=Sum("credit"),
    )
    try:
        from logic.pagination import parse_page
        offset, limit = parse_page(params)
    except (TypeError, ValueError):
        offset, limit = 0, 10
    journal_ids = list(
        qs.order_by("-journal__entry_date", "-journal_id")
        .values_list("journal_id", flat=True)
        .distinct()[offset:offset + limit]
    )
    results = [
        qs.filter(journal_id=journal_id).order_by("line_number").first()
        for journal_id in journal_ids
    ]
    return {
        "results": results,
        "total": agg["total"] or 0, "offset": offset, "limit": limit,
        "filtered_debit": int(agg["total_debit"] or 0),
        "filtered_credit": int(agg["total_credit"] or 0),
        "types": [{"value": v, "label": l} for v, l in JournalEntry.ENTRY_TYPE_CHOICES],
        "accounts": accounts_grouped(ledger=ledger),
    }


def get_entry(pk, *, ledger=OFFICE_LEDGER):
    try:
        return entry_base_queryset(ledger=ledger).get(pk=pk)
    except JournalLine.DoesNotExist as exc:
        raise LookupError("Entry not found") from exc


def _sale(sale_id):
    if not sale_id:
        return None
    try:
        return Sale.objects.get(pk=sale_id)
    except Sale.DoesNotExist as exc:
        raise LookupError("Sale not found") from exc


def create_entry_from_data(data, *, user, ledger=OFFICE_LEDGER):
    entry_type = (data.get("entry_type") or "manual").strip()
    if entry_type not in VALID_ENTRY_TYPES:
        raise ValueError("نوع سند نامعتبر است.")
    try:
        account = resolve_account_for_entry(
            account_id=data.get("account_id"), account_slug=(data.get("account_slug") or "").strip() or None,
            entry_type=entry_type, ledger=ledger,
        )
    except Exception as exc:
        raise ValueError("حساب سند نامعتبر است.") from exc
    debit, credit = parse_money(data.get("debit"), "بدهکار"), parse_money(data.get("credit"), "بستانکار")
    amount = parse_money(data.get("amount"), "مبلغ") or debit or credit
    if amount <= 0:
        raise ValueError("مبلغ سند باید بزرگ‌تر از صفر باشد.")
    if not debit and not credit:
        debit = amount if account.normal_balance == "debit" else Decimal(0)
        credit = amount if account.normal_balance == "credit" else Decimal(0)
    description = (data.get("description") or "").strip()
    if not description:
        raise ValueError("شرح سند الزامی است.")
    sale = _sale(data.get("sale_id")) if ledger.syncs_sales else None
    if sale and entry_type == "payment":
        from logic.sales import record_payment
        before = set(entry_base_queryset().values_list("id", flat=True))
        record_payment(sale, amount, description=description, recorded_by=user, account=account)
        entry = entry_base_queryset().exclude(id__in=before).order_by("id").first()
        return entry, {"kind": "payment", "amount_rial": int(amount), "sale": sale}
    entry = create_accounting_entry(
        entry_type=entry_type, account=account, debit=debit, credit=credit, amount=amount,
        description=description, sale=sale, is_approved=bool(data.get("is_approved")),
        document_code=(data.get("document_code") or "").strip(),
        entry_date=parse_entry_date(data["entry_date"]) if data.get("entry_date") else None,
        ledger=ledger,
    )
    return entry, {"kind": "manual", "account": account}


def update_entry_from_data(entry, data, *, user, ledger=OFFICE_LEDGER):
    if entry.journal.status == JournalEntry.STATUS_POSTED:
        raise ValueError("سند ثبت قطعی قابل ویرایش نیست.")
    permissions = entry_permissions(entry, user=user, ledger=ledger)
    if permissions["edit_mode"] == "partial":
        data = {key: value for key, value in data.items() if key in {"description", "entry_date"}}
    if "description" in data:
        entry.description = (data.get("description") or "").strip()
    if "account_id" in data:
        entry.account = resolve_account_for_entry(account_id=data["account_id"], ledger=ledger)
    if "debit" in data:
        entry.debit = parse_money(data["debit"], "بدهکار")
    if "credit" in data:
        entry.credit = parse_money(data["credit"], "بستانکار")
    entry.save()
    counter = entry.journal.lines.exclude(pk=entry.pk).order_by("line_number").first()
    if counter and any(key in data for key in ("debit", "credit")):
        counter.debit = entry.credit
        counter.credit = entry.debit
        counter.save()
    journal = entry.journal
    if data.get("entry_date"):
        journal.entry_date = parse_entry_date(data["entry_date"])
    if "entry_type" in data:
        journal.entry_type = data["entry_type"]
    journal.save()
    totals = journal.lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    if totals["debit"] != totals["credit"]:
        raise ValueError("ویرایش باعث نامتوازن شدن سند می‌شود؛ سند را به صورت کامل ویرایش کنید.")
    return entry, {"kind": "full"}


def set_entry_approval(entry, is_approved):
    from logic.accounting_documents import approve_accounting_document
    approve_accounting_document(entry.document_code, is_approved=is_approved)
    entry.refresh_from_db()
    entry.journal.refresh_from_db()
    return entry


def bulk_approve_entries(ids=None, *, ledger=OFFICE_LEDGER):
    qs = JournalEntry.objects.filter(ledger__code=ledger.id).exclude(
        status_ref_id=JournalEntry.STATUS_POSTED
    )
    if ids:
        qs = qs.filter(lines__id__in=ids).distinct()
    count = 0
    for journal in qs:
        journal.post()
        count += 1
    return count
