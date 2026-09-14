"""Relational factory-to-office journal transfer."""

from django.db import transaction

from backend.models import Account, JournalEntry
from logic.accounting import is_auto_approved_accounting_user
from logic.accounting_accounts import seed_accounts
from logic.accounting_documents import create_accounting_document
from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER


class AccountMappingError(Exception):
    def __init__(self, message, account_label=""):
        super().__init__(message)
        self.account_label = account_label


def _factory_journal(document_code="", document_number=None):
    qs = JournalEntry.objects.filter(ledger__code=FACTORY_LEDGER.id).prefetch_related("lines__account")
    try:
        if document_code:
            return qs.get(document_code=document_code.strip())
        return qs.get(document_number=int(document_number))
    except (JournalEntry.DoesNotExist, ValueError, TypeError) as exc:
        raise ValueError("سند کارخانه یافت نشد.") from exc


def _office_account(factory_account):
    ancestors = [p.ancestor for p in factory_account.ancestor_paths.select_related("ancestor").order_by("-depth")]
    parent = None
    for source in ancestors:
        target = Account.objects.filter(
            ledger__code=OFFICE_LEDGER.id, parent=parent, code=source.code, is_active=True
        ).first()
        if not target:
            raise AccountMappingError(
                f"حساب «{source.full_code} — {source.name}» در دفتر اداری یافت نشد.",
                f"{source.full_code} — {source.name}",
            )
        parent = target
    return parent


def _line_preview(line):
    try:
        target = _office_account(line.account)
        return {"entry_id": line.id, "account_label": f"{line.account.full_code} — {line.account.name}",
                "debit": int(line.debit), "credit": int(line.credit),
                "description": line.description, "mappable": True, "mapped_account_id": target.id}
    except AccountMappingError as exc:
        return {"entry_id": line.id, "account_label": exc.account_label,
                "debit": int(line.debit), "credit": int(line.credit),
                "description": line.description, "mappable": False, "error": str(exc)}


def preview_transfer(*, document_code="", document_number=None):
    seed_accounts(ledger=OFFICE_LEDGER)
    seed_accounts(ledger=FACTORY_LEDGER)
    journal = _factory_journal(document_code, document_number)
    transferred = getattr(journal, "transferred_journal", None)
    lines = [_line_preview(line) for line in journal.lines.all()]
    bad = [line for line in lines if not line["mappable"]]
    return {
        "factory_document_code": journal.document_code, "document_number": journal.document_number,
        "already_transferred": bool(transferred),
        "transferred_to_office_at": transferred.created_at.isoformat() if transferred else None,
        "office_document_code": transferred.document_code if transferred else "",
        "lines": lines, "mappable_count": len(lines) - len(bad), "unmappable_count": len(bad),
        "can_transfer": not transferred and not bad and bool(lines),
        "unmappable_accounts": [line["account_label"] for line in bad],
    }


@transaction.atomic
def transfer_factory_document_to_office(*, document_code="", document_number=None, user=None):
    source = _factory_journal(document_code, document_number)
    source = JournalEntry.objects.select_for_update().get(pk=source.pk)
    if hasattr(source, "transferred_journal"):
        raise ValueError("این سند قبلاً به اداری منتقل شده است.")
    lines = []
    for line in source.lines.select_related("account"):
        try:
            target = _office_account(line.account)
        except AccountMappingError as exc:
            raise ValueError(f"حساب غیرمشترک قابل انتقال نیست: {exc}") from exc
        depth = target.ancestor_paths.order_by("-depth").first().depth
        row = {"debit": int(line.debit), "credit": int(line.credit),
               "description": line.description or f"انتقال از {source.document_code}"}
        if depth == 0:
            row["account_id"] = target.id
        elif depth == 1:
            row["subsidiary_id"] = target.id
        else:
            row["detailed_id"] = target.id
        lines.append(row)
    result = create_accounting_document(
        lines=lines, entry_date=source.entry_date,
        description=f"انتقال از {source.document_code}",
        is_approved=is_auto_approved_accounting_user(user, ledger=OFFICE_LEDGER),
        entry_type=source.entry_type, ledger=OFFICE_LEDGER, user=user,
        transfer_source=source,
    )
    target = result["journal"]
    return {"factory_document_code": source.document_code,
            "office_document_code": target.document_code,
            "office_document_number": target.document_number,
            "lines_transferred": len(lines),
            "transferred_to_office_at": target.created_at.isoformat()}


def is_factory_entry_transferred(entry):
    return hasattr(entry.journal, "transferred_journal")
