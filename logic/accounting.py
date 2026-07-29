"""منطق دسترسی و کمک‌تابع‌های حسابداری."""

from django.db import transaction
from django.utils import timezone

from backend.models import AccountingEntry

SYSTEM_ENTRY_TYPES = {"sale", "receivable", "payment"}
PAYMENT_ACCOUNT_SLUGS = {"cash_documents", "petty_cash", "bank", "collection_at_bank"}


def generate_document_code(*, entry_date=None):
    """کد خودکار سند — S-{سال}-{شماره}."""
    when = entry_date or timezone.now()
    if timezone.is_naive(when):
        when = timezone.make_aware(when)
    year = timezone.localtime(when).year
    prefix = f"S-{year}-"
    last = (
        AccountingEntry.objects.filter(document_code__startswith=prefix)
        .order_by("-document_code")
        .values_list("document_code", flat=True)
        .first()
    )
    seq = 1
    if last:
        try:
            seq = int(last.rsplit("-", 1)[-1]) + 1
        except (TypeError, ValueError):
            seq = AccountingEntry.objects.filter(document_code__startswith=prefix).count() + 1
    return f"{prefix}{seq:05d}"


def assign_document_code(entry):
    if entry.document_code:
        return entry.document_code
    entry.document_code = generate_document_code(entry_date=entry.entry_date)
    entry.save(update_fields=["document_code"])
    return entry.document_code


def next_document_number(*, entry_date=None):
    """شماره سند عددی — یکتا در هر سال میلادی (مثل 1 تا 2115)."""
    when = entry_date or timezone.now()
    if timezone.is_naive(when):
        when = timezone.make_aware(when)
    year = timezone.localtime(when).year
    last = (
        AccountingEntry.objects.filter(document_number__isnull=False, entry_date__year=year)
        .order_by("-document_number")
        .values_list("document_number", flat=True)
        .first()
    )
    return (last or 0) + 1


def assign_document_number(entry):
    if entry.document_number:
        return entry.document_number
    entry.document_number = next_document_number(entry_date=entry.entry_date)
    entry.save(update_fields=["document_number"])
    return entry.document_number


def default_accounts_for_model(account):
    if not account:
        return "", "", ""
    return account.get_account_class_display(), account.name, ""


def resolve_entry_accounts(account, *, general="", subsidiary="", detailed=""):
    general = (general or "").strip()
    subsidiary = (subsidiary or "").strip()
    detailed = (detailed or "").strip()
    if account:
        if not general:
            general = account.get_account_class_display()
        if not subsidiary:
            subsidiary = account.name
    return general, subsidiary, detailed


def create_accounting_entry(
    *,
    entry_type,
    sale=None,
    debit=0,
    credit=0,
    amount=0,
    description="",
    is_approved=True,
    account=None,
    account_slug=None,
    subsidiary_ref=None,
    detailed_ref=None,
    document_code="",
    document_number=None,
    attach_code="",
    opening_debit=0,
    opening_credit=0,
    balance_debit=0,
    balance_credit=0,
    entry_date=None,
    general_account="",
    subsidiary_account="",
    detailed_account="",
):
    from logic.accounting_accounts import payment_account_for_sale, resolve_account_for_entry
    from logic.accounting_money import to_rial

    debit = to_rial(debit)
    credit = to_rial(credit)
    amount = to_rial(amount) if amount else 0
    opening_debit = to_rial(opening_debit)
    opening_credit = to_rial(opening_credit)
    balance_debit = to_rial(balance_debit)
    balance_credit = to_rial(balance_credit)

    if account is None:
        if account_slug:
            account = resolve_account_for_entry(account_slug=account_slug)
        elif entry_type == "payment" and sale is not None:
            account = payment_account_for_sale(sale)
        else:
            account = resolve_account_for_entry(entry_type=entry_type)

    if detailed_ref and not subsidiary_ref:
        subsidiary_ref = detailed_ref.subsidiary
    if subsidiary_ref and not account:
        account = subsidiary_ref.account

    effective_amount = amount or debit or credit
    general, subsidiary_text, detailed_text = resolve_entry_accounts(
        account,
        general=general_account,
        subsidiary=subsidiary_account or (subsidiary_ref.name if subsidiary_ref else ""),
        detailed=detailed_account or (detailed_ref.name if detailed_ref else ""),
    )
    entry = AccountingEntry.objects.create(
        entry_type=entry_type,
        account=account,
        subsidiary=subsidiary_ref,
        detailed=detailed_ref,
        debit=debit,
        credit=credit,
        amount=effective_amount,
        description=description,
        sale=sale,
        is_approved=is_approved,
        document_code=(document_code or "").strip(),
        document_number=document_number,
        attach_code=(attach_code or "").strip(),
        general_account=general,
        subsidiary_account=subsidiary_text,
        detailed_account=detailed_text,
        opening_debit=opening_debit,
        opening_credit=opening_credit,
        balance_debit=balance_debit,
        balance_credit=balance_credit,
    )
    if entry_date is not None:
        entry.entry_date = entry_date
        entry.save(update_fields=["entry_date"])
    if not entry.document_code:
        assign_document_code(entry)
    if not entry.document_number:
        assign_document_number(entry)
    return entry


