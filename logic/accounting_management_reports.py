"""گزارش‌های مدیریتی لازم از دفتر قانونی و زیرسیستم‌ها."""

from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils.dateparse import parse_date

from backend.models import JournalEntry, JournalLine, PurchaseInvoice, Sale
from logic.accounting_accounts import get_account
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.ledger import LEGAL_LEDGER


def _bucket(days):
    if days <= 0:
        return "current"
    if days <= 30:
        return "1_30"
    if days <= 60:
        return "31_60"
    if days <= 90:
        return "61_90"
    return "over_90"


def receivable_aging(as_of=None):
    day = parse_date(str(as_of or "")) or date.today()
    rows = []
    totals = {key: 0 for key in ("current", "1_30", "31_60", "61_90", "over_90")}
    for sale in Sale.objects.filter(is_deleted=False).select_related("customer"):
        remaining = Decimal(sale.final_amount or 0) - Decimal(sale.paid_amount or 0)
        if remaining <= 0:
            continue
        due = sale.delivery_date or sale.sold_at.date()
        bucket = _bucket((day - due).days)
        totals[bucket] += int(remaining)
        rows.append({
            "sale_id": sale.id,
            "invoice_number": sale.invoice_number or str(sale.id),
            "customer": sale.customer.full_name if sale.customer_id else "",
            "due_date": due.isoformat(),
            "days": (day - due).days,
            "bucket": bucket,
            "amount": int(remaining),
        })
    return {"as_of": day.isoformat(), "totals": totals, "rows": rows}


def payable_aging(as_of=None):
    day = parse_date(str(as_of or "")) or date.today()
    rows = []
    totals = {key: 0 for key in ("current", "1_30", "31_60", "61_90", "over_90")}
    for invoice in PurchaseInvoice.objects.select_related("supplier"):
        remaining = Decimal(invoice.payable_amount or 0) - Decimal(invoice.settled_amount or 0)
        if remaining <= 0:
            continue
        bucket = _bucket((day - invoice.due_date).days)
        totals[bucket] += int(remaining)
        rows.append({
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "supplier": invoice.supplier.name,
            "due_date": invoice.due_date.isoformat(),
            "days": (day - invoice.due_date).days,
            "bucket": bucket,
            "amount": int(remaining),
        })
    return {"as_of": day.isoformat(), "totals": totals, "rows": rows}


def _posted_lines(date_from="", date_to=""):
    qs = JournalLine.objects.filter(
        journal__ledger__code=LEGAL_LEDGER.id,
        journal__status_ref_id=JournalEntry.STATUS_POSTED,
    )
    start = parse_date(str(date_from or ""))
    end = parse_date(str(date_to or ""))
    if start:
        qs = qs.filter(journal__entry_date__date__gte=start)
    if end:
        qs = qs.filter(journal__entry_date__date__lte=end)
    return qs


def vat_report(date_from="", date_to=""):
    lines = _posted_lines(date_from, date_to)
    vat_in = get_account(ACCOUNT_SLUGS.VAT_RECEIVABLE, ledger=LEGAL_LEDGER)
    vat_out = get_account(ACCOUNT_SLUGS.VAT_PAYABLE, ledger=LEGAL_LEDGER)
    purchase = lines.filter(account__ancestor_paths__ancestor=vat_in).aggregate(
        debit=Sum("debit"), credit=Sum("credit")
    )
    sales = lines.filter(account__ancestor_paths__ancestor=vat_out).aggregate(
        debit=Sum("debit"), credit=Sum("credit")
    )
    input_vat = Decimal(purchase["debit"] or 0) - Decimal(purchase["credit"] or 0)
    output_vat = Decimal(sales["credit"] or 0) - Decimal(sales["debit"] or 0)
    return {
        "date_from": date_from or "",
        "date_to": date_to or "",
        "input_vat": int(input_vat),
        "output_vat": int(output_vat),
        "payable": int(max(Decimal(0), output_vat - input_vat)),
        "receivable": int(max(Decimal(0), input_vat - output_vat)),
    }


def journal_report(date_from="", date_to="", limit=1000):
    journals = JournalEntry.objects.filter(
        ledger__code=LEGAL_LEDGER.id,
        status_ref_id=JournalEntry.STATUS_POSTED,
    ).prefetch_related("lines__account").order_by("entry_date", "document_number")
    start = parse_date(str(date_from or ""))
    end = parse_date(str(date_to or ""))
    if start:
        journals = journals.filter(entry_date__date__gte=start)
    if end:
        journals = journals.filter(entry_date__date__lte=end)
    rows = []
    for journal in journals[: int(limit or 1000)]:
        for line in journal.lines.all():
            rows.append({
                "document_code": journal.document_code,
                "date": journal.entry_date.isoformat(),
                "description": line.description or journal.description,
                "account_code": line.account.path,
                "account_name": line.account.name,
                "debit": int(line.debit or 0),
                "credit": int(line.credit or 0),
            })
    return {"rows": rows, "count": len(rows)}
