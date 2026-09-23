"""وجوه سرگردان و برنامه پرداخت چک."""

from decimal import Decimal
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from backend.models import Account, SaleInstallment, UnidentifiedDeposit
from logic.accounting import create_journal
from logic.accounting_events import issue_event_draft, register_event
from logic.accounting_accounts import get_account
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.check_accounting import clear_registered_check
from logic.ledger import OFFICE_LEDGER


def deposit_to_dict(row):
    journal = row.journal
    return {
        "id": row.id,
        "deposit_date": row.deposit_date.isoformat(),
        "amount": int(row.amount or 0),
        "bank_account_id": row.bank_account_id,
        "bank_account_name": row.bank_account.name if row.bank_account_id else "",
        "description": row.description or "",
        "status": row.status,
        "status_label": row.get_status_display(),
        "customer_id": row.customer_id,
        "customer_name": row.customer.full_name if row.customer_id else "",
        "document_code": journal.document_code if journal else "",
        "journal_status": journal.status if journal else "",
    }


def list_deposits():
    rows = UnidentifiedDeposit.objects.select_related("bank_account", "customer", "journal")
    return [deposit_to_dict(row) for row in rows]


@transaction.atomic
def create_deposit(data, *, user=None):
    when = parse_date(str(data.get("deposit_date") or ""))
    if not when:
        raise ValueError("تاریخ واریز الزامی است.")
    try:
        amount = Decimal(str(data.get("amount") or 0))
    except Exception as exc:
        raise ValueError("مبلغ واریز نامعتبر است.") from exc
    if amount <= 0:
        raise ValueError("مبلغ واریز باید بزرگ‌تر از صفر باشد.")
    account_id = data.get("bank_account_id")
    try:
        account = Account.objects.get(pk=int(account_id), ledger__code=OFFICE_LEDGER.id, is_active=True)
    except (Account.DoesNotExist, TypeError, ValueError) as exc:
        raise ValueError("حساب بانک نامعتبر است.") from exc
    row = UnidentifiedDeposit.objects.create(
        deposit_date=when,
        amount=amount,
        bank_account=account,
        description=(data.get("description") or "").strip(),
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    clearing = get_account(ACCOUNT_SLUGS.OTHER_PAYABLES, ledger=OFFICE_LEDGER)
    description = row.description or f"واریز شناسایی‌نشده {row.pk}"
    event, _created = register_event(
        source_module="treasury",
        source_type="UnidentifiedDeposit",
        source=row.pk,
        event_type="deposit_received",
        payload={"amount": str(amount), "bank_account_id": account.id},
        occurred_at=timezone.make_aware(
            datetime.combine(when, datetime.min.time())
        ),
    )
    journal = issue_event_draft(
        event,
        lines=[
            {"account": account, "debit": amount, "credit": 0, "description": description},
            {"account": clearing, "debit": 0, "credit": amount, "description": description},
        ],
        entry_type="payment",
        description=description,
        user=user,
    )
    row.journal = journal
    row.save(update_fields=["journal"])
    return deposit_to_dict(row)


@transaction.atomic
def allocate_deposit(deposit_id, customer, *, user=None):
    deposit = UnidentifiedDeposit.objects.select_for_update().select_related("bank_account").get(pk=deposit_id)
    if deposit.status != UnidentifiedDeposit.STATUS_OPEN:
        raise ValueError("این واریز قبلاً تخصیص شده است.")
    receivables = get_account(ACCOUNT_SLUGS.RECEIVABLES, ledger=OFFICE_LEDGER)
    amount = int(deposit.amount)
    clearing = get_account(ACCOUNT_SLUGS.OTHER_PAYABLES, ledger=OFFICE_LEDGER)
    description = f"تخصیص وجه سرگردان — {customer.full_name}"
    event, _created = register_event(
        source_module="treasury",
        source_type="UnidentifiedDeposit",
        source=deposit.pk,
        event_type="deposit_allocated",
        payload={"amount": str(amount), "customer_id": customer.pk},
    )
    journal = issue_event_draft(
        event,
        lines=[
            {
                "account": clearing,
                "debit": amount,
                "credit": 0,
                "description": description,
            },
            {
                "account": receivables,
                "debit": 0,
                "credit": amount,
                "description": description,
            },
        ],
        entry_type="payment",
        description=description,
        user=user,
    )
    deposit.customer = customer
    deposit.journal = journal
    deposit.status = UnidentifiedDeposit.STATUS_ALLOCATED
    deposit.save(update_fields=["customer", "journal", "status"])
    return deposit_to_dict(deposit)


def check_plan_rows():
    rows = SaleInstallment.objects.filter(
        payment_method_ref_id="check",
        status_ref_id="pending",
    ).select_related("sale", "sale__customer", "deposit_account").order_by("due_date", "id")
    payload = []
    for row in rows:
        sale = row.sale
        payload.append({
            "id": row.id,
            "due_date": row.due_date.isoformat() if row.due_date else "",
            "amount": int(row.amount or 0),
            "check_number": row.check_number or "",
            "bank_name": row.bank_name or "",
            "customer_name": sale.customer.full_name if sale.customer_id else "",
            "invoice_number": sale.invoice_number or str(sale.pk),
            "registered": bool(row.accounting_registered_at),
            "deposit_account_id": row.deposit_account_id,
            "deposit_account_name": row.deposit_account.name if row.deposit_account_id else "",
        })
    return payload


def _register_one_check(installment, user=None):
    from django.utils import timezone

    from logic.posting import build_journal_lines

    sale = installment.sale
    amount = Decimal(installment.amount or 0)
    registration = installment.registration_account or get_account(
        ACCOUNT_SLUGS.COLLECTION_AT_BANK, ledger=OFFICE_LEDGER
    )
    deposit = installment.deposit_account or get_account(ACCOUNT_SLUGS.BANK, ledger=OFFICE_LEDGER)
    desc = f"ثبت چک {installment.check_number or installment.pk} — فاکتور {sale.invoice_number or sale.pk}"
    lines = build_journal_lines(
        "check_register",
        amounts={"amount": amount},
        accounts={"registration_account": registration},
        description=desc,
    )
    journal = create_journal(
        lines=lines,
        entry_type="payment",
        description=desc,
        sale=sale,
        is_approved=False,
        entry_date=sale.sold_at,
        branch=sale.branch,
    )
    installment.registration_account = registration
    installment.deposit_account = deposit
    installment.accounting_registered_at = timezone.now()
    installment.accounting_entry = journal
    installment.save(
        update_fields=[
            "registration_account",
            "deposit_account",
            "accounting_registered_at",
            "accounting_entry",
        ]
    )


@transaction.atomic
def pay_planned_check(installment_id, deposit_account_id, *, user=None):
    installment = SaleInstallment.objects.select_for_update().select_related("sale").get(pk=installment_id)
    if installment.payment_method != "check" or installment.status != "pending":
        raise ValueError("این قسط در برنامه پرداخت چک نیست.")
    try:
        account = Account.objects.get(
            pk=int(deposit_account_id), ledger__code=OFFICE_LEDGER.id, is_active=True
        )
    except (Account.DoesNotExist, TypeError, ValueError) as exc:
        raise ValueError("حساب بانک مبدا نامعتبر است.") from exc
    installment.deposit_account = account
    installment.save(update_fields=["deposit_account"])
    if not installment.accounting_registered_at:
        _register_one_check(installment, user=user)
        installment.refresh_from_db()
    clear_registered_check(installment, recorded_by=user)
    installment.refresh_from_db()
    return {
        "id": installment.id,
        "status": installment.status,
        "deposit_account_id": installment.deposit_account_id,
    }
