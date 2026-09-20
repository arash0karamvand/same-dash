"""وزن‌های رده‌بندی کارکنان — فروش، دریافت قبل از تحویل، تخفیف."""

from backend.models import LookupOption
from logic.lookups import invalidate_lookup_cache

SYSTEM_CATEGORY = "system"
RANKING_WEIGHTS_CODE = "ranking_weights"
DEFAULT_LABEL = "وزن‌های رده‌بندی کارکنان"

WEIGHT_KEYS = ("sales", "pre_delivery", "discount_percent", "discount_rial")
DEFAULT_WEIGHTS = {
    "sales": 100,
    "pre_delivery": 0,
    "discount_percent": 0,
    "discount_rial": 0,
}


def _option():
    return LookupOption.objects.filter(category=SYSTEM_CATEGORY, code=RANKING_WEIGHTS_CODE).first()


def _parse_weight(value, *, default=0):
    if value is None or value == "":
        return int(default)
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError) as exc:
        raise ValueError("وزن باید عدد باشد.") from exc
    if number < 0 or number > 100:
        raise ValueError("وزن باید بین ۰ تا ۱۰۰ باشد.")
    return number


def get_ranking_settings():
    opt = _option()
    meta = dict(opt.meta or {}) if opt else {}
    return {
        key: _parse_weight(meta.get(key), default=DEFAULT_WEIGHTS[key])
        for key in WEIGHT_KEYS
    }


def set_ranking_weights(data=None, **kwargs):
    payload = {}
    if isinstance(data, dict):
        payload.update(data)
    payload.update(kwargs)
    current = get_ranking_settings()
    meta = {
        key: _parse_weight(payload[key], default=current[key]) if key in payload else current[key]
        for key in WEIGHT_KEYS
    }
    opt, created = LookupOption.objects.get_or_create(
        category=SYSTEM_CATEGORY,
        code=RANKING_WEIGHTS_CODE,
        defaults={
            "label": DEFAULT_LABEL,
            "sort_order": 0,
            "is_active": True,
            "meta": meta,
        },
    )
    if not created:
        opt.label = DEFAULT_LABEL
        opt.meta = meta
        opt.is_active = True
        opt.save(update_fields=["label", "meta", "is_active"])
    invalidate_lookup_cache()
    return get_ranking_settings()
