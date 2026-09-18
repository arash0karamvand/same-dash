"""ثبت و وصول حسابداری چک."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from backend.models import Account, Sale, SaleInstallment, UserAccountingPreference
from logic.accounting import create_journal
from logic.accounting_accounts import get_account
from logic.chart_of_accounts import ACCOUNT_SLUGS, CHECK_ACCOUNT_SLUGS, code_for_slug
from logic.posting import build_journal_lines


def list_check_accounts():
    """حساب‌های مجاز برای ثبت/واریز چک."""
    return list(
        Account.objects.filter(
            is_active=True,
            account_class="asset",
            slug__in=CHECK_ACCOUNT_SLUGS,
        ).order_by("sort_order", "code")
    )


def _account_label(account):
    if not account:
        return ""
    code = (account.code or "").strip()
    name = account.name or ""
    return f"{code} — {name}" if code else name


def preference_to_dict(pref):
    if not pref:
        return {
            "default_check_registration_account_id": None,
            "default_check_registration_account_label": "",
            "default_check_deposit_account_id": None,
            "default_check_deposit_account_label": "",
        }
    reg = pref.default_check_registration_account
    dep = pref.default_check_deposit_account
    return {
        "default_check_registration_account_id": reg.id if reg else None,
        "default_check_registration_account_label": _account_label(reg),
        "default_check_deposit_account_id": dep.id if dep else None,
        "default_check_deposit_account_label": _account_label(dep),
    }


def get_user_accounting_preference(user):
    if not user or not getattr(user, "is_authenticated", False):
        return preference_to_dict(None)
    pref, _ = UserAccountingPreference.objects.get_or_create(user=user)
    return preference_to_dict(pref)


def resolve_default_check_accounts(user):
    """حساب‌های پیش‌فرض ثبت/واریز — از preference کاربر یا slug سیستمی."""
    reg = get_account(ACCOUNT_SLUGS.COLLECTION_AT_BANK, required=False)
    dep = get_account(ACCOUNT_SLUGS.BANK, required=False)
    if user and getattr(user, "is_authenticated", False):
        pref = UserAccountingPreference.objects.filter(user=user).first()
        if pref:
            if pref.default_check_registration_account_id:
                reg = pref.default_check_registration_account
            if pref.default_check_deposit_account_id:
                dep = pref.default_check_deposit_account
    return reg, dep


def save_user_accounting_preference(
    user,
    *,
    registration_account_id=None,
    deposit_account_id=None,
    save_as_default=False,
):
    if not save_as_default or not user or not getattr(user, "is_authenticated", False):
        return
    pref, _ = UserAccountingPreference.objects.get_or_create(user=user)
    updates = []
    if registration_account_id:
        pref.default_check_registration_account_id = registration_account_id
        updates.append("default_check_registration_account")
    if deposit_account_id:
        pref.default_check_deposit_account_id = deposit_account_id
        updates.append("default_check_deposit_account")
    if updates:
        pref.save(update_fields=updates + ["updated_at"])


def sale_has_pending_checks(sale):
    return SaleInstallment.objects.filter(
        sale=sale,
        payment_method="check",
        is_deleted=False,
        accounting_registered_at__isnull=True,
    ).exists()


def pending_check_installments(sale):
    return SaleInstallment.objects.filter(
        sale=sale,
        payment_method="check",
        is_deleted=False,
        accounting_registered_at__isnull=True,
    ).order_by("due_date", "id")


def _resolve_account(account_id, fallback_slug):
    if account_id:
        try:
            return Account.objects.get(pk=account_id, is_active=True)
        except Account.DoesNotExist as exc:
            raise ValueError("حساب انتخاب‌شده یافت نشد.") from exc
    account = get_account(fallback_slug, required=False)
    if not account:
        raise ValueError("حساب پیش‌فرض چک در سیستم تعریف نشده است.")
    return account


def _check_description(installment, sale):
    parts = ["ثبت چک"]
    if installment.check_number:
        parts.append(f"#{installment.check_number}")
    if installment.bank_name:
        parts.append(installment.bank_name)
    inv = sale.invoice_number or sale.pk
    parts.append(f"فاکتور {inv}")
    return " — ".join(parts)


@transaction.atomic
def register_sale_checks(sale, registration_account, deposit_account, user=None):
    """ثبت حسابداری چک‌های دریافتی — بدهکار حساب ثبت / بستانکار مطالبات."""
    installments = list(pending_check_installments(sale))
    if not installments:
        return []

    if sale.order_status == Sale.ORDER_STATUS_CANCELLED:
        raise ValueError("سفارش لغو شده است.")

    receivables = get_account(ACCOUNT_SLUGS.RECEIVABLES, required=False)
    if not receivables:
        rc = code_for_slug(ACCOUNT_SLUGS.RECEIVABLES) or "1310"
        raise ValueError(f"حساب مطالبات ({rc}) یافت نشد.")

    now = timezone.now()
    registered = []

    for inst in installments:
        amount = Decimal(inst.amount or 0)
        if amount <= 0:
            continue
        desc = _check_description(inst, sale)
        lines = build_journal_lines(
            "check_register",
            amounts={"amount": amount},
            accounts={"registration_account": registration_account},
            description=desc,
        )
        journal = create_journal(
            lines=lines,
            entry_type="payment",
            description=desc,
            sale=sale,
            is_approved=True,
            entry_date=sale.sold_at,
        )
        inst.registration_account = registration_account
        inst.deposit_account = deposit_account
        inst.accounting_registered_at = now
        inst.accounting_entry = journal
        inst.save(
            update_fields=[
                "registration_account",
                "deposit_account",
                "accounting_registered_at",
                "accounting_entry",
            ]
        )
        registered.append(inst)

    from logic.sales import _sync_receivable_entry

    _sync_receivable_entry(sale)
    return registered


@transaction.atomic
def clear_registered_check(installment, recorded_by=None):
    """وصول چک ثبت‌شده — انتقال از حساب ثبت به حساب واریز."""
    if installment.payment_method != "check":
        raise ValueError("این قسط چک نیست.")
    if installment.status == "paid":
        raise ValueError("این قسط قبلاً پرداخت شده است.")
    if installment.status == "cancelled":
        raise ValueError("قسط لغوشده قابل پرداخت نیست.")
    if not installment.accounting_registered_at:
        raise ValueError("این چک هنوز در حسابداری ثبت نشده است.")

    sale = installment.sale
    if sale.order_status == Sale.ORDER_STATUS_CANCELLED:
        raise ValueError("این سفارش لغو شده و قابل پرداخت نیست.")

    amount = Decimal(installment.amount or 0)
    if amount <= 0:
        raise ValueError("مبلغ چک نامعتبر است.")

    reg_account = installment.registration_account or get_account(ACCOUNT_SLUGS.COLLECTION_AT_BANK)
    dep_account = installment.deposit_account or get_account(ACCOUNT_SLUGS.BANK)
    desc = _check_description(installment, sale).replace("ثبت چک", "وصول چک")

    lines = build_journal_lines(
        "check_clear",
        amounts={"amount": amount},
        accounts={
            "deposit_account": dep_account,
            "registration_account": reg_account,
        },
        description=desc,
    )
    create_journal(
        lines=lines,
        entry_type="payment",
        description=desc,
        sale=sale,
        is_approved=True,
    )

    sale.paid_amount += amount
    sale.payment_status = "paid" if sale.paid_amount >= sale.final_amount else "installment"
    sale.save(update_fields=["paid_amount", "payment_status"])

    from logic.sales import _apply_purchase_to_customer, _sync_receivable_entry

    _sync_receivable_entry(sale)
    _apply_purchase_to_customer(
        sale.customer,
        amount,
        sale.sold_at,
        reason="وصول چک",
        user=recorded_by,
        sale=sale,
    )

    installment.status = "paid"
    installment.paid_at = timezone.now()
    installment.save(update_fields=["status", "paid_at"])

    return installment
