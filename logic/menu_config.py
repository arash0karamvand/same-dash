"""منوی پنل — از MySQL."""

from django.core.cache import cache

from auth.permissions import PERMISSION_LABELS
from backend.models import MenuSection, Permission

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


def list_all_menu_sections():
    return list(MenuSection.objects.order_by("sort_order", "label"))


def create_menu_section(
    *,
    section_id,
    label,
    page_key,
    icon="📄",
    sort_order=0,
    is_active=True,
    system_admin=False,
    menu_permission_codes=None,
    section_permission_codes=None,
):
    section_id = (section_id or "").strip()
    label = (label or "").strip()
    page_key = (page_key or "").strip()
    if not section_id or not label or not page_key:
        raise ValueError("شناسه، عنوان و کلید صفحه الزامی است.")
    if MenuSection.objects.filter(section_id=section_id).exists():
        raise ValueError("این شناسه بخش قبلاً ثبت شده.")
    sec = MenuSection.objects.create(
        section_id=section_id,
        label=label,
        page_key=page_key,
        icon=(icon or "📄").strip()[:16],
        sort_order=int(sort_order or 0),
        is_active=bool(is_active),
        system_admin=bool(system_admin),
    )
    _set_permissions(sec.menu_permissions, menu_permission_codes or [])
    _set_permissions(sec.section_permissions, section_permission_codes or [])
    invalidate_menu_cache()
    return sec


def update_menu_section(sec, data):
    for field, key in [
        ("label", "label"),
        ("icon", "icon"),
        ("page_key", "page_key"),
    ]:
        if key in data:
            setattr(sec, field, (data.get(key) or getattr(sec, field)).strip())
    if "sort_order" in data:
        sec.sort_order = int(data.get("sort_order") or sec.sort_order)
    if "is_active" in data:
        sec.is_active = bool(data.get("is_active"))
    if "system_admin" in data:
        sec.system_admin = bool(data.get("system_admin"))
    if "menu_permission_codes" in data:
        _set_permissions(sec.menu_permissions, data.get("menu_permission_codes") or [])
    if "section_permission_codes" in data:
        _set_permissions(sec.section_permissions, data.get("section_permission_codes") or [])
    sec.save()
    invalidate_menu_cache()
    return sec


def _set_permissions(relation, codes):
    relation.set(
        [
            Permission.objects.get_or_create(
                code=code, defaults={"label": PERMISSION_LABELS.get(code, code)}
            )[0]
            for code in codes
        ]
    )


def deactivate_menu_section(sec):
    sec.is_active = False
    sec.save(update_fields=["is_active"])
    invalidate_menu_cache()
    return sec
