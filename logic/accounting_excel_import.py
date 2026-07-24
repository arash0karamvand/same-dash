"""آپلود و پردازش فایل‌های اکسل حسابداری (تراز کل/معین/تفصیلی + ریز)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.db import transaction
from django.utils import timezone

from backend.models import Account, AccountingEntry, DetailedAccount, SubsidiaryAccount
from logic.accounting import generate_document_code
from logic.accounting_accounts import CHART_OF_ACCOUNTS, seed_accounts
from logic.jalali import parse_jalali_date

SHEET_ALIASES = {
    "general": ("تراز کل",),
    "subsidiary": ("تراز معین", "تراز معين"),
    "detailed": ("تراز تفصیلی", "تراز تفصيلي"),
    "detail_ledger": ("ریز نمونه", "ريز نمونه"),
}

TOTAL_LABELS = {"جمع", "جمع کل", "جمع كل"}
DETAILED_CODE_RE = re.compile(r"(\d{3,4}/\d+/[\d]+)")
DATE_RANGE_RE = re.compile(r"(\d{4}/\d{2}/\d{2})")
DOC_RANGE_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


@dataclass
class TrialBalanceRow:
    code: str
    name: str
    opening_debit: Decimal = Decimal(0)
    opening_credit: Decimal = Decimal(0)
    turnover_debit: Decimal = Decimal(0)
    turnover_credit: Decimal = Decimal(0)
    balance_debit: Decimal = Decimal(0)
    balance_credit: Decimal = Decimal(0)


@dataclass
class DetailLedgerRow:
    entry_date: str
    document_number: int
    attach_code: str
    description: str
    debit: Decimal = Decimal(0)
    credit: Decimal = Decimal(0)


@dataclass
class ParsedExcel:
    metadata: dict = field(default_factory=dict)
    general_rows: list[TrialBalanceRow] = field(default_factory=list)
    subsidiary_rows: list[TrialBalanceRow] = field(default_factory=list)
    detailed_rows: list[TrialBalanceRow] = field(default_factory=list)
    detail_ledger_account_code: str = ""
    detail_ledger_account_name: str = ""
    detail_ledger_rows: list[DetailLedgerRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _normalize_text(value):
    if value is None:
        return ""
    text = str(value).strip()
    return (
        text.replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\u200c", "")
        .strip()
    )


def _parse_money(value):
    if value is None or value == "":
        return Decimal(0)
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = _normalize_text(value).replace(",", "")
    if not text:
        return Decimal(0)
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"مبلغ نامعتبر: {value}") from exc


def _find_sheet(workbook, aliases):
    normalized = {_normalize_text(name): name for name in workbook.sheetnames}
    for alias in aliases:
        key = _normalize_text(alias)
        if key in normalized:
            return workbook[normalized[key]]
    return None


def _parse_metadata_rows(rows):
    meta = {}
    for row in rows[:5]:
        joined = " ".join(_normalize_text(cell) for cell in row if cell is not None)
        if not joined:
            continue
        dates = DATE_RANGE_RE.findall(joined)
        if "از تاريخ" in joined.replace(" ", "") or "از تاریخ" in joined:
            if dates:
                meta.setdefault("date_from", dates[0])
        if "تا تاريخ" in joined.replace(" ", "") or "تا تاریخ" in joined:
            if dates:
                meta.setdefault("date_to", dates[-1])
        doc_match = DOC_RANGE_RE.search(joined)
        if doc_match and ("سند" in joined or "سند" in joined.replace("ي", "ی")):
            if "از سند" in joined.replace(" ", ""):
                meta.setdefault("doc_from", int(doc_match.group(1)))
            elif "تا سند" in joined.replace(" ", ""):
                meta.setdefault("doc_to", int(doc_match.group(1)))
    return meta


def _find_header_row(rows):
    for index, row in enumerate(rows):
        first = _normalize_text(row[0] if row else "")
        second = _normalize_text(row[1] if row and len(row) > 1 else "")
        if first == "کد حساب" and "عنوان" in second:
            return index
    return None


def _parse_trial_balance_sheet(worksheet):
    rows = list(worksheet.iter_rows(values_only=True))
    metadata = _parse_metadata_rows(rows)
    header_index = _find_header_row(rows)
    if header_index is None:
        raise ValueError("سطر عنوان ستون‌های تراز (کد حساب / عنوان حساب) یافت نشد.")

    parsed_rows = []
    totals = None
    data_start = header_index + 2
    for row in rows[data_start:]:
        code = _normalize_text(row[0] if row else "")
        name = _normalize_text(row[1] if row and len(row) > 1 else "")
        if not code and not name:
            continue
        if name in TOTAL_LABELS or code in TOTAL_LABELS:
            totals = TrialBalanceRow(
                code="",
                name="جمع",
                opening_debit=_parse_money(row[2] if row and len(row) > 2 else 0),
                opening_credit=_parse_money(row[3] if row and len(row) > 3 else 0),
                turnover_debit=_parse_money(row[4] if row and len(row) > 4 else 0),
                turnover_credit=_parse_money(row[5] if row and len(row) > 5 else 0),
                balance_debit=_parse_money(row[6] if row and len(row) > 6 else 0),
                balance_credit=_parse_money(row[7] if row and len(row) > 7 else 0),
            )
            break
        if not code:
            continue
        parsed_rows.append(
            TrialBalanceRow(
                code=code,
                name=name,
                opening_debit=_parse_money(row[2] if row and len(row) > 2 else 0),
                opening_credit=_parse_money(row[3] if row and len(row) > 3 else 0),
                turnover_debit=_parse_money(row[4] if row and len(row) > 4 else 0),
                turnover_credit=_parse_money(row[5] if row and len(row) > 5 else 0),
                balance_debit=_parse_money(row[6] if row and len(row) > 6 else 0),
                balance_credit=_parse_money(row[7] if row and len(row) > 7 else 0),
            )
        )
    return metadata, parsed_rows, totals


def _parse_detail_ledger_sheet(worksheet):
    rows = list(worksheet.iter_rows(values_only=True))
    account_code = ""
    account_name = ""
    for row in rows[:4]:
        joined = " ".join(_normalize_text(cell) for cell in row if cell is not None)
        match = DETAILED_CODE_RE.search(joined)
        if match:
            account_code = match.group(1)
        if "عنوان حساب تفصيلی" in joined or "عنوان حساب تفصیلی" in joined:
            parts = joined.split(":")
            if len(parts) > 1:
                account_name = parts[-1].strip(" -")

    header_index = None
    for index, row in enumerate(rows):
        first = _normalize_text(row[0] if row else "")
        if first in ("تاريخ", "تاریخ"):
            header_index = index
            break
    if header_index is None:
        raise ValueError("سطر عنوان ستون‌های ریز حساب یافت نشد.")

    parsed_rows = []
    for row in rows[header_index + 1 :]:
        date_text = _normalize_text(row[0] if row else "")
        if not date_text:
            continue
        doc_raw = row[1] if row and len(row) > 1 else None
        if doc_raw is None or str(doc_raw).strip() == "":
            continue
        try:
            document_number = int(doc_raw)
        except (TypeError, ValueError):
            continue
        parsed_rows.append(
            DetailLedgerRow(
                entry_date=date_text,
                document_number=document_number,
                attach_code=_normalize_text(row[2] if row and len(row) > 2 else ""),
                description=_normalize_text(row[3] if row and len(row) > 3 else ""),
                debit=_parse_money(row[4] if row and len(row) > 4 else 0),
                credit=_parse_money(row[5] if row and len(row) > 5 else 0),
            )
        )
    return account_code, account_name, parsed_rows


def parse_account_code(code):
    parts = [part.strip() for part in _normalize_text(code).split("/") if part.strip()]
    if len(parts) == 1:
        return "general", parts[0], None, None
    if len(parts) == 2:
        return "subsidiary", parts[0], parts[1], None
    if len(parts) >= 3:
        return "detailed", parts[0], parts[1], parts[2]
    raise ValueError(f"کد حساب نامعتبر: {code}")


def infer_account_class(code):
    first = (code or "0")[0]
    return {
        "1": "asset",
        "4": "liability",
        "5": "liability",
        "6": "equity",
        "7": "revenue",
        "8": "expense",
        "9": "expense",
    }.get(first, "asset")


def infer_normal_balance(account_class):
    if account_class in {"liability", "equity", "revenue"}:
        return "credit"
    return "debit"


def _slug_for_code(code):
    for row in CHART_OF_ACCOUNTS:
        if row.get("code") == code:
            return row["slug"]
    return f"excel_{code}"


def validate_excel_workbook(workbook):
    parsed = ParsedExcel()
    general_ws = _find_sheet(workbook, SHEET_ALIASES["general"])
    subsidiary_ws = _find_sheet(workbook, SHEET_ALIASES["subsidiary"])
    detailed_ws = _find_sheet(workbook, SHEET_ALIASES["detailed"])
    detail_ws = _find_sheet(workbook, SHEET_ALIASES["detail_ledger"])

    if not general_ws:
        parsed.errors.append("شیت «تراز کل» یافت نشد.")
        return parsed
    if not subsidiary_ws:
        parsed.errors.append("شیت «تراز معین» یافت نشد.")
        return parsed
    if not detailed_ws:
        parsed.errors.append("شیت «تراز تفصیلی» یافت نشد.")
        return parsed

    try:
        general_meta, parsed.general_rows, general_totals = _parse_trial_balance_sheet(general_ws)
        parsed.metadata.update(general_meta)
        parsed.metadata["general_totals"] = general_totals
    except ValueError as exc:
        parsed.errors.append(str(exc))

    try:
        subsidiary_meta, parsed.subsidiary_rows, subsidiary_totals = _parse_trial_balance_sheet(subsidiary_ws)
        parsed.metadata.setdefault("date_from", subsidiary_meta.get("date_from"))
        parsed.metadata.setdefault("date_to", subsidiary_meta.get("date_to"))
        parsed.metadata["subsidiary_totals"] = subsidiary_totals
    except ValueError as exc:
        parsed.errors.append(str(exc))

    try:
        _, parsed.detailed_rows, detailed_totals = _parse_trial_balance_sheet(detailed_ws)
        parsed.metadata["detailed_totals"] = detailed_totals
    except ValueError as exc:
        parsed.errors.append(str(exc))

    if detail_ws:
        try:
            (
                parsed.detail_ledger_account_code,
                parsed.detail_ledger_account_name,
                parsed.detail_ledger_rows,
            ) = _parse_detail_ledger_sheet(detail_ws)
        except ValueError as exc:
            parsed.errors.append(str(exc))

    for label, totals in (
        ("تراز کل", parsed.metadata.get("general_totals")),
        ("تراز معین", parsed.metadata.get("subsidiary_totals")),
        ("تراز تفصیلی", parsed.metadata.get("detailed_totals")),
    ):
        if not totals:
            continue
        if totals.turnover_debit != totals.turnover_credit:
            parsed.warnings.append(
                f"{label}: گردش بدهکار ({int(totals.turnover_debit)}) "
                f"با بستانکار ({int(totals.turnover_credit)}) برابر نیست."
            )
        if totals.opening_debit != totals.opening_credit:
            parsed.warnings.append(
                f"{label}: افتتاحیه بدهکار ({int(totals.opening_debit)}) "
                f"با بستانکار ({int(totals.opening_credit)}) برابر نیست."
            )

    if parsed.detail_ledger_rows:
        detail_debit = sum(row.debit for row in parsed.detail_ledger_rows)
        detail_credit = sum(row.credit for row in parsed.detail_ledger_rows)
        if detail_debit != detail_credit:
            parsed.warnings.append(
                f"ریز حساب (تک‌حسابی): جمع بدهکار ({int(detail_debit)}) "
                f"و بستانکار ({int(detail_credit)}) — این طبیعی است و مانع import نیست."
            )

    return parsed


def parse_excel_file(file_obj):
    from openpyxl import load_workbook

    content = file_obj.read()
    if not content:
        raise ValueError("فایل خالی است.")
    workbook = load_workbook(filename=BytesIO(content), read_only=True, data_only=True)
    try:
        parsed = validate_excel_workbook(workbook)
    finally:
        workbook.close()
    return parsed


def _get_or_create_general_account(code, name):
    account = Account.objects.filter(code=code).first()
    if account:
        clean_name = name.strip()
        if clean_name and account.name != clean_name:
            account.name = clean_name
            account.save(update_fields=["name"])
        return account, False

    slug = _slug_for_code(code)
    account_class = infer_account_class(code)
    account, created = Account.objects.get_or_create(
        slug=slug,
        defaults={
            "code": code,
            "name": name.strip() or f"حساب {code}",
            "account_class": account_class,
            "normal_balance": infer_normal_balance(account_class),
            "sort_order": int(code) if code.isdigit() else 0,
            "is_active": True,
        },
    )
    if not created and not account.code:
        account.code = code
        account.save(update_fields=["code"])
    return account, created


def _get_or_create_subsidiary(general_code, sub_code, name):
    account = Account.objects.filter(code=general_code).first()
    if not account:
        account, _ = _get_or_create_general_account(general_code, name)
    sub = SubsidiaryAccount.objects.filter(account=account, code=sub_code).first()
    if sub:
        clean_name = name.strip()
        if clean_name and sub.name != clean_name:
            sub.name = clean_name
            sub.save(update_fields=["name"])
        return sub, False
    sub = SubsidiaryAccount.objects.create(
        account=account,
        code=sub_code,
        name=name.strip() or f"معین {general_code}/{sub_code}",
    )
    return sub, True


def _get_or_create_detailed(general_code, sub_code, detail_code, name):
    subsidiary = SubsidiaryAccount.objects.filter(account__code=general_code, code=sub_code).first()
    if not subsidiary:
        subsidiary, _ = _get_or_create_subsidiary(general_code, sub_code, name)
    detail = DetailedAccount.objects.filter(subsidiary=subsidiary, code=detail_code).first()
    if detail:
        clean_name = name.strip()
        if clean_name and detail.name != clean_name:
            detail.name = clean_name
            detail.save(update_fields=["name"])
        return detail, False
    detail = DetailedAccount.objects.create(
        subsidiary=subsidiary,
        code=detail_code,
        name=name.strip() or f"تفصیلی {general_code}/{sub_code}/{detail_code}",
    )
    return detail, True


def _resolve_detailed_by_code(full_code, fallback_name=""):
    level, general_code, sub_code, detail_code = parse_account_code(full_code)
    if level != "detailed":
        raise ValueError(f"کد تفصیلی نامعتبر: {full_code}")
    return _get_or_create_detailed(general_code, sub_code, detail_code, fallback_name)


@transaction.atomic
def import_excel_file(file_obj, *, dry_run=False, approve=False, force=False):
    seed_accounts()
    parsed = parse_excel_file(file_obj)
    if parsed.errors:
        return _build_report(parsed, dry_run=dry_run, committed=False)

    stats = {
        "accounts_created": 0,
        "accounts_updated": 0,
        "subsidiaries_created": 0,
        "subsidiaries_updated": 0,
        "details_created": 0,
        "details_updated": 0,
        "entries_created": 0,
        "entries_skipped": 0,
    }

    for row in parsed.general_rows:
        _, created = _get_or_create_general_account(row.code, row.name)
        if created:
            stats["accounts_created"] += 1
        else:
            stats["accounts_updated"] += 1

    for row in parsed.subsidiary_rows:
        level, general_code, sub_code, _ = parse_account_code(row.code)
        if level != "subsidiary":
            parsed.warnings.append(f"ردیف معین نادیده گرفته شد: {row.code}")
            continue
        _, created = _get_or_create_subsidiary(general_code, sub_code, row.name)
        if created:
            stats["subsidiaries_created"] += 1
        else:
            stats["subsidiaries_updated"] += 1

    for row in parsed.detailed_rows:
        level, general_code, sub_code, detail_code = parse_account_code(row.code)
        if level != "detailed":
            parsed.warnings.append(f"ردیف تفصیلی نادیده گرفته شد: {row.code}")
            continue
        _, created = _get_or_create_detailed(general_code, sub_code, detail_code, row.name)
        if created:
            stats["details_created"] += 1
        else:
            stats["details_updated"] += 1

    if parsed.detail_ledger_rows:
        if not parsed.detail_ledger_account_code:
            parsed.errors.append("کد حساب تفصیلی در شیت ریز یافت نشد.")
            return _build_report(parsed, dry_run=dry_run, committed=False, stats=stats)

        detailed, _ = _resolve_detailed_by_code(
            parsed.detail_ledger_account_code,
            parsed.detail_ledger_account_name,
        )
        subsidiary = detailed.subsidiary
        account = subsidiary.account
        doc_codes = {}

        for row in parsed.detail_ledger_rows:
            if row.debit <= 0 and row.credit <= 0:
                continue
            try:
                entry_date = parse_jalali_date(row.entry_date)
            except ValueError as exc:
                parsed.warnings.append(f"تاریخ نامعتبر {row.entry_date}: {exc}")
                continue

            exists = AccountingEntry.objects.filter(
                detailed=detailed,
                document_number=row.document_number,
                entry_date__date=entry_date.date(),
                debit=row.debit,
                credit=row.credit,
                description=row.description,
            ).exists()
            if exists:
                stats["entries_skipped"] += 1
                continue

            doc_code = doc_codes.get(row.document_number)
            if not doc_code:
                doc_code = generate_document_code(entry_date=entry_date)
                doc_codes[row.document_number] = doc_code

            amount = row.debit or row.credit
            AccountingEntry.objects.create(
                entry_type="manual",
                account=account,
                subsidiary=subsidiary,
                detailed=detailed,
                debit=row.debit,
                credit=row.credit,
                amount=amount,
                description=row.description or f"سند {row.document_number}",
                document_code=doc_code,
                document_number=row.document_number,
                attach_code=row.attach_code,
                general_account=account.get_account_class_display(),
                subsidiary_account=subsidiary.name,
                detailed_account=detailed.name,
                is_approved=approve,
                entry_date=entry_date,
            )
            stats["entries_created"] += 1

    if dry_run:
        transaction.set_rollback(True)

    balanced = not any(
        w for w in parsed.warnings
        if "گردش بدهکار" in w or "افتتاحیه بدهکار" in w
    )
    return _build_report(parsed, dry_run=dry_run, committed=not dry_run, stats=stats, balanced=balanced)


def _build_report(parsed, *, dry_run, committed, stats=None, balanced=True):
    totals = parsed.metadata.get("general_totals")
    return {
        "dry_run": dry_run,
        "committed": committed,
        "balanced": balanced,
        "metadata": {
            "date_from": parsed.metadata.get("date_from"),
            "date_to": parsed.metadata.get("date_to"),
            "doc_from": parsed.metadata.get("doc_from"),
            "doc_to": parsed.metadata.get("doc_to"),
        },
        "counts": {
            "general_rows": len(parsed.general_rows),
            "subsidiary_rows": len(parsed.subsidiary_rows),
            "detailed_rows": len(parsed.detailed_rows),
            "detail_ledger_rows": len(parsed.detail_ledger_rows),
        },
        "stats": stats or {},
        "trial_totals": {
            "turnover_debit": int(totals.turnover_debit) if totals else 0,
            "turnover_credit": int(totals.turnover_credit) if totals else 0,
            "turnover_balanced": bool(totals and totals.turnover_debit == totals.turnover_credit),
        },
        "detail_ledger_account": parsed.detail_ledger_account_code,
        "warnings": parsed.warnings,
        "errors": parsed.errors,
    }
