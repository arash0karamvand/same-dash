"""تطبیق‌های اجباری و بستن دوره دفتر قانونی واحد."""

from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from time import monotonic

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from backend.models import (
    AccountingPeriod,
    FinancialEvent,
    JournalEntry,
    JournalLine,
    Material,
    MaterialSupplier,
    PurchaseInvoice,
    Sale,
)
from logic.accounting_accounts import get_account
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.inventory_costing import inventory_value
from logic.ledger import LEGAL_LEDGER


def _dates(date_from, date_to):
    start = parse_date(str(date_from or ""))
    end = parse_date(str(date_to or ""))
    if not start or not end or end < start:
        raise ValueError("بازه تاریخ معتبر الزامی است.")
    return start, end


def _journals(start, end):
    start_at = timezone.make_aware(datetime.combine(start, time.min))
    end_at = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min))
    return JournalEntry.objects.filter(
        ledger__code=LEGAL_LEDGER.id,
        entry_date__gte=start_at,
        entry_date__lt=end_at,
    )


def _account_balance(slug, as_of=None):
    account = get_account(slug, ledger=LEGAL_LEDGER)
    lines = JournalLine.objects.filter(
        journal__ledger__code=LEGAL_LEDGER.id,
        journal__status_ref_id=JournalEntry.STATUS_POSTED,
        account__ancestor_paths__ancestor=account,
    )
    if as_of:
        end_at = timezone.make_aware(datetime.combine(as_of + timedelta(days=1), time.min))
        lines = lines.filter(journal__entry_date__lt=end_at)
    totals = lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    return (totals["debit"] or Decimal(0)) - (totals["credit"] or Decimal(0))


SCAN_DOMAINS = {"journal", "event", "inventory", "receivable", "payable"}
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
JOURNAL_SOURCE_LABELS = {
    "sales": "فروش",
    "factory": "کارخانه",
    "warehouse": "انبار",
    "manual": "دستی",
}


def _csv_set(value, allowed=None):
    values = {part.strip() for part in str(value or "").split(",") if part.strip()}
    return values & set(allowed) if allowed else values


