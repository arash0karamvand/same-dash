"""منطق دسترسی و کمک‌تابع‌های حسابداری."""

from backend.models import AccountingEntry

SYSTEM_ENTRY_TYPES = {"sale", "receivable", "payment"}


def is_system_entry(entry):
    return entry.sale_id is not None and entry.entry_type in SYSTEM_ENTRY_TYPES


def entry_permissions(entry):
    """سطح دسترسی ویرایش/حذف هر سند."""
    if entry.is_approved:
        return {"can_edit": False, "can_delete": True, "edit_mode": "none"}
    if is_system_entry(entry):
        return {"can_edit": True, "can_delete": True, "edit_mode": "partial"}
    return {"can_edit": True, "can_delete": True, "edit_mode": "full"}


def delete_entries_for_sale(sale):
    """حذف تمام اسناد حسابداری مرتبط با یک فروش."""
    deleted, _ = AccountingEntry.objects.filter(sale=sale).delete()
    return deleted
