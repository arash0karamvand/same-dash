"""Multi-line journal document operations."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Q, Sum

from backend.models import JournalEntry, JournalLine
from logic.accounting import create_journal, entry_permissions, is_system_entry
from logic.accounting_accounts import resolve_line_accounts
from logic.ledger import OFFICE_LEDGER


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
        "is_approved": perms["is_approved"], "line_count": len(entries),
        "total_debit": debit, "total_credit": credit, "balanced": debit == credit,
        **{k: perms[k] for k in ("can_edit", "can_delete", "can_approve", "is_transferred", "has_system_entries")},
        "transferred_to_office_at": transferred.created_at.isoformat() if transferred else None,
        "office_document_code": transferred.document_code if transferred else "",
        "lines": [accounting_to_dict(e, user=user, ledger=ledger) for e in entries],
    }


def list_accounting_documents(params, *, ledger=OFFICE_LEDGER):
    qs = JournalEntry.objects.filter(ledger__code=ledger.id).exclude(
        status_ref_id=JournalEntry.STATUS_VOID
    ).annotate(
        total_debit=Sum("lines__debit"), total_credit=Sum("lines__credit"),
        line_count=Count("lines"),
    ).order_by("-document_number")
    entry_type = (params.get("type") or "").strip()
    if entry_type:
        qs = qs.filter(entry_type_ref_id=entry_type)
    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(Q(description__icontains=search) | Q(document_code__icontains=search))
    rows = list(qs)
    try:
        from logic.pagination import parse_page
        offset, limit = parse_page(params)
    except (TypeError, ValueError):
        offset, limit = 0, 10
    results = []
    for journal in rows[offset:offset + limit]:
        transferred = getattr(journal, "transferred_journal", None)
        results.append({
            "document_code": journal.document_code, "document_number": journal.document_number,
            "entry_date": journal.entry_date.isoformat(), "description": journal.description,
            "attach_code": "", "total_debit": int(journal.total_debit or 0),
            "total_credit": int(journal.total_credit or 0), "line_count": journal.line_count,
            "is_approved": journal.status == JournalEntry.STATUS_POSTED,
            "balanced": journal.total_debit == journal.total_credit,
            "is_transferred": bool(transferred),
            "transferred_to_office_at": transferred.created_at.isoformat() if transferred else None,
            "office_document_code": transferred.document_code if transferred else "",
            "has_system_entries": journal.entry_type in {"sale", "receivable", "payment"},
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
                               description="", is_approved=None, user=None, ledger=OFFICE_LEDGER):
    journal = _journal(document_code, ledger)
    existing = list(journal.lines.all())
    if not document_permissions(existing, user=user, ledger=ledger)["can_edit"]:
        raise ValueError("این سند قابل ویرایش نیست.")
    parsed = _parse_lines(lines, description or journal.description, ledger)
    journal.lines.all().delete()
    journal.entry_date = entry_date or journal.entry_date
    journal.document_number = document_number or journal.document_number
    journal.description = description or journal.description
    journal.save()
    for index, row in enumerate(parsed, 1):
        JournalLine.objects.create(
            journal=journal, account=row["account"], debit=row["debit"],
            credit=row["credit"], description=row["description"], line_number=index,
        )
    if is_approved:
        journal.post()
    return get_accounting_document(document_code, user=user, ledger=ledger)


@transaction.atomic
def delete_accounting_document(document_code, *, user=None, ledger=OFFICE_LEDGER):
    journal = _journal(document_code, ledger)
    entries = list(journal.lines.all())
    if not document_permissions(entries, user=user, ledger=ledger)["can_delete"]:
        raise ValueError("این سند قابل حذف نیست.")
    ids = [e.id for e in entries]
    journal.status = JournalEntry.STATUS_VOID
    journal.posted_at = None
    journal.save(update_fields=["status", "posted_at"])
    return {"deleted": True, "document_code": document_code, "entry_ids": ids, "sale_deleted": False}


def approve_accounting_document(document_code, *, is_approved, ledger=OFFICE_LEDGER):
    journal = _journal(document_code, ledger)
    if is_approved:
        journal.post()
    elif journal.status == JournalEntry.STATUS_POSTED:
        journal.status = JournalEntry.STATUS_DRAFT
        journal.posted_at = None
        journal.save(update_fields=["status", "posted_at"])
    return {"document_code": document_code, "is_approved": bool(is_approved), "line_count": journal.lines.count()}
