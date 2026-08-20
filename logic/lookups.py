"""گزینه‌های سیستم — از MySQL."""

from django.core.cache import cache

from backend.models import LookupOption

CACHE_KEY = "lookup_options_v1"
CACHE_TTL = 60

# دسته‌هایی که گزینه فرم نیستند و نباید در کش گزینه‌ها بیایند (مقدارشان حجیم است).
NON_CHOICE_CATEGORIES = ("branding",)


def _invalidate_cache():
    cache.delete(CACHE_KEY)


def get_all_lookups(force_refresh=False):
    if not force_refresh:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached

    grouped = {}
    options = (
        LookupOption.objects.filter(is_active=True)
        .exclude(category__in=NON_CHOICE_CATEGORIES)
        .order_by("category", "sort_order", "label")
    )
    for opt in options:
        grouped.setdefault(opt.category, []).append(lookup_to_dict(opt))

    cache.set(CACHE_KEY, grouped, CACHE_TTL)
    return grouped


def get_lookup_choices(category):
    return get_all_lookups().get(category, [])


def lookup_label(category, code):
    for item in get_lookup_choices(category):
        if item["code"] == code:
            return item["label"]
    return code or "—"


def valid_codes(category):
    return {item["code"] for item in get_lookup_choices(category)}


def normalize_code(category, code, default=None):
    code = (code or "").strip()
    valid = valid_codes(category)
    if code in valid:
        return code
    if default and default in valid:
        return default
    if valid:
        return sorted(valid)[0]
    return code


def lookup_to_dict(opt):
    return {
        "id": opt.id,
        "category": opt.category,
        "code": opt.code,
        "label": opt.label,
        "sort_order": opt.sort_order,
        "is_active": opt.is_active,
        "meta": opt.meta or {},
    }


def invalidate_lookup_cache():
    _invalidate_cache()


def list_lookups(category=""):
    qs = LookupOption.objects.order_by("category", "sort_order", "label")
    if category:
        qs = qs.filter(category=category)
    else:
        qs = qs.exclude(category__in=NON_CHOICE_CATEGORIES)
    return list(qs)


def create_lookup(*, category, code, label, sort_order=0, is_active=True, meta=None):
    category = (category or "").strip()
    code = (code or "").strip()
    label = (label or "").strip()
    if not category or not code or not label:
        raise ValueError("دسته، کد و عنوان الزامی است.")
    if LookupOption.objects.filter(category=category, code=code).exists():
        raise ValueError("این گزینه قبلاً ثبت شده.")
    opt = LookupOption.objects.create(
        category=category,
        code=code,
        label=label,
        sort_order=int(sort_order or 0),
        is_active=bool(is_active),
        meta=meta or {},
    )
    invalidate_lookup_cache()
    return opt


def update_lookup(opt, data):
    if "label" in data:
        opt.label = (data.get("label") or opt.label).strip()
    if "sort_order" in data:
        opt.sort_order = int(data.get("sort_order") or opt.sort_order)
    if "is_active" in data:
        opt.is_active = bool(data.get("is_active"))
    if "meta" in data:
        opt.meta = data.get("meta") or {}
    opt.save()
    invalidate_lookup_cache()
    return opt


def deactivate_lookup(opt):
    opt.is_active = False
    opt.save(update_fields=["is_active"])
    invalidate_lookup_cache()
    return opt
