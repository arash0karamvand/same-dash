"""ثبت و مدیریت اسناد چندردیفی حسابداری."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Min, Sum
from django.utils import timezone

from logic.accounting import (
    SYSTEM_ENTRY_TYPES,
    assign_document_code,
    delete_accounting_entry,
    entry_permissions,
    generate_document_code,
    is_system_entry,
    next_document_number,
    resolve_entry_accounts,
)
from logic.accounting_accounts import resolve_line_accounts
from logic.accounting_entries import apply_entry_filters, entry_base_queryset, parse_entry_date
from logic.ledger import OFFICE_LEDGER


def _parse_line_money(value, label):
    try:
        amount = Decimal(str(value or 0))
    except (TypeError, ValueError):
        raise ValueError(f"مقدار {label} نامعتبر است.")
    if amount < 0:
        raise ValueError(f"مقدار {label} نمی‌تواند منفی باشد.")
    return amount


def _parse_document_lines(lines, *, default_description=""):
    if not lines:
        raise ValueError("حداقل یک ردیف سند لازم است.")

    parsed_lines = []
    total_debit = Decimal(0)
    total_credit = Decimal(0)

    for index, line in enumerate(lines, start=1):
        debit = _parse_line_money(line.get("debit"), f"بدهکار ردیف {index}")
        credit = _parse_line_money(line.get("credit"), f"بستانکار ردیف {index}")
        if debit <= 0 and credit <= 0:
            raise ValueError(f"ردیف {index}: بدهکار یا بستانکار باید بزرگ‌تر از صفر باشد.")
        if debit > 0 and credit > 0:
            raise ValueError(f"ردیف {index}: فقط یکی از بدهکار یا بستانکار مجاز است.")

        line_desc = (line.get("description") or default_description or "").strip()
        if not line_desc:
            raise ValueError(f"ردیف {index}: شرح الزامی است.")

        parsed_lines.append(
            {
                "id": line.get("id"),
                "account_id": line.get("account_id"),
                "subsidiary_id": line.get("subsidiary_id"),
                "detailed_id": line.get("detailed_id"),
                "debit": debit,
                "credit": credit,
                "description": line_desc,
                "attach_code": (line.get("attach_code") or "").strip(),
            }
        )
        total_debit += debit
        total_credit += credit

    return parsed_lines, total_debit, total_credit


def _document_entries_qs(document_code, *, ledger=OFFICE_LEDGER):
    code = (document_code or "").strip()
    if not code:
        raise ValueError("کد سند الزامی است.")
    return entry_base_queryset(ledger=ledger).filter(document_code=code).order_by("id")


def document_permissions(entries, *, user=None, ledger=OFFICE_LEDGER):
    """مجوزهای سطح سند بر اساس ردیف‌ها."""
    if not entries:
        return {
            "can_edit": False,
            "can_delete": False,
            "can_approve": True,
            "is_transferred": False,
            "has_system_entries": False,
        }

    can_edit = all(entry_permissions(e, user=user, ledger=ledger)["can_edit"] for e in entries)
    can_delete = all(entry_permissions(e, user=user, ledger=ledger)["can_delete"] for e in entries)
    is_transferred = any(getattr(e, "transferred_to_office_at", None) for e in entries)
    has_system = any(is_system_entry(e, ledger=ledger) for e in entries)
    all_approved = all(e.is_approved for e in entries)
    any_approved = any(e.is_approved for e in entries)

    return {
        "can_edit": can_edit and not is_transferred,
        "can_delete": can_delete and not is_transferred,
        "can_approve": not is_transferred,
        "is_transferred": is_transferred,
        "has_system_entries": has_system,
        "is_approved": all_approved,
        "any_approved": any_approved,
    }


def document_to_dict(entries, *, user=None, ledger=OFFICE_LEDGER):
    """سریال‌سازی سند چندردیفی."""
    from api.serializers import accounting_to_dict

    if not entries:
        raise LookupError("سند یافت نشد.")

    first = entries[0]
    perms = document_permissions(entries, user=user, ledger=ledger)
    total_debit = sum(int(e.debit or 0) for e in entries)
    total_credit = sum(int(e.credit or 0) for e in entries)
    transferred_at = next(
        (e.transferred_to_office_at for e in entries if getattr(e, "transferred_to_office_at", None)),
        None,
    )
    office_doc = next(
        (getattr(e, "office_document_code", "") or "" for e in entries if getattr(e, "office_document_code", None)),
        "",
    )

    return {
        "document_code": first.document_code or "",
        "document_number": first.document_number,
        "entry_date": first.entry_date.isoformat(),
        "description": first.description,
        "attach_code": first.attach_code or "",
        "entry_type": first.entry_type,
        "is_approved": perms["is_approved"],
        "line_count": len(entries),
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balanced": total_debit == total_credit,
        "can_edit": perms["can_edit"],
        "can_delete": perms["can_delete"],
        "can_approve": perms["can_approve"],
        "is_transferred": perms["is_transferred"],
        "has_system_entries": perms["has_system_entries"],
        "transferred_to_office_at": transferred_at.isoformat() if transferred_at else None,
        "office_document_code": office_doc,
        "lines": [accounting_to_dict(e, user=user, ledger=ledger) for e in entries],
    }


def list_accounting_documents(params, *, ledger=OFFICE_LEDGER):
    """فهرست اسناد گروه‌بندی‌شده بر اساس document_code."""
    qs = apply_entry_filters(entry_base_queryset(ledger=ledger), params, ledger=ledger)
    qs = qs.exclude(document_code="").exclude(document_code__isnull=True)

    grouped = (
        qs.values("document_code", "document_number")
        .annotate(
            entry_date=Min("entry_date"),
            total_debit=Sum("debit"),
            total_credit=Sum("credit"),
            line_count=Count("id"),
            description=Min("description"),
            is_approved=Min("is_approved"),
            attach_code=Min("attach_code"),
        )
        .order_by("-document_number", "-entry_date")
    )

    try:
        offset = max(0, int(params.get("offset") or 0))
        limit = min(max(1, int(params.get("limit") or 50)), 500)
    except (TypeError, ValueError):
        offset, limit = 0, 50

    all_rows = list(grouped)
    total = len(all_rows)
    page = all_rows[offset : offset + limit]

    EntryModel = ledger.AccountingEntry
    results = []
    for row in page:
        doc_code = row["document_code"]
        if ledger.syncs_sales:
            has_system = EntryModel.objects.filter(
                document_code=doc_code,
                sale_id__isnull=False,
                entry_type__in=SYSTEM_ENTRY_TYPES,
            ).exists()
        else:
            has_system = False
        if ledger.id == "factory":
            transferred_entry = EntryModel.objects.filter(
                document_code=doc_code,
                transferred_to_office_at__isnull=False,
            ).first()
            transferred = transferred_entry.transferred_to_office_at if transferred_entry else None
            office_doc = transferred_entry.office_document_code if transferred_entry else ""
        else:
            transferred = None
            office_doc = ""

        results.append(
            {
                "document_code": doc_code,
                "document_number": row["document_number"],
                "entry_date": row["entry_date"].isoformat() if row["entry_date"] else None,
                "description": row["description"] or "",
                "attach_code": row["attach_code"] or "",
                "total_debit": int(row["total_debit"] or 0),
                "total_credit": int(row["total_credit"] or 0),
                "line_count": row["line_count"],
                "is_approved": bool(row["is_approved"]),
                "balanced": int(row["total_debit"] or 0) == int(row["total_credit"] or 0),
                "is_transferred": transferred is not None,
                "transferred_to_office_at": transferred.isoformat() if transferred else None,
                "office_document_code": office_doc or "",
                "has_system_entries": has_system,
            }
        )

    return {
        "results": results,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def get_accounting_document(document_code, *, user=None, ledger=OFFICE_LEDGER):
    """دریافت یک سند با تمام ردیف‌ها."""
    entries = list(_document_entries_qs(document_code, ledger=ledger))
    if not entries:
        raise LookupError("سند یافت نشد.")
    return document_to_dict(entries, user=user, ledger=ledger)


@transaction.atomic
def create_accounting_document(
    *,
    lines,
    entry_date=None,
    document_code="",
    document_number=None,
    description="",
    is_approved=False,
    entry_type="manual",
    ledger=OFFICE_LEDGER,
):
    """ثبت سند چندردیفی (تراز بودن اختیاری است)."""
    EntryModel = ledger.AccountingEntry
    parsed_lines, total_debit, total_credit = _parse_document_lines(lines, default_description=description)

    for index, line in enumerate(parsed_lines, start=1):
        account, subsidiary, detailed = resolve_line_accounts(
            account_id=line["account_id"],
            subsidiary_id=line["subsidiary_id"],
            detailed_id=line["detailed_id"],
            ledger=ledger,
        )
        parsed_lines[index - 1]["account"] = account
        parsed_lines[index - 1]["subsidiary"] = subsidiary
        parsed_lines[index - 1]["detailed"] = detailed

    when = entry_date or timezone.now()
    doc_number = document_number or next_document_number(entry_date=when, ledger=ledger)
    doc_code = (document_code or "").strip() or generate_document_code(entry_date=when, ledger=ledger)

    created = []
    for line in parsed_lines:
        general, subsidiary_name, detailed_name = resolve_entry_accounts(
            line["account"],
            general=line["account"].get_account_class_display(),
            subsidiary=line["subsidiary"].name if line["subsidiary"] else line["account"].name,
            detailed=line["detailed"].name if line["detailed"] else "",
        )
        amount = line["debit"] or line["credit"]
        entry = EntryModel.objects.create(
            entry_type=entry_type,
            account=line["account"],
            subsidiary=line["subsidiary"],
            detailed=line["detailed"],
            debit=line["debit"],
            credit=line["credit"],
            amount=amount,
            description=line["description"],
            document_code=doc_code,
            document_number=doc_number,
            attach_code=line["attach_code"],
            general_account=general,
            subsidiary_account=subsidiary_name,
            detailed_account=detailed_name,
            is_approved=is_approved,
            entry_date=when,
        )
        created.append(entry)

    if created and not created[0].document_code:
        assign_document_code(created[0], ledger=ledger)
        doc_code = created[0].document_code
        EntryModel.objects.filter(pk__in=[e.pk for e in created]).update(document_code=doc_code)

    return {
        "document_code": doc_code,
        "document_number": doc_number,
        "entries": created,
        "total_debit": int(total_debit),
        "total_credit": int(total_credit),
        "balanced": total_debit == total_credit,
    }


@transaction.atomic
def update_accounting_document(
    document_code,
    *,
    lines,
    entry_date=None,
    document_number=None,
    description="",
    is_approved=None,
    user=None,
    ledger=OFFICE_LEDGER,
):
    """ویرایش سند — فقط اسناد دستی بدون قفل انتقال."""
    existing = list(_document_entries_qs(document_code, ledger=ledger))
    if not existing:
        raise LookupError("سند یافت نشد.")

    perms = document_permissions(existing, user=user, ledger=ledger)
    if not perms["can_edit"]:
        if perms["is_transferred"]:
            raise ValueError("سند منتقل‌شده به اداری قابل ویرایش نیست.")
        if perms["has_system_entries"]:
            raise ValueError("سند سیستمی را فقط می‌توان ردیف‌به‌ردیف ویرایش کرد.")
        raise ValueError("این سند قابل ویرایش نیست.")

    doc_description = (description or existing[0].description or "").strip()
    parsed_lines, total_debit, total_credit = _parse_document_lines(
        lines,
        default_description=doc_description,
    )

    EntryModel = ledger.AccountingEntry
    from logic.accounting_entries import update_entry_from_data

    when = entry_date
    if when is None:
        when = existing[0].entry_date
    elif not hasattr(when, "isoformat"):
        when = parse_entry_date(when)

    doc_number = document_number if document_number is not None else existing[0].document_number
    doc_code = existing[0].document_code
    approved = existing[0].is_approved if is_approved is None else bool(is_approved)

    kept_ids = {int(line["id"]) for line in parsed_lines if line.get("id")}
    for entry in existing:
        if entry.id not in kept_ids:
            delete_accounting_entry(entry, user=user, ledger=ledger)

    updated_entries = []
    for line in parsed_lines:
        account, subsidiary, detailed = resolve_line_accounts(
            account_id=line["account_id"],
            subsidiary_id=line["subsidiary_id"],
            detailed_id=line["detailed_id"],
            ledger=ledger,
        )
        general, subsidiary_name, detailed_name = resolve_entry_accounts(
            account,
            general=account.get_account_class_display(),
            subsidiary=subsidiary.name if subsidiary else account.name,
            detailed=detailed.name if detailed else "",
        )

        entry_id = line.get("id")
        if entry_id:
            entry = EntryModel.objects.get(pk=int(entry_id), document_code=doc_code)
            update_entry_from_data(
                entry,
                {
                    "account_id": account.id,
                    "debit": int(line["debit"]),
                    "credit": int(line["credit"]),
                    "description": line["description"],
                    "entry_date": when.isoformat() if hasattr(when, "isoformat") else when,
                    "general_account": general,
                    "subsidiary_account": subsidiary_name,
                    "detailed_account": detailed_name,
                },
                user=user,
                ledger=ledger,
            )
            entry.subsidiary = subsidiary
            entry.detailed = detailed
            entry.document_number = doc_number
            entry.attach_code = line["attach_code"]
            entry.is_approved = approved
            entry.save(
                update_fields=[
                    "subsidiary",
                    "detailed",
                    "document_number",
                    "attach_code",
                    "is_approved",
                ]
            )
            updated_entries.append(entry)
        else:
            amount = line["debit"] or line["credit"]
            entry = EntryModel.objects.create(
                entry_type=existing[0].entry_type or "manual",
                account=account,
                subsidiary=subsidiary,
                detailed=detailed,
                debit=line["debit"],
                credit=line["credit"],
                amount=amount,
                description=line["description"],
                document_code=doc_code,
                document_number=doc_number,
                attach_code=line["attach_code"],
                general_account=general,
                subsidiary_account=subsidiary_name,
                detailed_account=detailed_name,
                is_approved=approved,
                entry_date=when,
            )
            updated_entries.append(entry)

    refreshed = list(_document_entries_qs(doc_code, ledger=ledger))
    result = document_to_dict(refreshed, user=user, ledger=ledger)
    result["total_debit"] = int(total_debit)
    result["total_credit"] = int(total_credit)
    result["balanced"] = total_debit == total_credit
    return result


@transaction.atomic
def delete_accounting_document(document_code, *, user=None, ledger=OFFICE_LEDGER):
    """حذف تمام ردیف‌های یک سند."""
    entries = list(_document_entries_qs(document_code, ledger=ledger))
    if not entries:
        raise LookupError("سند یافت نشد.")

    perms = document_permissions(entries, user=user, ledger=ledger)
    if not perms["can_delete"]:
        if perms["is_transferred"]:
            raise ValueError("سند منتقل‌شده به اداری قابل حذف نیست.")
        raise ValueError("این سند قابل حذف نیست.")

    deleted_ids = []
    sale_deleted = False
    for entry in entries:
        result = delete_accounting_entry(entry, user=user, ledger=ledger)
        deleted_ids.append(result.get("entry_id"))
        if result.get("sale_deleted"):
            sale_deleted = True

    return {
        "deleted": True,
        "document_code": document_code,
        "entry_ids": deleted_ids,
        "sale_deleted": sale_deleted,
    }


def approve_accounting_document(document_code, *, is_approved, ledger=OFFICE_LEDGER):
    """تایید یا لغو تایید همه ردیف‌های سند."""
    entries = list(_document_entries_qs(document_code, ledger=ledger))
    if not entries:
        raise LookupError("سند یافت نشد.")
    if any(getattr(e, "transferred_to_office_at", None) for e in entries):
        raise ValueError("سند منتقل‌شده قابل تغییر وضعیت تایید نیست.")

    EntryModel = ledger.AccountingEntry
    EntryModel.objects.filter(document_code=document_code.strip()).update(is_approved=bool(is_approved))
    return {"document_code": document_code, "is_approved": bool(is_approved), "line_count": len(entries)}
