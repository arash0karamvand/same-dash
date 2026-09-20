"""تنظیم اجبار حضورغیاب و ساعت کاری سراسری."""

from datetime import datetime, timedelta

from backend.models import LookupOption
from logic.lookups import invalidate_lookup_cache

SYSTEM_CATEGORY = "system"
ATTENDANCE_ENFORCED_CODE = "attendance_enforced"
DEFAULT_LABEL = "اجبار حضورغیاب برای ثبت سفارش"


def _option():
    return LookupOption.objects.filter(category=SYSTEM_CATEGORY, code=ATTENDANCE_ENFORCED_CODE).first()


def _meta():
    opt = _option()
    return dict(opt.meta or {}) if opt else {}


def _parse_time(value):
    text = (value or "").strip() if isinstance(value, str) else ""
    if not text:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError("ساعت کاری نامعتبر است.")


def _format_time(value):
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value).strip()[:5]


def is_attendance_enforced():
    opt = _option()
    if opt is None:
        return True
    meta = opt.meta or {}
    if "enabled" in meta:
        return bool(meta.get("enabled"))
    return bool(opt.is_active)


def work_hours():
    meta = _meta()
    return _parse_time(meta.get("work_start")), _parse_time(meta.get("work_end"))


def work_day_hours():
    start, end = work_hours()
    if start is None or end is None:
        return None
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt = datetime.combine(today.date(), start)
    end_dt = datetime.combine(today.date(), end)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    hours = (end_dt - start_dt).total_seconds() / 3600
    if hours <= 0:
        return None
    return round(hours, 2)


def get_attendance_settings():
    start, end = work_hours()
    return {
        "enforced": is_attendance_enforced(),
        "work_start": _format_time(start),
        "work_end": _format_time(end),
        "work_day_hours": work_day_hours(),
    }


def _save_meta(meta, *, label=DEFAULT_LABEL):
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


def set_attendance_enforced(enabled, *, label=DEFAULT_LABEL):
    meta = _meta()
    meta["enabled"] = bool(enabled)
    return _save_meta(meta, label=label)


def set_attendance_work_hours(work_start=None, work_end=None, *, label=DEFAULT_LABEL):
    meta = _meta()
    if work_start is not None:
        parsed = _parse_time(work_start)
        meta["work_start"] = _format_time(parsed)
    if work_end is not None:
        parsed = _parse_time(work_end)
        meta["work_end"] = _format_time(parsed)
    start = _parse_time(meta.get("work_start"))
    end = _parse_time(meta.get("work_end"))
    if start and end and start == end:
        raise ValueError("شروع و پایان ساعت کاری نباید یکسان باشد.")
    return _save_meta(meta, label=label)
