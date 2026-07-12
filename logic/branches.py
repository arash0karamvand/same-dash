"""شعب — خواندن از MySQL با کش ساده."""

from django.core.cache import cache

from backend.models import Branch

CACHE_KEY = "active_branches_v1"
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
    }


def invalidate_branch_cache():
    _invalidate_cache()
