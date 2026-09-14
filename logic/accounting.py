"""Core journal operations and legacy line adapters."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from backend.models import JournalEntry, JournalLine, JournalOrderLink, Ledger
from logic.chart_of_accounts import ACCOUNT_SLUGS, PAYMENT_ACCOUNT_SLUGS
from logic.ledger import OFFICE_LEDGER

SYSTEM_ENTRY_TYPES = {"sale", "receivable", "payment"}


def _ledger_row(config, *, lock=False):
    qs = Ledger.objects
    if lock:
        qs = qs.select_for_update()
    return qs.get(code=config.id)


def _allocate_document(*, ledger=OFFICE_LEDGER, entry_date=None, document_number=None, document_code=""):
    when = entry_date or timezone.now()
    with transaction.atomic():
        row = _ledger_row(ledger, lock=True)
        number = document_number
        if number is None:
            number = (
                JournalEntry.objects.filter(ledger=row).aggregate(value=Max("document_number"))["value"]
                or 0
            ) + 1
        code = (document_code or "").strip() or f"{ledger.document_prefix}-{timezone.localtime(when).year}-{number:05d}"
        if JournalEntry.objects.filter(ledger=row).filter(
            models_q_document(number, code)
        ).exists():
            raise ValueError("این کد یا شماره سند قبلاً ثبت شده است.")
        return row, number, code


def models_q_document(number, code):
    from django.db.models import Q

    return Q(document_number=number) | Q(document_code=code)


def generate_document_code(*, entry_date=None, ledger=OFFICE_LEDGER):
    _, number, code = _allocate_document(ledger=ledger, entry_date=entry_date)
    return code


def next_document_number(*, entry_date=None, ledger=OFFICE_LEDGER):
    _, number, _ = _allocate_document(ledger=ledger, entry_date=entry_date)
    return number


def assign_document_code(entry, *, ledger=OFFICE_LEDGER):
    return entry.journal.document_code


def assign_document_number(entry, *, ledger=OFFICE_LEDGER):
    return entry.journal.document_number


def resolve_entry_accounts(account, *, general="", subsidiary="", detailed=""):
    if not account:
        return general, subsidiary, detailed
    ancestors = list(
        account.ancestor_paths.select_related("ancestor").order_by("-depth")
    )
    names = [path.ancestor.name for path in ancestors]
    return (
        general or account.get_account_class_display(),
        subsidiary or (names[-2] if len(names) >= 2 else account.name),
        detailed or (account.name if len(names) >= 3 else ""),
    )


@transaction.atomic
def create_journal(*, lines, entry_type="manual", description="", entry_date=None,
                   is_approved=True, ledger=OFFICE_LEDGER, document_code="",
                   document_number=None, user=None, sale=None, factory_order=None,
                   transfer_source=None):
    if len(lines) < 2:
        raise ValueError("سند حسابداری باید حداقل دو ردیف داشته باشد.")
    total_debit = sum(Decimal(line.get("debit") or 0) for line in lines)
    total_credit = sum(Decimal(line.get("credit") or 0) for line in lines)
    if total_debit != total_credit:
        raise ValueError("جمع بدهکار و بستانکار سند باید برابر باشد.")
    if total_debit <= 0:
        raise ValueError("مبلغ سند باید بزرگ‌تر از صفر باشد.")

    when = entry_date or timezone.now()
    ledger_row, number, code = _allocate_document(
        ledger=ledger, entry_date=when, document_number=document_number,
        document_code=document_code,
    )
    try:
        journal = JournalEntry.objects.create(
            ledger=ledger_row,
            document_number=number,
            document_code=code,
            entry_type=entry_type,
            entry_date=when,
            description=description,
            status=JournalEntry.STATUS_DRAFT,
            created_by=user,
            transfer_source=transfer_source,
        )
    except IntegrityError as exc:
        raise ValueError("این کد یا شماره سند قبلاً ثبت شده است.") from exc

    for index, line in enumerate(lines, 1):
        account = line["account"]
        if account.ledger_id != ledger_row.id:
            raise ValueError("همه حساب‌ها باید متعلق به دفتر سند باشند.")
        JournalLine.objects.create(
            journal=journal,
            account=account,
            debit=Decimal(line.get("debit") or 0),
            credit=Decimal(line.get("credit") or 0),
            description=(line.get("description") or description or "").strip(),
            line_number=index,
        )
    source = sale or factory_order
    if source:
        JournalOrderLink.objects.create(
            journal=journal,
            order=source,
            relation_type="sale" if sale else "factory_order",
        )
    if is_approved:
        journal.post()
    return journal


def create_accounting_entry(**kwargs):
    """Create a balanced two-line journal for the legacy single-row endpoint."""
    from logic.accounting_accounts import get_account, payment_account_for_sale, resolve_account_for_entry
    from logic.accounting_money import to_rial

    ledger = kwargs.get("ledger", OFFICE_LEDGER)
    entry_type = kwargs["entry_type"]
    account = kwargs.get("account")
    sale = kwargs.get("sale")
    if account is None:
        if kwargs.get("account_slug"):
            account = resolve_account_for_entry(account_slug=kwargs["account_slug"], ledger=ledger)
        elif entry_type == "payment" and sale:
            account = payment_account_for_sale(sale, ledger=ledger)
        else:
            account = resolve_account_for_entry(entry_type=entry_type, ledger=ledger)
    debit = Decimal(to_rial(kwargs.get("debit") or 0))
    credit = Decimal(to_rial(kwargs.get("credit") or 0))
    amount = Decimal(to_rial(kwargs.get("amount") or debit or credit))
    if not debit and not credit:
        debit = amount if account.normal_balance == "debit" else Decimal(0)
        credit = amount if account.normal_balance == "credit" else Decimal(0)
    counter = get_account(
        ACCOUNT_SLUGS.RECEIVABLES if account.slug != ACCOUNT_SLUGS.RECEIVABLES else ACCOUNT_SLUGS.OTHER_REVENUE,
        ledger=ledger,
    )
    lines = [{"account": account, "debit": debit, "credit": credit, "description": kwargs.get("description", "")}]
    lines.append({
        "account": counter,
        "debit": credit,
        "credit": debit,
        "description": kwargs.get("description", ""),
    })
    journal = create_journal(
        lines=lines,
        entry_type=entry_type,
        description=kwargs.get("description", ""),
        entry_date=kwargs.get("entry_date"),
        is_approved=kwargs.get("is_approved", True),
        ledger=ledger,
        document_code=kwargs.get("document_code", ""),
        document_number=kwargs.get("document_number"),
        sale=sale,
        factory_order=kwargs.get("factory_order"),
    )
    return journal.lines.order_by("line_number").first()


def is_payment_account(account):
    return bool(account and account.slug in PAYMENT_ACCOUNT_SLUGS)


def is_system_entry(entry, *, ledger=OFFICE_LEDGER):
    return bool(entry.sale_id and entry.entry_type in SYSTEM_ENTRY_TYPES)


def is_office_accounting_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    from auth.org_roles import is_accounting_finance
    from auth.permissions import APPROVE_SALE_ACCOUNTING, has_permission
    return is_accounting_finance(user) or has_permission(user, APPROVE_SALE_ACCOUNTING)


def is_factory_accounting_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    from auth.permissions import APPROVE_FACTORY_ACCOUNTING, MANAGE_FACTORY_ORDERS, VIEW_FACTORY_ACCOUNTING, has_permission
    return has_permission(user, APPROVE_FACTORY_ACCOUNTING) or (
        has_permission(user, VIEW_FACTORY_ACCOUNTING) and has_permission(user, MANAGE_FACTORY_ORDERS)
    )


def is_auto_approved_accounting_user(user, *, ledger=OFFICE_LEDGER):
    return is_factory_accounting_user(user) if ledger.id == "factory" else is_office_accounting_user(user)


def entry_permissions(entry, user=None, *, ledger=OFFICE_LEDGER):
    transferred = bool(getattr(entry.journal, "transferred_journal", None))
    approved = entry.journal.status == JournalEntry.STATUS_POSTED
    privileged = is_auto_approved_accounting_user(user, ledger=ledger)
    system = is_system_entry(entry, ledger=ledger)
    return {
        "can_edit": not transferred and not approved and (privileged or not system),
        "can_delete": not transferred and not approved,
        "edit_mode": "partial" if system and not approved else ("full" if not approved else "none"),
    }


def approve_sale_accounting_entries(sale, *, ledger=OFFICE_LEDGER):
    for journal in JournalEntry.objects.filter(order_links__order=sale, order_links__relation_type="sale").distinct():
        if journal.status != JournalEntry.STATUS_POSTED:
            journal.post()


def delete_entries_for_sale(sale, *, ledger=OFFICE_LEDGER):
    qs = JournalEntry.objects.filter(
        order_links__order=sale, ledger__code=ledger.id
    ).exclude(status_ref_id=JournalEntry.STATUS_VOID).distinct()
    count = sum(journal.lines.count() for journal in qs)
    qs.update(status_ref_id=JournalEntry.STATUS_VOID, posted_at=None)
    return count


@transaction.atomic
def delete_accounting_entry(entry, user=None, *, ledger=OFFICE_LEDGER):
    journal = entry.journal
    sale = entry.sale
    entry_id = entry.id
    if getattr(journal, "transferred_journal", None):
        raise ValueError("سند منتقل‌شده قابل حذف نیست.")
    if sale and entry.entry_type == "sale":
        from logic.sales import delete_sale
        deleted = delete_sale(sale, user=user)
        return {"deleted": True, "entry_id": entry_id, "sale_deleted": True,
                "sale_id": sale.id, "accounting_entries_deleted": deleted}
    if sale and entry.entry_type == "payment":
        payment_amount = sum(
            line.debit
            for line in journal.lines.select_related("account")
            if is_payment_account(line.account)
        )
        if payment_amount:
            from logic.sales import reverse_payment

            reverse_payment(sale, payment_amount, user=user)
    journal.status = JournalEntry.STATUS_VOID
    journal.posted_at = None
    journal.save(update_fields=["status", "posted_at"])
    return {"deleted": True, "entry_id": entry_id, "sale_deleted": False,
            "sale_id": sale.id if sale else None}
