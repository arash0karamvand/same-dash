"""ثبت و مدیریت اسناد چندردیفی حسابداری."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from backend.models import AccountingEntry

from logic.accounting import assign_document_code, generate_document_code, next_document_number, resolve_entry_accounts
from logic.accounting_accounts import resolve_line_accounts


def _parse_line_money(value, label):
    try:
        amount = Decimal(str(value or 0))
    except (TypeError, ValueError):
        raise ValueError(f"مقدار {label} نامعتبر است.")
    if amount < 0:
        raise ValueError(f"مقدار {label} نمی‌تواند منفی باشد.")
    return amount


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
):
    """ثبت سند چندردیفی (تراز بودن اختیاری است)."""
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

        line_desc = (line.get("description") or description or "").strip()
        if not line_desc:
            raise ValueError(f"ردیف {index}: شرح الزامی است.")

        account, subsidiary, detailed = resolve_line_accounts(
            account_id=line.get("account_id"),
            subsidiary_id=line.get("subsidiary_id"),
            detailed_id=line.get("detailed_id"),
        )
        parsed_lines.append(
            {
                "account": account,
                "subsidiary": subsidiary,
                "detailed": detailed,
                "debit": debit,
                "credit": credit,
                "description": line_desc,
                "attach_code": (line.get("attach_code") or "").strip(),
            }
        )
        total_debit += debit
        total_credit += credit

    when = entry_date or timezone.now()
    doc_number = document_number or next_document_number(entry_date=when)
    doc_code = (document_code or "").strip() or generate_document_code(entry_date=when)

    created = []
    for line in parsed_lines:
        general, subsidiary_name, detailed_name = resolve_entry_accounts(
            line["account"],
            general=line["account"].get_account_class_display(),
            subsidiary=line["subsidiary"].name if line["subsidiary"] else line["account"].name,
            detailed=line["detailed"].name if line["detailed"] else "",
        )
        amount = line["debit"] or line["credit"]
        entry = AccountingEntry.objects.create(
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
        assign_document_code(created[0])
        doc_code = created[0].document_code
        AccountingEntry.objects.filter(pk__in=[e.pk for e in created]).update(document_code=doc_code)

    return {
        "document_code": doc_code,
        "document_number": doc_number,
        "entries": created,
        "total_debit": int(total_debit),
        "total_credit": int(total_credit),
        "balanced": total_debit == total_credit,
    }
