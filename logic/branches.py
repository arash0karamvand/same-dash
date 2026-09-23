"""شعب — خواندن از MySQL با کش ساده."""

from django.core.cache import cache

from backend.models import Branch

CACHE_KEY = "active_branches_v2"
CACHE_TTL = 60

FALLBACK_BRANCHES = [
    {"code": "branch_1", "label": "کمرد", "color": "#6366f1", "sort_order": 0},
    {"code": "branch_2", "label": "پاسداران", "color": "#10b981", "sort_order": 1},
]


def _invalidate_cache():
    cache.delete(CACHE_KEY)


def get_active_branches(force_refresh=False):
    if not force_refresh:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached

    qs = Branch.objects.filter(is_active=True).order_by("sort_order", "label")
    if qs.exists():
        data = [
            {
                "id": b.id,
                "code": b.code,
                "label": b.label,
                "color": b.color,
                "sort_order": b.sort_order,
                "work_start": b.work_start.strftime("%H:%M") if b.work_start else "",
                "work_end": b.work_end.strftime("%H:%M") if b.work_end else "",
                "is_profit_center": b.is_profit_center,
            }
            for b in qs
        ]
    else:
        data = [dict(x) for x in FALLBACK_BRANCHES]

    cache.set(CACHE_KEY, data, CACHE_TTL)
    return data


def branch_choices():
    return [(b["code"], b["label"]) for b in get_active_branches()]


def branch_labels():
    return {b["code"]: b["label"] for b in get_active_branches()}


def default_branch_code():
    branches = get_active_branches()
    return branches[0]["code"] if branches else "branch_1"


def normalize_branch_code(branch):
    code = (branch or "").strip()
    labels = branch_labels()
    if code in labels:
        return code
    return default_branch_code()


def branch_to_dict(branch):
    return {
        "id": branch.id,
        "code": branch.code,
        "label": branch.label,
        "color": branch.color,
        "sort_order": branch.sort_order,
        "is_active": branch.is_active,
        "work_start": branch.work_start.strftime("%H:%M") if branch.work_start else "",
        "work_end": branch.work_end.strftime("%H:%M") if branch.work_end else "",
        "is_profit_center": branch.is_profit_center,
    }


def invalidate_branch_cache():
    _invalidate_cache()


def list_all_branches():
    return list(Branch.objects.order_by("sort_order", "label"))


def create_branch(*, code, label, color="#6366f1", sort_order=0, is_active=True, work_start=None, work_end=None, is_profit_center=True):
    code = (code or "").strip()
    label = (label or "").strip()
    if not code or not label:
        raise ValueError("کد و نام شعبه الزامی است.")
    if Branch.objects.filter(code=code).exists():
        raise ValueError("این کد شعبه قبلاً ثبت شده.")
    branch = Branch.objects.create(
        code=code,
        label=label,
        color=(color or "#6366f1").strip()[:20],
        sort_order=int(sort_order or 0),
        is_active=bool(is_active),
        work_start=_parse_time(work_start),
        work_end=_parse_time(work_end),
        is_profit_center=bool(is_profit_center),
    )
    invalidate_branch_cache()
    return branch


def _parse_time(value):
    if not value:
        return None
    if hasattr(value, "hour"):
        return value
    text = str(value).strip()
    if not text:
        return None
    from datetime import datetime

    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError("ساعت کاری نامعتبر است.")


def update_branch(branch, data):
    if "label" in data:
        branch.label = (data.get("label") or branch.label).strip()
    if "color" in data:
        branch.color = (data.get("color") or branch.color).strip()[:20]
    if "sort_order" in data:
        branch.sort_order = int(data.get("sort_order") or branch.sort_order)
    if "is_active" in data:
        branch.is_active = bool(data.get("is_active"))
    if "work_start" in data:
        branch.work_start = _parse_time(data.get("work_start"))
    if "work_end" in data:
        branch.work_end = _parse_time(data.get("work_end"))
    if "is_profit_center" in data:
        branch.is_profit_center = bool(data.get("is_profit_center"))
    branch.save()
    invalidate_branch_cache()
    return branch


def deactivate_branch(branch):
    branch.is_active = False
    branch.save(update_fields=["is_active"])
    invalidate_branch_cache()
    return branch
