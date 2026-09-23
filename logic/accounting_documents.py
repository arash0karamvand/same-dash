"""Multi-line journal document operations."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from backend.models import JournalEntry, JournalLine, JournalRevision
from logic.accounting import create_journal, entry_permissions, is_system_entry
from logic.accounting_accounts import resolve_line_accounts
from logic.ledger import OFFICE_LEDGER

STATUS_LABELS = {
    JournalEntry.STATUS_DRAFT: "پیش‌نویس",
    JournalEntry.STATUS_PENDING: "در انتظار بررسی",
    JournalEntry.STATUS_POSTED: "ثبت قطعی",
    JournalEntry.STATUS_VOID: "باطل",
}


def _money(value, label):
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"مقدار {label} نامعتبر است.") from exc
    if amount < 0:
        raise ValueError(f"مقدار {label} نمی‌تواند منفی باشد.")
    return amount


def _parse_lines(lines, description, ledger):
    if not isinstance(lines, list) or len(lines) < 2:
        raise ValueError("سند حسابداری باید حداقل دو ردیف داشته باشد.")
    result = []
    for index, row in enumerate(lines, 1):
        debit, credit = _money(row.get("debit"), "بدهکار"), _money(row.get("credit"), "بستانکار")
        if (debit > 0) == (credit > 0):
            raise ValueError(f"ردیف {index}: دقیقاً یکی از بدهکار یا بستانکار باید مثبت باشد.")
        account, subsidiary, detailed = resolve_line_accounts(
            account_id=row.get("account_id"), subsidiary_id=row.get("subsidiary_id"),
            detailed_id=row.get("detailed_id"), ledger=ledger,
        )
        result.append({
            "id": row.get("id"), "account": account, "subsidiary": subsidiary,
            "detailed": detailed, "debit": debit, "credit": credit,
            "description": (row.get("description") or description or "").strip(),
            "attach_code": (row.get("attach_code") or "").strip(),
        })
    if sum(r["debit"] for r in result) != sum(r["credit"] for r in result):
        raise ValueError("جمع بدهکار و بستانکار سند باید برابر باشد.")
    return result


def _journal(code, ledger):
    try:
        return JournalEntry.objects.prefetch_related(
            "lines__account__ancestor_paths__ancestor", "order_links__order"
        ).exclude(status_ref_id=JournalEntry.STATUS_VOID).get(
            ledger__code=ledger.id, document_code=(code or "").strip()
        )
    except JournalEntry.DoesNotExist as exc:
        raise LookupError("سند یافت نشد.") from exc


def _line_snapshot(lines):
    rows = []
    for line in lines:
        rows.append({
            "account_id": line.account_id,
            "debit": int(line.debit or 0),
            "credit": int(line.credit or 0),
            "description": line.description or "",
        })
    return rows


def _parsed_snapshot(parsed):
    return [
        {
            "account_id": row["account"].id,
            "debit": int(row["debit"] or 0),
            "credit": int(row["credit"] or 0),
            "description": row["description"] or "",
        }
        for row in parsed
    ]


def _record_revision(journal, action, *, user=None, reason="", before=None, after=None):
    JournalRevision.objects.create(
        journal=journal,
        actor=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        reason=(reason or "").strip(),
        before_lines=before or [],
        after_lines=after or [],
    )


def document_status_payload(journal):
    status = journal.status
    return {
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "is_overridden": bool(journal.overridden_at),
        "override_reason": journal.override_reason or "",
        "is_approved": status == JournalEntry.STATUS_POSTED,
    }


def document_permissions(entries, *, user=None, ledger=OFFICE_LEDGER):
    journal = entries[0].journal if entries else None
    transferred = bool(journal and getattr(journal, "transferred_journal", None))
    system = any(is_system_entry(line, ledger=ledger) for line in entries)
    can_edit = bool(entries) and all(entry_permissions(e, user=user, ledger=ledger)["can_edit"] for e in entries)
    can_delete = bool(entries) and all(entry_permissions(e, user=user, ledger=ledger)["can_delete"] for e in entries)
    return {
        "can_edit": can_edit, "can_delete": can_delete, "can_approve": not transferred,
        "is_transferred": transferred, "has_system_entries": system,
        "is_approved": bool(journal and journal.status == JournalEntry.STATUS_POSTED),
        "any_approved": bool(journal and journal.status == JournalEntry.STATUS_POSTED),
    }


def document_to_dict(entries, *, user=None, ledger=OFFICE_LEDGER):
    from api.serializers import accounting_to_dict
    if not entries:
        raise LookupError("سند یافت نشد.")
    journal = entries[0].journal
    perms = document_permissions(entries, user=user, ledger=ledger)
    debit = sum(int(e.debit) for e in entries)
    credit = sum(int(e.credit) for e in entries)
    transferred = getattr(journal, "transferred_journal", None)
    return {
        "document_code": journal.document_code, "document_number": journal.document_number,
        "entry_date": journal.entry_date.isoformat(), "description": journal.description,
        "attach_code": "", "entry_type": journal.entry_type,
        "source_module": source_of(journal)[0],
        "source_label": source_of(journal)[1],
        "is_approved": perms["is_approved"], "line_count": len(entries),
        **document_status_payload(journal),
        "total_debit": debit, "total_credit": credit, "balanced": debit == credit,
        **{k: perms[k] for k in ("can_edit", "can_delete", "can_approve", "is_transferred", "has_system_entries")},
        "transferred_to_office_at": transferred.created_at.isoformat() if transferred else None,
        "office_document_code": transferred.document_code if transferred else "",
        "lines": [accounting_to_dict(e, user=user, ledger=ledger) for e in entries],
    }


SALES_ENTRY_TYPES = {"sale", "receivable", "payment", "refund"}
SOURCE_LABELS = {
    "sales": "فروش",
    "warehouse": "انبار",
    "factory": "کارخانه",
    "manual": "دستی",
}


def source_of(journal):
    relations = {link.relation_type for link in journal.order_links.all()}
    if "factory_order" in relations:
        module = "factory"
    elif "sale" in relations or journal.entry_type in SALES_ENTRY_TYPES:
        module = "sales"
    elif journal.entry_type == "manual":
        module = "manual"
    else:
        module = "warehouse"
    return module, SOURCE_LABELS[module]


def list_accounting_documents(params, *, ledger=OFFICE_LEDGER):
    from logic.accounting_reports import _day_start
    from datetime import timedelta

    qs = JournalEntry.objects.filter(ledger__code=ledger.id).exclude(
        status_ref_id=JournalEntry.STATUS_VOID
    ).annotate(
        total_debit=Sum("lines__debit"), total_credit=Sum("lines__credit"),
        line_count=Count("lines"),
    ).prefetch_related("order_links").order_by("-document_number")
    entry_type = (params.get("type") or "").strip()
    if entry_type:
        qs = qs.filter(entry_type_ref_id=entry_type)
    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(Q(description__icontains=search) | Q(document_code__icontains=search))
    status = (params.get("status") or "").strip()
    if status == "overridden":
        qs = qs.exclude(overridden_at=None).exclude(status_ref_id=JournalEntry.STATUS_POSTED)
    elif status in {
        JournalEntry.STATUS_DRAFT,
        JournalEntry.STATUS_PENDING,
        JournalEntry.STATUS_POSTED,
    }:
        qs = qs.filter(status_ref_id=status)
    approved = (params.get("approved") or "").strip().lower()
    if approved in {"true", "1"}:
        qs = qs.filter(status_ref_id=JournalEntry.STATUS_POSTED)
    elif approved in {"false", "0"}:
        qs = qs.exclude(status_ref_id=JournalEntry.STATUS_POSTED)
    number = str(params.get("document_number") or "").strip()
    if number.isdigit():
        qs = qs.filter(document_number=int(number))
    start = _day_start(params.get("date_from"))
    end = _day_start(params.get("date_to"))
    if start:
        qs = qs.filter(entry_date__gte=start)
    if end:
        qs = qs.filter(entry_date__lt=end + timedelta(days=1))
    source = (params.get("source_module") or "").strip()
    if source == "automatic":
        qs = qs.exclude(entry_type_ref_id="manual")
    elif source == "sales":
        qs = qs.filter(
            Q(entry_type_ref_id__in=SALES_ENTRY_TYPES) | Q(order_links__relation_type="sale")
        ).distinct()
    elif source == "factory":
        qs = qs.filter(order_links__relation_type="factory_order").distinct()
    elif source == "manual":
        qs = qs.filter(entry_type_ref_id="manual")
    elif source == "warehouse":
        qs = qs.exclude(entry_type_ref_id__in=[*SALES_ENTRY_TYPES, "manual"]).exclude(
            order_links__relation_type="factory_order"
        )
    rows = list(qs)
    try:
        from logic.pagination import parse_page
        offset, limit = parse_page(params)
    except (TypeError, ValueError):
        offset, limit = 0, 10
    results = []
    for journal in rows[offset:offset + limit]:
        transferred = getattr(journal, "transferred_journal", None)
        source_module, source_label = source_of(journal)
        results.append({
            "document_code": journal.document_code, "document_number": journal.document_number,
            "entry_date": journal.entry_date.isoformat(), "description": journal.description,
            "attach_code": "", "total_debit": int(journal.total_debit or 0),
            "total_credit": int(journal.total_credit or 0), "line_count": journal.line_count,
            "is_approved": journal.status == JournalEntry.STATUS_POSTED,
            **document_status_payload(journal),
            "balanced": journal.total_debit == journal.total_credit,
            "is_transferred": bool(transferred),
            "transferred_to_office_at": transferred.created_at.isoformat() if transferred else None,
            "office_document_code": transferred.document_code if transferred else "",
            "has_system_entries": journal.entry_type in SALES_ENTRY_TYPES,
            "source_module": source_module,
            "source_label": source_label,
        })
    return {"results": results, "total": len(rows), "offset": offset, "limit": limit}


def get_accounting_document(document_code, *, user=None, ledger=OFFICE_LEDGER):
    journal = _journal(document_code, ledger)
    return document_to_dict(list(journal.lines.all()), user=user, ledger=ledger)


@transaction.atomic
def create_accounting_document(*, lines, entry_date=None, document_code="", document_number=None,
                               description="", is_approved=False, entry_type="manual",
                               ledger=OFFICE_LEDGER, user=None, sale=None, factory_order=None,
                               transfer_source=None):
    parsed = _parse_lines(lines, description, ledger)
    journal = create_journal(
        lines=parsed, entry_type=entry_type, description=description,
        entry_date=entry_date, is_approved=is_approved, ledger=ledger,
        document_code=document_code, document_number=document_number, user=user,
        sale=sale, factory_order=factory_order, transfer_source=transfer_source,
    )
    return {
        "document_code": journal.document_code, "document_number": journal.document_number,
        "journal": journal, "entries": list(journal.lines.all()),
        "total_debit": int(sum(r["debit"] for r in parsed)),
        "total_credit": int(sum(r["credit"] for r in parsed)), "balanced": True,
    }


@transaction.atomic
def update_accounting_document(document_code, *, lines, entry_date=None, document_number=None,
                               description="", is_approved=None, user=None, ledger=OFFICE_LEDGER,
                               override_reason=""):
    journal = _journal(document_code, ledger)
    existing = list(journal.lines.all())
    if not document_permissions(existing, user=user, ledger=ledger)["can_edit"]:
        raise ValueError("این سند قابل ویرایش نیست.")
    parsed = _parse_lines(lines, description or journal.description, ledger)
    before = _line_snapshot(existing)
    after = _parsed_snapshot(parsed)
    lines_changed = before != after
    reason = (override_reason or "").strip()
    if journal.status == JournalEntry.STATUS_PENDING and lines_changed and not reason:
        raise ValueError("برای ویرایش سند در انتظار بررسی، دلیل الزامی است.")
    journal.lines.all().delete()
    journal.entry_date = entry_date or journal.entry_date
    journal.document_number = document_number or journal.document_number
    journal.description = description or journal.description
    update_fields = ["entry_date", "document_number", "description"]
    if journal.status == JournalEntry.STATUS_PENDING and lines_changed:
        journal.override_reason = reason
        journal.overridden_at = timezone.now()
        update_fields.extend(["override_reason", "overridden_at"])
    journal.save(update_fields=update_fields)
    for index, row in enumerate(parsed, 1):
        JournalLine.objects.create(
            journal=journal, account=row["account"], debit=row["debit"],
            credit=row["credit"], description=row["description"], line_number=index,
        )
    if journal.status == JournalEntry.STATUS_PENDING and lines_changed:
        _record_revision(
            journal, JournalRevision.ACTION_OVERRIDE, user=user, reason=reason,
            before=before, after=after,
        )
    if is_approved:
        _record_revision(
            journal, JournalRevision.ACTION_POST, user=user, reason=reason,
            before=after, after=after,
        )
        journal.post()
    return get_accounting_document(document_code, user=user, ledger=ledger)


@transaction.atomic
def delete_accounting_document(document_code, *, user=None, ledger=OFFICE_LEDGER):
    journal = _journal(document_code, ledger)
    entries = list(journal.lines.all())
    if not document_permissions(entries, user=user, ledger=ledger)["can_delete"]:
        raise ValueError("این سند قابل حذف نیست.")
    ids = [e.id for e in entries]
    before = _line_snapshot(entries)
    _record_revision(journal, JournalRevision.ACTION_VOID, user=user, before=before, after=[])
    journal.status = JournalEntry.STATUS_VOID
    journal.posted_at = None
    journal.save(update_fields=["status", "posted_at"])
    return {"deleted": True, "document_code": document_code, "entry_ids": ids, "sale_deleted": False}


def submit_accounting_document(document_code, *, user=None, ledger=OFFICE_LEDGER):
    journal = _journal(document_code, ledger)
    if journal.status != JournalEntry.STATUS_DRAFT:
        raise ValueError("فقط پیش‌نویس قابل ارسال برای بررسی است.")
    snapshot = _line_snapshot(journal.lines.all())
    journal.status = JournalEntry.STATUS_PENDING
    journal.save(update_fields=["status"])
    _record_revision(
        journal, JournalRevision.ACTION_SUBMIT, user=user, before=snapshot, after=snapshot,
    )
    return get_accounting_document(document_code, user=user, ledger=ledger)


def approve_accounting_document(document_code, *, is_approved, ledger=OFFICE_LEDGER, user=None):
    journal = _journal(document_code, ledger)
    snapshot = _line_snapshot(journal.lines.all())
    if is_approved:
        if journal.status != JournalEntry.STATUS_POSTED:
            _record_revision(
                journal, JournalRevision.ACTION_POST, user=user, before=snapshot, after=snapshot,
            )
        journal.post()
        from backend.models import FinancialEvent

        FinancialEvent.objects.filter(journal=journal).update(
            status=FinancialEvent.STATUS_POSTED,
            error="",
        )
    elif journal.status == JournalEntry.STATUS_POSTED:
        raise ValueError("سند قطعی قابل برگشت به پیش‌نویس نیست؛ سند اصلاحی صادر کنید.")
    else:
        from backend.models import FinancialEvent
        from logic.document_issuance import DocumentIssuanceService

        DocumentIssuanceService().retire_draft(
            journal,
            user=user,
            reason="رد سند توسط حسابدار",
        )
        FinancialEvent.objects.filter(journal=journal).update(
            status=FinancialEvent.STATUS_VOID,
        )
    payload = {"document_code": document_code, "is_approved": bool(is_approved), "line_count": journal.lines.count()}
    payload.update(document_status_payload(journal))
    return payload
