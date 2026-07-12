"""منطق دسترسی و کمک‌تابع‌های حسابداری."""

from django.db import transaction

from backend.models import AccountingEntry

SYSTEM_ENTRY_TYPES = {"sale", "receivable", "payment"}


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
        from logic.sales import reverse_payment

        reverse_payment(sale, amount, user=user)
        entry.delete()
        return {
            "deleted": True,
            "entry_id": entry_id,
            "sale_deleted": False,
            "sale_id": sale.id,
            "payment_reversed": int(amount or 0),
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
