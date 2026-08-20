"""برندینگ — لوگوی سایت که مدیر سیستم می‌تواند تغییر دهد.

لوگو به‌صورت data URL در LookupOption (دسته «branding») نگه داشته می‌شود تا
بدون نیاز به فضای ذخیره‌سازی فایل و تنظیمات MEDIA قابل تغییر باشد.
"""

from backend.models import LookupOption
from logic.lookups import invalidate_lookup_cache

BRANDING_CATEGORY = "branding"
LOGO_CODE = "logo"

# لوگوی پیش‌فرض داخل ui/public — وقتی چیزی آپلود نشده باشد.
DEFAULT_LOGO_URL = "/company_logo.png"

MAX_LOGO_BYTES = 1_500_000
ALLOWED_LOGO_TYPES = ("image/png", "image/jpeg", "image/webp", "image/svg+xml")


def _logo_option():
    return LookupOption.objects.filter(category=BRANDING_CATEGORY, code=LOGO_CODE).first()


def get_branding():
    """برندینگ فعلی برای پاسخ /api/config/."""
    opt = _logo_option()
    meta = (opt.meta or {}) if opt else {}
    data_url = (meta.get("data_url") or "").strip()
    return {
        "logo_url": data_url or DEFAULT_LOGO_URL,
        "logo_is_custom": bool(data_url),
        "logo_name": meta.get("file_name") or "",
        "logo_updated_at": meta.get("updated_at") or "",
    }


def _validate_data_url(data_url):
    data_url = (data_url or "").strip()
    if not data_url:
        raise ValueError("تصویر لوگو ارسال نشده است.")
    if not data_url.startswith("data:"):
        raise ValueError("فرمت تصویر نامعتبر است.")

    header, _, payload = data_url.partition(",")
    if not payload:
        raise ValueError("محتوای تصویر خالی است.")

    mime = header[5:].split(";")[0].strip().lower()
    if mime not in ALLOWED_LOGO_TYPES:
        raise ValueError("فقط تصویر PNG، JPEG، WebP یا SVG پذیرفته می‌شود.")
    if len(data_url.encode("utf-8")) > MAX_LOGO_BYTES:
        raise ValueError("حجم لوگو بیش از حد مجاز است (حداکثر حدود ۱ مگابایت).")

    return data_url


def set_logo(data_url, file_name="", updated_by=""):
    """ذخیره لوگوی جدید — data_url باید base64 معتبر باشد."""
    from django.utils import timezone

    data_url = _validate_data_url(data_url)
    meta = {
        "data_url": data_url,
        "file_name": (file_name or "").strip()[:120],
        "updated_at": timezone.now().isoformat(timespec="seconds"),
        "updated_by": (updated_by or "").strip()[:80],
    }
    opt, created = LookupOption.objects.get_or_create(
        category=BRANDING_CATEGORY,
        code=LOGO_CODE,
        defaults={"label": "لوگوی سایت", "meta": meta, "is_active": True},
    )
    if not created:
        opt.label = "لوگوی سایت"
        opt.meta = meta
        opt.is_active = True
        opt.save(update_fields=["label", "meta", "is_active"])
    invalidate_lookup_cache()
    return get_branding()


def reset_logo():
    """بازگشت به لوگوی پیش‌فرض پروژه."""
    opt = _logo_option()
    if opt:
        opt.delete()
        invalidate_lookup_cache()
    return get_branding()
