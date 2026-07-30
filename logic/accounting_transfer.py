"""انتقال اسناد حسابداری کارخانه به دفتر اداری — فقط حساب‌های مشترک."""

from django.db import transaction
from django.utils import timezone

from backend.models import Account, DetailedAccount, SubsidiaryAccount
from logic.accounting import is_auto_approved_accounting_user
from logic.accounting_accounts import seed_accounts
from logic.accounting_documents import create_accounting_document
from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER


class AccountMappingError(Exception):
    def __init__(self, message, account_label=""):
        super().__init__(message)
        self.account_label = account_label


def _ensure_charts():
    if not OFFICE_LEDGER.Account.objects.exists():
        seed_accounts(ledger=OFFICE_LEDGER)
    if not FACTORY_LEDGER.Account.objects.exists():
        seed_accounts(ledger=FACTORY_LEDGER)


def _office_general_by_slug(slug):
    if not slug:
        return None
    return Account.objects.filter(slug=slug, is_active=True).first()


def _office_subsidiary(general, code):
    if not general or not code:
        return None
    return SubsidiaryAccount.objects.filter(account=general, code=code, is_active=True).first()


def _office_detailed(subsidiary, code):
    if not subsidiary or not code:
        return None
    return DetailedAccount.objects.filter(subsidiary=subsidiary, code=code, is_active=True).first()


def _entry_account_label(entry):
    if entry.detailed_id:
        return entry.detailed.full_code + " — " + entry.detailed.name
    if entry.subsidiary_id:
        return entry.subsidiary.full_code + " — " + entry.subsidiary.name
    if entry.account_id:
        code = entry.account.code or entry.account.slug
        return f"{code} — {entry.account.name}"
    return entry.general_account or "—"


def map_factory_line_to_office(entry):
    """نگاشت یک ردیف کارخانه به حساب‌های اداری مشترک."""
    factory_account = entry.account
    if not factory_account or not factory_account.slug:
        raise AccountMappingError("حساب کل سند در کارخانه نامعتبر است.", _entry_account_label(entry))

    office_general = _office_general_by_slug(factory_account.slug)
    if not office_general:
        raise AccountMappingError(
            f"حساب کل «{factory_account.name}» در دفتر اداری یافت نشد.",
            _entry_account_label(entry),
        )

    office_subsidiary = None
    if entry.subsidiary_id:
        office_subsidiary = _office_subsidiary(office_general, entry.subsidiary.code)
        if not office_subsidiary:
            raise AccountMappingError(
                f"حساب معین «{entry.subsidiary.full_code} — {entry.subsidiary.name}» در اداری یافت نشد.",
                _entry_account_label(entry),
            )

    office_detailed = None
    if entry.detailed_id:
        if not office_subsidiary:
            raise AccountMappingError(
                f"حساب تفصیلی «{entry.detailed.full_code}» بدون معین مشترک قابل انتقال نیست.",
                _entry_account_label(entry),
            )
        office_detailed = _office_detailed(office_subsidiary, entry.detailed.code)
        if not office_detailed:
            raise AccountMappingError(
                f"حساب تفصیلی «{entry.detailed.full_code} — {entry.detailed.name}» در اداری یافت نشد.",
                _entry_account_label(entry),
            )

    line = {
        "account_id": office_general.id,
        "debit": int(entry.debit or 0),
        "credit": int(entry.credit or 0),
        "description": (entry.description or "").strip(),
        "attach_code": (entry.document_code or "").strip(),
    }
    if office_subsidiary:
        line["subsidiary_id"] = office_subsidiary.id
    if office_detailed:
        line["detailed_id"] = office_detailed.id
    return line


def _resolve_document_code(document_code="", document_number=None):
    code = (document_code or "").strip()
    if code:
        return code
    if document_number is not None:
        try:
            num = int(document_number)
        except (TypeError, ValueError):
            raise ValueError("شماره سند نامعتبر است.")
        entry = (
            FACTORY_LEDGER.AccountingEntry.objects.filter(document_number=num)
            .exclude(document_code="")
            .order_by("id")
            .first()
        )
        if entry:
            return entry.document_code
        raise ValueError(f"سند شماره {num} در کارخانه یافت نشد.")
    raise ValueError("کد یا شماره سند الزامی است.")


