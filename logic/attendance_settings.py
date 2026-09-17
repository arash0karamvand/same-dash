"""تنظیم اجبار حضورغیاب برای ثبت سفارش."""

from backend.models import LookupOption
from logic.lookups import invalidate_lookup_cache

SYSTEM_CATEGORY = "system"
ATTENDANCE_ENFORCED_CODE = "attendance_enforced"


def _option():
    return LookupOption.objects.filter(category=SYSTEM_CATEGORY, code=ATTENDANCE_ENFORCED_CODE).first()


def is_attendance_enforced():
    opt = _option()
    if opt is None:
        return True
    meta = opt.meta or {}
    if "enabled" in meta:
        return bool(meta.get("enabled"))
    return bool(opt.is_active)


def get_attendance_settings():
    return {"enforced": is_attendance_enforced()}


def set_attendance_enforced(enabled, *, label="اجبار حضورغیاب برای ثبت سفارش"):
    meta = {"enabled": bool(enabled)}
    opt, created = LookupOption.objects.get_or_create(
        category=SYSTEM_CATEGORY,
        code=ATTENDANCE_ENFORCED_CODE,
        defaults={
            "label": label,
            "sort_order": 0,
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
    return get_attendance_settings()
