"""قفل سراسری تغییر دستی موجودی محصول."""

from backend.models import LookupOption
from logic.lookups import invalidate_lookup_cache

SYSTEM_CATEGORY = "system"
MANUAL_STOCK_LOCKED_CODE = "manual_stock_locked"
MANUAL_STOCK_LOCKED_MESSAGE = "تغییر دستی موجودی قفل است."


def _option():
    return LookupOption.objects.filter(category=SYSTEM_CATEGORY, code=MANUAL_STOCK_LOCKED_CODE).first()


def is_manual_stock_locked():
    opt = _option()
    if opt is None:
        return False
    meta = opt.meta or {}
    if "locked" in meta:
        return bool(meta.get("locked"))
    if "enabled" in meta:
        return bool(meta.get("enabled"))
    return bool(opt.is_active)


def get_inventory_settings():
    return {"manual_stock_locked": is_manual_stock_locked()}


def set_manual_stock_locked(locked, *, label="قفل تغییر دستی موجودی"):
    meta = {"locked": bool(locked)}
    opt, created = LookupOption.objects.get_or_create(
        category=SYSTEM_CATEGORY,
        code=MANUAL_STOCK_LOCKED_CODE,
        defaults={
            "label": label,
            "sort_order": 1,
            "is_active": True,
            "meta": meta,
        },
    )
    if not created:
        opt.label = label
        opt.meta = meta
        opt.is_active = True
        opt.save(update_fields=["label", "meta", "is_active"])
    invalidate_lookup_cache()
    return get_inventory_settings()


def assert_manual_stock_unlocked():
    if is_manual_stock_locked():
        raise ValueError(MANUAL_STOCK_LOCKED_MESSAGE)


def can_toggle_manual_stock_lock(user):
    """کاربرانی که پورتال مدیران را می‌بینند."""
    from logic.module_catalog import can_see_managers_portal

    return can_see_managers_portal(user)