def is_payment_account(account):
    return account and account.slug in PAYMENT_ACCOUNT_SLUGS


def is_system_entry(entry):
    return entry.sale_id is not None and entry.entry_type in SYSTEM_ENTRY_TYPES


def is_office_accounting_user(user):
    """اداری = حسابداری — بدون تایید جداگانه اسناد."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    from auth.org_roles import is_accounting_finance
    from auth.permissions import APPROVE_SALE_ACCOUNTING, has_permission

    return is_accounting_finance(user) or has_permission(user, APPROVE_SALE_ACCOUNTING)


def entry_permissions(entry, user=None):
    """سطح دسترسی ویرایش/حذف هر سند."""
    if is_office_accounting_user(user):
        if is_system_entry(entry):
            return {"can_edit": True, "can_delete": True, "edit_mode": "partial"}
        return {"can_edit": True, "can_delete": True, "edit_mode": "full"}
    if entry.is_approved:
        return {"can_edit": False, "can_delete": True, "edit_mode": "none"}
    if is_system_entry(entry):
        return {"can_edit": True, "can_delete": True, "edit_mode": "partial"}
    return {"can_edit": True, "can_delete": True, "edit_mode": "full"}


def approve_sale_accounting_entries(sale):
    """تایید خودکار اسناد فاکتور — اداری نیازی به تایید جداگانه ندارد."""
    AccountingEntry.objects.filter(sale=sale).update(is_approved=True)


def delete_entries_for_sale(sale):
    """حذف تمام اسناد حسابداری مرتبط با یک فروش."""
    deleted, _ = AccountingEntry.objects.filter(sale=sale).delete()
    return deleted


@transaction.atomic
def delete_accounting_entry(entry, user=None):
    """
    حذف سند حسابداری با همگام‌سازی فاکتور در همه جداول.

    - سند درآمد (sale): حذف نرم کل فاکتور + اداری + کارخانه
    - سند پرداخت: برگشت مبلغ روی فاکتور
    - سند مطالبات: بازسازی از مانده فعلی فاکتور
    """
    sale = entry.sale
    entry_type = entry.entry_type
    entry_id = entry.id
    amount = entry.amount

    if sale and getattr(sale, "is_deleted", False):
        entry.delete()
        return {
            "deleted": True,
            "entry_id": entry_id,
            "sale_deleted": False,
            "sale_id": sale.id,
        }

    if sale and entry_type == "sale":
        from logic.sales import delete_sale

        deleted_entries = delete_sale(sale, user=user)
        return {
            "deleted": True,
            "entry_id": entry_id,
            "sale_deleted": True,
            "sale_id": sale.id,
            "accounting_entries_deleted": deleted_entries,
        }

    if sale and entry_type == "payment":
        from decimal import Decimal

        from logic.sales import reverse_payment

        amount_rial = Decimal(amount or 0)
        reverse_payment(sale, amount_rial, user=user)
        entry.delete()
        return {
            "deleted": True,
            "entry_id": entry_id,
            "sale_deleted": False,
            "sale_id": sale.id,
            "payment_reversed": int(amount_rial),
        }

    if sale and entry_type == "receivable":
        entry.delete()
        from logic.sales import _sync_receivable_entry
        from logic.order_queues import sync_workflow_orders_from_sale

        _sync_receivable_entry(sale)
        sync_workflow_orders_from_sale(sale)
        return {
            "deleted": True,
            "entry_id": entry_id,
            "sale_deleted": False,
            "sale_id": sale.id,
        }

    entry.delete()
    return {
        "deleted": True,
        "entry_id": entry_id,
        "sale_deleted": False,
        "sale_id": sale.id if sale else None,
    }