def _factory_document_entries(document_code):
    qs = (
        FACTORY_LEDGER.AccountingEntry.objects.filter(document_code=document_code)
        .select_related("account", "subsidiary", "detailed", "subsidiary__account", "detailed__subsidiary")
        .order_by("id")
    )
    if not qs.exists():
        raise ValueError("سند کارخانه یافت نشد.")
    return list(qs)


def _line_preview(entry):
    label = _entry_account_label(entry)
    try:
        mapped = map_factory_line_to_office(entry)
        return {
            "entry_id": entry.id,
            "account_label": label,
            "debit": int(entry.debit or 0),
            "credit": int(entry.credit or 0),
            "description": entry.description,
            "mappable": True,
            "mapped_account_id": mapped.get("account_id"),
        }
    except AccountMappingError as exc:
        return {
            "entry_id": entry.id,
            "account_label": label,
            "debit": int(entry.debit or 0),
            "credit": int(entry.credit or 0),
            "description": entry.description,
            "mappable": False,
            "error": str(exc),
        }


def preview_transfer(*, document_code="", document_number=None):
    _ensure_charts()
    code = _resolve_document_code(document_code, document_number)
    entries = _factory_document_entries(code)
    transferred = entries[0].transferred_to_office_at
    office_code = entries[0].office_document_code or ""
    lines = [_line_preview(entry) for entry in entries]
    unmappable = [line for line in lines if not line["mappable"]]
    return {
        "factory_document_code": code,
        "document_number": entries[0].document_number,
        "already_transferred": bool(transferred),
        "transferred_to_office_at": transferred.isoformat() if transferred else None,
        "office_document_code": office_code,
        "lines": lines,
        "mappable_count": len(lines) - len(unmappable),
        "unmappable_count": len(unmappable),
        "can_transfer": not transferred and not unmappable and bool(lines),
        "unmappable_accounts": [line["account_label"] for line in unmappable],
    }


@transaction.atomic
def transfer_factory_document_to_office(*, document_code="", document_number=None, user=None):
    preview = preview_transfer(document_code=document_code, document_number=document_number)
    if preview["already_transferred"]:
        raise ValueError(
            f"این سند قبلاً به اداری منتقل شده است"
            + (f" ({preview['office_document_code']})" if preview["office_document_code"] else "")
            + "."
        )
    if preview["unmappable_count"]:
        accounts = "، ".join(preview["unmappable_accounts"])
        raise ValueError(f"انتقال ممکن نیست — حساب‌های غیرمشترک: {accounts}")

    entries = _factory_document_entries(preview["factory_document_code"])
    office_lines = [map_factory_line_to_office(entry) for entry in entries]
    header_desc = f"انتقال از {preview['factory_document_code']}"
    for line in office_lines:
        if not line.get("description"):
            line["description"] = header_desc

    entry_date = entries[0].entry_date
    is_approved = is_auto_approved_accounting_user(user, ledger=OFFICE_LEDGER)
    result = create_accounting_document(
        lines=office_lines,
        entry_date=entry_date,
        description=header_desc,
        is_approved=is_approved,
        entry_type="manual",
        ledger=OFFICE_LEDGER,
    )

    now = timezone.now()
    FACTORY_LEDGER.AccountingEntry.objects.filter(document_code=preview["factory_document_code"]).update(
        transferred_to_office_at=now,
        office_document_code=result["document_code"],
    )

    return {
        "factory_document_code": preview["factory_document_code"],
        "office_document_code": result["document_code"],
        "office_document_number": result["document_number"],
        "lines_transferred": len(office_lines),
        "transferred_to_office_at": now.isoformat(),
    }


def is_factory_entry_transferred(entry):
    return bool(getattr(entry, "transferred_to_office_at", None))
