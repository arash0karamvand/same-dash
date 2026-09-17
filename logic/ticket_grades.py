"""چهار درجه رنگی تیکت/مسئولیت سازمانی."""

import re

from backend.models import LookupOption
from logic.lookups import invalidate_lookup_cache

SYSTEM_CATEGORY = "system"
TICKET_GRADES_CODE = "ticket_grades"
HEX_COLOR = re.compile(r"^#([0-9a-fA-F]{6})$")

DEFAULT_TICKET_GRADES = [
    {"grade": 1, "label": "درجه ۱", "color": "#dc2626"},
    {"grade": 2, "label": "درجه ۲", "color": "#f59e0b"},
    {"grade": 3, "label": "درجه ۳", "color": "#2563eb"},
    {"grade": 4, "label": "درجه ۴", "color": "#64748b"},
]
DEFAULT_TICKET_GRADE = 3


def _normalize_color(value, fallback):
    raw = str(value or "").strip()
    if HEX_COLOR.match(raw):
        return raw.lower()
    return fallback


def _normalize_grades(raw_grades):
    incoming = {int(item.get("grade")): item for item in (raw_grades or []) if item.get("grade")}
    grades = []
    for spec in DEFAULT_TICKET_GRADES:
        item = incoming.get(spec["grade"]) or {}
        grades.append(
            {
                "grade": spec["grade"],
                "label": (item.get("label") or spec["label"]).strip() or spec["label"],
                "color": _normalize_color(item.get("color"), spec["color"]),
            }
        )
    return grades


def get_ticket_grades():
    opt = LookupOption.objects.filter(category=SYSTEM_CATEGORY, code=TICKET_GRADES_CODE).first()
    meta = (opt.meta if opt else None) or {}
    grades = _normalize_grades(meta.get("grades"))
    default_grade = int(meta.get("default_grade") or DEFAULT_TICKET_GRADE)
    if default_grade not in {item["grade"] for item in grades}:
        default_grade = DEFAULT_TICKET_GRADE
    return {"grades": grades, "default_grade": default_grade}


def grade_color(grade, settings=None):
    data = settings or get_ticket_grades()
    mapping = {item["grade"]: item["color"] for item in data["grades"]}
    try:
        key = int(grade)
    except (TypeError, ValueError):
        key = data["default_grade"]
    return mapping.get(key) or mapping[data["default_grade"]]


def set_ticket_grades(grades=None, default_grade=None, *, label="رنگ تیکت سازمانی"):
    current = get_ticket_grades()
    next_grades = _normalize_grades(grades if grades is not None else current["grades"])
    next_default = int(default_grade if default_grade is not None else current["default_grade"])
    if next_default not in {item["grade"] for item in next_grades}:
        next_default = DEFAULT_TICKET_GRADE
    meta = {"grades": next_grades, "default_grade": next_default}
    opt, created = LookupOption.objects.get_or_create(
        category=SYSTEM_CATEGORY,
        code=TICKET_GRADES_CODE,
        defaults={
            "label": label,
            "sort_order": 2,
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
    return get_ticket_grades()