def _bool_param(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _scan_params(params):
    start, end = _dates(params.get("date_from"), params.get("date_to"))
    domains = _csv_set(params.get("domains"), SCAN_DOMAINS) or set(SCAN_DOMAINS)
    severities = _csv_set(params.get("severity"), SEVERITY_ORDER)
    kinds = _csv_set(params.get("kinds"))
    try:
        offset = max(0, int(params.get("offset") or 0))
        limit = min(500, max(1, int(params.get("limit") or 50)))
        min_difference = max(0, int(params.get("min_difference") or 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("مقادیر صفحه‌بندی و حداقل اختلاف باید عددی باشند.") from exc
    return {
        "start": start,
        "end": end,
        "domains": domains,
        "severities": severities,
        "kinds": kinds,
        "offset": offset,
        "limit": limit,
        "min_difference": min_difference,
        "blocking_only": _bool_param(params.get("blocking_only")),
        "search": str(params.get("search") or "").strip().casefold(),
        "status": str(params.get("status") or "").strip(),
        "entry_type": str(params.get("entry_type") or "").strip(),
        "source_module": str(params.get("source_module") or "").strip(),
    }


def _issue(
    issue_id,
    domain,
    kind,
    title,
    message,
    *,
    severity="warning",
    blocking=False,
    difference=0,
    debit=None,
    credit=None,
    book=None,
    subledger=None,
    occurred_at=None,
    status="",
    source_module="",
    refs=None,
    details=None,
):
    return {
        "id": issue_id,
        "domain": domain,
        "kind": kind,
        "severity": severity,
        "blocking": bool(blocking),
        "title": title,
        "message": message,
        "difference": int(difference or 0),
        "amounts": {
            "debit": int(debit) if debit is not None else None,
            "credit": int(credit) if credit is not None else None,
            "book": int(book) if book is not None else None,
            "subledger": int(subledger) if subledger is not None else None,
            "difference": int(difference or 0),
        },
        "occurred_at": occurred_at.isoformat() if hasattr(occurred_at, "isoformat") else (occurred_at or ""),
        "status": status or "",
        "source_module": source_module or "",
        "refs": refs or {},
        "details": details or {},
    }


def _journal_source(journal):
    relations = {link.relation_type for link in journal.order_links.all()}
    if "factory_order" in relations:
        return "factory"
    if "sale" in relations or journal.entry_type in {"sale", "receivable", "payment", "refund"}:
        return "sales"
    if journal.entry_type == "manual":
        return "manual"
    return "warehouse"


def _scan_journals(config):
    qs = (
        _journals(config["start"], config["end"])
        .exclude(status_ref_id=JournalEntry.STATUS_VOID)
        .annotate(
            line_debit=Sum("lines__debit"),
            line_credit=Sum("lines__credit"),
            line_count=Count("lines"),
        )
        .prefetch_related("order_links")
        .order_by("-entry_date", "-document_number")
    )
    if config["status"]:
        qs = qs.filter(status_ref_id=config["status"])
    if config["entry_type"]:
        qs = qs.filter(entry_type_ref_id=config["entry_type"])

    issues = []
    for journal in qs.iterator(chunk_size=500):
        debit = Decimal(journal.line_debit or 0)
        credit = Decimal(journal.line_credit or 0)
        source = _journal_source(journal)
        if config["source_module"] and source != config["source_module"]:
            continue
        refs = {
            "journal_id": journal.id,
            "document_code": journal.document_code,
            "document_number": journal.document_number,
        }
        common = {
            "occurred_at": journal.entry_date,
            "status": journal.status,
            "source_module": source,
            "refs": refs,
            "details": {
                "description": journal.description or "",
                "source_label": JOURNAL_SOURCE_LABELS.get(source, source),
                "entry_type": journal.entry_type,
            },
        }
        if journal.line_count == 0:
            issues.append(_issue(
                f"journal:empty:{journal.id}", "journal", "journal_empty_lines",
                "سند بدون آرتیکل", f"سند {journal.document_code} هیچ ردیف حسابداری ندارد.",
                severity="critical", blocking=True, **common,
            ))
        elif debit != credit or debit <= 0:
            issues.append(_issue(
                f"journal:unbalanced:{journal.id}", "journal", "journal_unbalanced",
                "سند نامتوازن", f"جمع بدهکار و بستانکار سند {journal.document_code} برابر نیست.",
                severity="critical", blocking=True, difference=debit - credit,
                debit=debit, credit=credit, **common,
            ))
        if debit != Decimal(journal.debit_total or 0) or credit != Decimal(journal.credit_total or 0):
            issues.append(_issue(
                f"journal:header:{journal.id}", "journal", "journal_header_total_mismatch",
                "مغایرت جمع سند با آرتیکل‌ها",
                f"جمع ذخیره‌شده سند {journal.document_code} با ردیف‌های آن یکسان نیست.",
                severity="critical", blocking=True,
                difference=(Decimal(journal.debit_total or 0) - Decimal(journal.credit_total or 0)),
                debit=debit, credit=credit, **common,
            ))
        if journal.status in {JournalEntry.STATUS_DRAFT, JournalEntry.STATUS_PENDING}:
            label = "پیش‌نویس" if journal.status == JournalEntry.STATUS_DRAFT else "در انتظار بررسی"
            issues.append(_issue(
                f"journal:pending:{journal.id}", "journal", "journal_unresolved",
                f"سند {label}", f"سند {journal.document_code} هنوز تعیین تکلیف نشده است.",
                severity="warning", blocking=True, debit=debit, credit=credit, **common,
            ))

    missing_origin = (
        _journals(config["start"], config["end"])
        .filter(status_ref_id=JournalEntry.STATUS_POSTED, entry_type_ref_id__in=["sale", "payment", "refund"])
        .filter(sources__isnull=True, financial_events__isnull=True)
        .distinct()
    )
    for journal in missing_origin.iterator(chunk_size=500):
        issues.append(_issue(
            f"journal:origin:{journal.id}", "journal", "journal_missing_origin",
            "سند سیستمی بدون مبدأ",
            f"سند {journal.document_code} به فروش، رویداد مالی یا عملیات مبدأ متصل نیست.",
            severity="warning", blocking=True, occurred_at=journal.entry_date,
            status=journal.status, source_module="sales",
            refs={"journal_id": journal.id, "document_code": journal.document_code},
            details={"description": journal.description or ""},
        ))
    return issues


def _scan_events(config):
    start_at = timezone.make_aware(datetime.combine(config["start"], time.min))
    end_at = timezone.make_aware(datetime.combine(config["end"] + timedelta(days=1), time.min))
    qs = FinancialEvent.objects.filter(
        occurred_at__gte=start_at,
        occurred_at__lt=end_at,
    ).select_related("journal")
    if config["source_module"]:
        qs = qs.filter(source_module=config["source_module"])
    if config["status"]:
        qs = qs.filter(status=config["status"])
    issues = []
    for event in qs.iterator(chunk_size=500):
        refs = {
            "financial_event_id": event.id,
            "journal_id": event.journal_id,
            "document_code": event.journal.document_code if event.journal_id else "",
            "source_key": event.source_key,
        }
        common = {
            "occurred_at": event.occurred_at,
            "status": event.status,
            "source_module": event.source_module,
            "refs": refs,
            "details": {
                "source_type": event.source_type,
                "event_type": event.event_type,
                "error": event.error or "",
            },
        }
        if event.status == FinancialEvent.STATUS_FAILED:
            issues.append(_issue(
                f"event:failed:{event.id}", "event", "event_failed",
                "خطا در سندزنی خودکار",
                event.error or f"رویداد {event.source_key} با خطا متوقف شده است.",
                severity="critical", blocking=True, **common,
            ))
        elif event.status == FinancialEvent.STATUS_PENDING:
            issues.append(_issue(
                f"event:pending:{event.id}", "event", "event_pending",
                "رویداد مالی در انتظار",
                f"رویداد {event.source_key} هنوز به سند تبدیل نشده است.",
                severity="warning", blocking=True, **common,
            ))
        if event.status in {FinancialEvent.STATUS_DRAFTED, FinancialEvent.STATUS_POSTED} and not event.journal_id:
            issues.append(_issue(
                f"event:missing-journal:{event.id}", "event", "event_missing_journal",
                "رویداد بدون سند",
                f"رویداد {event.source_key} وضعیت صادرشده دارد اما سندی به آن متصل نیست.",
                severity="critical", blocking=True, **common,
            ))
        if event.journal_id and (
            (event.status == FinancialEvent.STATUS_POSTED and event.journal.status != JournalEntry.STATUS_POSTED)
            or (event.status == FinancialEvent.STATUS_DRAFTED and event.journal.status == JournalEntry.STATUS_POSTED)
        ):
            issues.append(_issue(
                f"event:status:{event.id}", "event", "event_journal_status_mismatch",
                "ناسازگاری وضعیت رویداد و سند",
                f"وضعیت رویداد {event.source_key} با سند متصل به آن هم‌خوان نیست.",
                severity="critical", blocking=True, **common,
            ))

    duplicate_journals = (
        qs.exclude(status=FinancialEvent.STATUS_VOID)
        .exclude(journal__isnull=True)
        .values("journal_id", "journal__document_code")
        .annotate(event_count=Count("id"))
        .filter(event_count__gt=1)
    )
    for row in duplicate_journals:
        issues.append(_issue(
            f"event:duplicate-journal:{row['journal_id']}", "event", "event_multiple_live",
            "چند رویداد فعال برای یک سند",
            f"{row['event_count']} رویداد فعال به سند {row['journal__document_code']} متصل است.",
            severity="critical", blocking=True,
            refs={"journal_id": row["journal_id"], "document_code": row["journal__document_code"]},
            details={"event_count": row["event_count"]},
        ))
    return issues


def _posted_account_balance(slug, as_of):
    account = get_account(slug, ledger=LEGAL_LEDGER)
    end_at = timezone.make_aware(datetime.combine(as_of + timedelta(days=1), time.min))
    totals = JournalLine.objects.filter(
        journal__ledger__code=LEGAL_LEDGER.id,
        journal__status_ref_id=JournalEntry.STATUS_POSTED,
        journal__entry_date__lt=end_at,
        account__ancestor_paths__ancestor=account,
    ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
    return (totals["debit"] or Decimal(0)) - (totals["credit"] or Decimal(0))


def _material_value(material):
    stock = Decimal(material.stock or 0)
    if material.valuation_method == Material.VALUATION_FIFO:
        return sum(
            Decimal(layer.qty_remaining or 0) * Decimal(layer.unit_cost or 0)
            for layer in material.cost_layers.all()
            if Decimal(layer.qty_remaining or 0) > 0
        )
    return stock * Decimal(material.unit_cost or 0)


def _scan_inventory(config):
    materials = list(Material.objects.filter(is_deleted=False).prefetch_related("cost_layers"))
    rows = []
    subledger = Decimal(0)
    for material in materials:
        stock = Decimal(material.stock or 0)
        value = _material_value(material)
        subledger += value
        if stock > 0 and value <= 0:
            rows.append(_issue(
                f"inventory:zero-value:{material.id}", "inventory", "inventory_zero_value",
                "موجودی دارای ارزش صفر",
                f"{material.name} موجودی مثبت دارد اما ارزش حسابداری آن صفر است.",
                severity="warning", blocking=False, subledger=value,
                refs={"material_id": material.id},
                details={"material_name": material.name, "stock": str(stock), "unit": material.unit},
            ))
    book = _posted_account_balance(ACCOUNT_SLUGS.RAW_MATERIALS_INVENTORY, config["end"])
    difference = book - subledger
    if difference:
        rows.insert(0, _issue(
            "inventory:aggregate", "inventory", "inventory_aggregate_mismatch",
            "مغایرت ارزش موجودی با دفتر کل",
            "مانده حساب موجودی مواد با ارزش محاسبه‌شده مواد برابر نیست.",
            severity="warning", blocking=False, difference=difference,
            book=book, subledger=subledger,
            refs={"account_slug": ACCOUNT_SLUGS.RAW_MATERIALS_INVENTORY},
            details={"scope_note": "اختلاف کل قطعی است؛ ردیف‌های مواد، سرنخ بررسی هستند."},
        ))
    control = {
        "key": "inventory",
        "label": "تطبیق موجودی مواد با دفتر کل",
        "ok": difference == 0,
        "book": int(book),
        "subledger": int(subledger),
        "difference": int(difference),
        "blocking": False,
    }
    return rows, control


def _scan_receivables(config):
    end_at = timezone.make_aware(datetime.combine(config["end"] + timedelta(days=1), time.min))
    sales = Sale.objects.filter(
        is_deleted=False,
        sold_at__lt=end_at,
    ).exclude(order_status_ref_id=Sale.ORDER_STATUS_CANCELLED).select_related("customer")
    subledger = sum(
        max(Decimal(0), Decimal(sale.final_amount or 0) - Decimal(sale.paid_amount or 0))
        for sale in sales
    )
    book = _posted_account_balance(ACCOUNT_SLUGS.RECEIVABLES, config["end"])
    difference = book - subledger
    rows = []
    if difference:
        rows.append(_issue(
            "receivable:aggregate", "receivable", "receivable_aggregate_mismatch",
            "مغایرت حساب‌های دریافتنی",
            "مانده دریافتنی دفتر کل با مانده فاکتورهای فروش برابر نیست.",
            severity="warning", blocking=False, difference=difference,
            book=book, subledger=subledger,
            refs={"account_slug": ACCOUNT_SLUGS.RECEIVABLES},
            details={"scope_note": "اختلاف کل قطعی است؛ فاکتورهای بدون سند، سرنخ بررسی هستند."},
        ))
    missing_journal = sales.filter(
        accounting_mode_ref_id=Sale.ACCOUNTING_MODE_AUTOMATIC,
    ).exclude(journal_links__journal__status_ref_id=JournalEntry.STATUS_POSTED).distinct()
    for sale in missing_journal.iterator(chunk_size=500):
        remaining = max(Decimal(0), Decimal(sale.final_amount or 0) - Decimal(sale.paid_amount or 0))
        rows.append(_issue(
            f"receivable:sale:{sale.id}", "receivable", "receivable_sale_missing_journal",
            "فروش خودکار بدون سند قطعی",
            f"فاکتور {sale.invoice_number or sale.id} سند قطعی متصل ندارد.",
            severity="warning", blocking=False, difference=remaining, subledger=remaining,
            occurred_at=sale.sold_at, source_module="sales",
            refs={"sale_id": sale.id, "customer_id": sale.customer_id, "invoice_number": sale.invoice_number or ""},
            details={"customer_name": sale.customer.full_name if sale.customer_id else "بدون مشتری"},
        ))
    control = {
        "key": "receivables",
        "label": "تطبیق حساب دریافتنی با مشتریان",
        "ok": difference == 0,
        "book": int(book),
        "subledger": int(subledger),
        "difference": int(difference),
        "blocking": False,
    }
    return rows, control


def _supplier_book_balances(suppliers, as_of):
    account_ids = [supplier.account_id for supplier in suppliers]
    end_at = timezone.make_aware(datetime.combine(as_of + timedelta(days=1), time.min))
    rows = (
        JournalLine.objects.filter(
            journal__ledger__code=LEGAL_LEDGER.id,
            journal__status_ref_id=JournalEntry.STATUS_POSTED,
            journal__entry_date__lt=end_at,
            account__ancestor_paths__ancestor_id__in=account_ids,
        )
        .values("account__ancestor_paths__ancestor_id")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
    )
    return {
        row["account__ancestor_paths__ancestor_id"]:
            Decimal(row["credit"] or 0) - Decimal(row["debit"] or 0)
        for row in rows
    }


def _scan_payables(config):
    suppliers = list(MaterialSupplier.objects.filter(is_active=True).select_related("account"))
    balances = _supplier_book_balances(suppliers, config["end"])
    invoice_rows = (
        PurchaseInvoice.objects.filter(invoice_date__lte=config["end"])
        .values("supplier_id")
        .annotate(payable=Sum("payable_amount"), settled=Sum("settled_amount"))
    )
    invoice_balances = {
        row["supplier_id"]: Decimal(row["payable"] or 0) - Decimal(row["settled"] or 0)
        for row in invoice_rows
    }
    rows = []
    for supplier in suppliers:
        book = balances.get(supplier.account_id, Decimal(0))
        subledger = invoice_balances.get(supplier.id, Decimal(0))
        difference = book - subledger
        if difference:
            rows.append(_issue(
                f"payable:supplier:{supplier.id}", "payable", "payable_supplier_mismatch",
                "مغایرت مانده تأمین‌کننده",
                f"مانده دفتر و فاکتورهای باز {supplier.name} برابر نیست.",
                severity="warning", blocking=False, difference=difference,
                book=book, subledger=subledger,
                refs={"supplier_id": supplier.id, "account_id": supplier.account_id},
                details={"supplier_name": supplier.name},
            ))
    book_total = _posted_account_balance(ACCOUNT_SLUGS.ACCOUNTS_PAYABLE, config["end"]) * Decimal(-1)
    subledger_total = sum(invoice_balances.values(), Decimal(0))
    difference_total = book_total - subledger_total
    if difference_total:
        rows.insert(0, _issue(
            "payable:aggregate", "payable", "payable_aggregate_mismatch",
            "مغایرت کل حساب‌های پرداختنی",
            "مانده پرداختنی دفتر کل با فاکتورهای خرید برابر نیست.",
            severity="warning", blocking=False, difference=difference_total,
            book=book_total, subledger=subledger_total,
            refs={"account_slug": ACCOUNT_SLUGS.ACCOUNTS_PAYABLE},
        ))
    control = {
        "key": "payables",
        "label": "تطبیق حساب پرداختنی با تأمین‌کنندگان",
        "ok": difference_total == 0,
        "book": int(book_total),
        "subledger": int(subledger_total),
        "difference": int(difference_total),
        "blocking": False,
    }
    return rows, control


def _matches_filters(item, config):
    if config["severities"] and item["severity"] not in config["severities"]:
        return False
    if config["kinds"] and item["kind"] not in config["kinds"]:
        return False
    if config["blocking_only"] and not item["blocking"]:
        return False
    if abs(int(item["difference"] or 0)) < config["min_difference"]:
        return False
    if config["search"]:
        haystack = " ".join([
            item["title"], item["message"], item["status"], item["source_module"],
            " ".join(str(value) for value in item["refs"].values()),
            " ".join(str(value) for value in item["details"].values()),
        ]).casefold()
        if config["search"] not in haystack:
            return False
    return True


def discrepancy_scan(params, *, paginate=True):
    started = monotonic()
    config = _scan_params(params)
    items = []
    controls = []

    if "journal" in config["domains"]:
        items.extend(_scan_journals(config))
    if "event" in config["domains"]:
        items.extend(_scan_events(config))

    posted = _journals(config["start"], config["end"]).filter(status_ref_id=JournalEntry.STATUS_POSTED)
    totals = JournalLine.objects.filter(journal__in=posted).aggregate(debit=Sum("debit"), credit=Sum("credit"))
    debit = Decimal(totals["debit"] or 0)
    credit = Decimal(totals["credit"] or 0)
    controls.append({
        "key": "trial_balance",
        "label": "تراز دفتر در بازه",
        "ok": debit == credit,
        "book": int(debit),
        "subledger": int(credit),
        "difference": int(debit - credit),
        "blocking": True,
    })
    if debit != credit and "journal" in config["domains"]:
        items.append(_issue(
            "journal:trial-balance", "journal", "trial_balance_imbalance",
            "عدم تراز دفتر در بازه",
            "جمع گردش بدهکار و بستانکار اسناد قطعی در بازه برابر نیست.",
            severity="critical", blocking=True, difference=debit - credit,
            debit=debit, credit=credit,
        ))

    if "inventory" in config["domains"]:
        domain_items, control = _scan_inventory(config)
        items.extend(domain_items)
        controls.append(control)
    if "receivable" in config["domains"]:
        domain_items, control = _scan_receivables(config)
        items.extend(domain_items)
        controls.append(control)
    if "payable" in config["domains"]:
        domain_items, control = _scan_payables(config)
        items.extend(domain_items)
        controls.append(control)

    filtered = [item for item in items if _matches_filters(item, config)]
    filtered.sort(key=lambda item: (
        SEVERITY_ORDER.get(item["severity"], 9),
        -abs(int(item["difference"] or 0)),
        item["domain"],
        item["id"],
    ))
    by_domain = Counter(item["domain"] for item in filtered)
    by_severity = Counter(item["severity"] for item in filtered)
    group_map = defaultdict(lambda: {"count": 0, "difference": 0, "critical": 0, "warning": 0, "info": 0})
    for item in filtered:
        group = group_map[item["domain"]]
        group["count"] += 1
        group["difference"] += abs(int(item["difference"] or 0))
        group[item["severity"]] += 1
    groups = [
        {"key": domain, "domain": domain, **values}
        for domain, values in sorted(group_map.items())
    ]
    total = len(filtered)
    page = (
        filtered[config["offset"]:config["offset"] + config["limit"]]
        if paginate
        else filtered
    )
    return {
        "meta": {
            "ledger": LEGAL_LEDGER.id,
            "date_from": config["start"].isoformat(),
            "date_to": config["end"].isoformat(),
            "scanned_at": timezone.now().isoformat(),
            "duration_ms": int((monotonic() - started) * 1000),
        },
        "summary": {
            "issue_count": total,
            "blocking_count": sum(1 for item in filtered if item["blocking"]),
            "by_domain": {domain: by_domain.get(domain, 0) for domain in sorted(SCAN_DOMAINS)},
            "by_severity": {severity: by_severity.get(severity, 0) for severity in SEVERITY_ORDER},
            "debit": int(debit),
            "credit": int(credit),
            "difference": int(debit - credit),
            "balanced": debit == credit,
        },
        "controls": controls,
        "groups": groups,
        "items": page,
        "pagination": {
            "offset": config["offset"],
            "limit": config["limit"],
            "total": total,
            "has_more": config["offset"] + config["limit"] < total,
        },
    }


def reconciliation_report(date_from, date_to):
    start, end = _dates(date_from, date_to)
    start_at = timezone.make_aware(datetime.combine(start, time.min))
    end_at = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min))
    journals = _journals(start, end)
    posted = journals.filter(status_ref_id=JournalEntry.STATUS_POSTED)
    totals = JournalLine.objects.filter(journal__in=posted).aggregate(
        debit=Sum("debit"), credit=Sum("credit")
    )
    debit = totals["debit"] or Decimal(0)
    credit = totals["credit"] or Decimal(0)
    drafts = journals.filter(
        status_ref_id__in=[JournalEntry.STATUS_DRAFT, JournalEntry.STATUS_PENDING]
    ).count()
    failed_events = FinancialEvent.objects.filter(
        occurred_at__gte=start_at,
        occurred_at__lt=end_at,
        status=FinancialEvent.STATUS_FAILED,
    ).count()
    pending_events = FinancialEvent.objects.filter(
        occurred_at__gte=start_at,
        occurred_at__lt=end_at,
        status=FinancialEvent.STATUS_PENDING,
    ).count()
    system_without_origin = (
        posted.filter(entry_type_ref_id__in=["sale", "payment", "refund"])
        .filter(sources__isnull=True, financial_events__isnull=True)
        .distinct()
        .count()
    )
    material_subledger = sum(Decimal(inventory_value(material)) for material in Material.objects.filter(is_deleted=False))
    material_gl = _account_balance(ACCOUNT_SLUGS.RAW_MATERIALS_INVENTORY, end)
    receivable_gl = _account_balance(ACCOUNT_SLUGS.RECEIVABLES, end)
    receivable_subledger = sum(
        Decimal(sale.final_amount or 0) - Decimal(sale.paid_amount or 0)
        for sale in Sale.objects.filter(is_deleted=False, sold_at__lt=end_at).exclude(
            order_status_ref_id=Sale.ORDER_STATUS_CANCELLED
        )
        if Decimal(sale.final_amount or 0) > Decimal(sale.paid_amount or 0)
    )
    payable_gl = -_account_balance(ACCOUNT_SLUGS.ACCOUNTS_PAYABLE, end)
    payable_subledger = sum(
        Decimal(invoice.payable_amount or 0) - Decimal(invoice.settled_amount or 0)
        for invoice in PurchaseInvoice.objects.filter(invoice_date__lte=end)
    )
    controls = [
        {
            "key": "trial_balance",
            "label": "تراز دفتر",
            "ok": debit == credit,
            "book": int(debit),
            "subledger": int(credit),
            "difference": int(debit - credit),
            "blocking": True,
        },
        {
            "key": "drafts",
            "label": "اسناد تعیین‌تکلیف‌نشده",
            "ok": drafts == 0,
            "count": drafts,
            "blocking": True,
        },
        {
            "key": "financial_events",
            "label": "رویدادهای مالی خطادار/در انتظار",
            "ok": failed_events == 0 and pending_events == 0,
            "failed": failed_events,
            "pending": pending_events,
            "blocking": True,
        },
        {
            "key": "origin",
            "label": "اسناد سیستمی بدون مبدأ",
            "ok": system_without_origin == 0,
            "count": system_without_origin,
            "blocking": True,
        },
        {
            "key": "inventory",
            "label": "تطبیق موجودی مواد با دفتر کل",
            "ok": material_gl == material_subledger,
            "book": int(material_gl),
            "subledger": int(material_subledger),
            "difference": int(material_gl - material_subledger),
            "blocking": False,
        },
        {
            "key": "receivables",
            "label": "تطبیق حساب دریافتنی با مشتریان",
            "ok": receivable_gl == receivable_subledger,
            "book": int(receivable_gl),
            "subledger": int(receivable_subledger),
            "difference": int(receivable_gl - receivable_subledger),
            "blocking": False,
        },
        {
            "key": "payables",
            "label": "تطبیق حساب پرداختنی با تأمین‌کنندگان",
            "ok": payable_gl == payable_subledger,
            "book": int(payable_gl),
            "subledger": int(payable_subledger),
            "difference": int(payable_gl - payable_subledger),
            "blocking": False,
        },
    ]
    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "debit": int(debit),
        "credit": int(credit),
        "balanced": debit == credit,
        "controls": controls,
        "can_close": all(item["ok"] for item in controls if item["blocking"]),
    }


@transaction.atomic
def close_period(date_from, date_to, *, user=None, reason=""):
    start, end = _dates(date_from, date_to)
    report = reconciliation_report(start.isoformat(), end.isoformat())
    if not report["can_close"]:
        raise ValueError("کنترل‌های مسدودکننده دوره رفع نشده‌اند.")
    ledger = LEGAL_LEDGER.model
    if AccountingPeriod.objects.filter(
        ledger=ledger,
        status=AccountingPeriod.STATUS_CLOSED,
        date_from__lte=end,
        date_to__gte=start,
    ).exists():
        raise ValueError("این بازه با یک دوره بسته هم‌پوشانی دارد.")
    period = AccountingPeriod.objects.create(
        ledger=ledger,
        date_from=start,
        date_to=end,
        status=AccountingPeriod.STATUS_CLOSED,
        closed_by=user if getattr(user, "is_authenticated", False) else None,
        closed_at=timezone.now(),
        reason=(reason or "").strip(),
    )
    return {"id": period.id, **report, "status": period.status}


@transaction.atomic
def reopen_period(period_id, *, user=None, reason=""):
    period = AccountingPeriod.objects.select_for_update().get(pk=period_id, ledger__code=LEGAL_LEDGER.id)
    text = (reason or "").strip()
    if not text:
        raise ValueError("دلیل بازگشایی دوره الزامی است.")
    period.status = AccountingPeriod.STATUS_REOPENED
    period.closed_by = user if getattr(user, "is_authenticated", False) else None
    period.reason = text
    period.save(update_fields=["status", "closed_by", "reason", "updated_at"])
    return {
        "id": period.id,
        "date_from": period.date_from.isoformat(),
        "date_to": period.date_to.isoformat(),
        "status": period.status,
    }
