"""منوی پنل — از MySQL."""

from django.core.cache import cache

from auth.permissions import PERMISSION_LABELS
from backend.models import MenuSection

CACHE_KEY = "menu_sections_v1"
CACHE_TTL = 60


def _invalidate_cache():
    cache.delete(CACHE_KEY)


def get_menu_sections(force_refresh=False):
    if not force_refresh:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached

    sections = []
    for sec in MenuSection.objects.filter(is_active=True).order_by("sort_order", "label"):
        sections.append(menu_section_to_dict(sec))

    cache.set(CACHE_KEY, sections, CACHE_TTL)
    return sections


def menu_section_to_dict(sec):
    menu_codes = list(sec.menu_permission_codes or [])
    section_codes = sorted(set(sec.section_permission_codes or []))
    return {
        "pk": sec.pk,
        "id": sec.section_id,
        "section_id": sec.section_id,
        "label": sec.label,
        "icon": sec.icon,
        "page_key": sec.page_key,
        "key": sec.page_key,
        "sort_order": sec.sort_order,
        "is_active": sec.is_active,
        "system_admin": sec.system_admin,
        "systemAdmin": sec.system_admin,
        "menu_permission_codes": menu_codes,
        "section_permission_codes": section_codes,
        "permission": menu_codes[0] if len(menu_codes) == 1 else None,
        "anyPermission": menu_codes if len(menu_codes) > 1 else None,
        "menu_permissions": [
            {"code": c, "label": PERMISSION_LABELS.get(c, c)} for c in menu_codes
        ],
        "section_permissions": [
            {"code": c, "label": PERMISSION_LABELS.get(c, c)} for c in section_codes
        ],
    }


def menu_sections_for_matrix(assignable_only=False, pool=None):
    from auth.permissions import ADMIN_ONLY_PERMISSIONS, ALL_PERMISSIONS, ASSIGNABLE_PERMISSIONS

    if pool is None:
        pool = ASSIGNABLE_PERMISSIONS if assignable_only else ALL_PERMISSIONS

    sections = []
    for sec in get_menu_sections():
        if assignable_only and sec["system_admin"]:
            continue
        menu_codes = [c for c in sec["menu_permission_codes"] if c in pool]
        section_codes = sorted(set(sec["section_permission_codes"]) & pool)
        if not menu_codes and not section_codes:
            continue
        sections.append({
            **sec,
            "menu_permission_codes": menu_codes,
            "section_permission_codes": section_codes,
            "menu_permissions": [
                {"code": c, "label": PERMISSION_LABELS.get(c, c)} for c in menu_codes
            ],
            "section_permissions": [
                {"code": c, "label": PERMISSION_LABELS.get(c, c)} for c in section_codes
            ],
        })
    return sections


def invalidate_menu_cache():
    _invalidate_cache()
