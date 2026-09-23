"""API تنظیمات داینامیک — شعب، گزینه‌ها، منو."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import is_system_admin
from backend.models import Branch, LookupOption, MenuSection
from logic.branding import get_branding, reset_logo, set_logo
from logic.branches import (
    branch_to_dict,
    create_branch,
    deactivate_branch,
    get_active_branches,
    list_all_branches,
    update_branch,
)
from logic.config_seed import permission_catalog, seed_config_defaults
from logic.lookups import (
    create_lookup,
    deactivate_lookup,
    get_all_lookups,
    list_lookups,
    lookup_to_dict,
    update_lookup,
)
from logic.menu_config import (
    create_menu_section,
    deactivate_menu_section,
    get_menu_sections,
    list_all_menu_sections,
    menu_section_to_dict,
    update_menu_section,
)
from logic.page_guides import get_page_guides_map, upsert_page_guide
from logic.attendance_settings import (
    get_attendance_settings,
    set_attendance_enforced,
    set_attendance_work_hours,
)
from logic.ranking_settings import get_ranking_settings, set_ranking_weights
from logic.ticket_grades import get_ticket_grades, set_ticket_grades
from logic.inventory_settings import (
    can_toggle_manual_stock_lock,
    get_inventory_settings,
    set_manual_stock_locked,
)
from logic.stock_locations import list_stock_locations


def _require_admin(user):
    if not is_system_admin(user):
        return fail("فقط مدیر سیستم مجاز است.", status=403)
    return None


@api_view("GET")
def app_config(request):
    """تنظیمات عمومی برای فرانت — کاربران احراز هویت‌شده."""
    if not request.user.is_authenticated:
        return fail("Unauthorized", status=401)
    seed_config_defaults()
    return success({
        "branches": get_active_branches(),
        "choices": get_all_lookups(),
        "nav_items": get_menu_sections(),
        "permission_catalog": permission_catalog(),
        "page_guides": get_page_guides_map(),
        "branding": get_branding(),
        "stock_locations": list_stock_locations(),
        "attendance_settings": get_attendance_settings(),
        "inventory_settings": get_inventory_settings(),
        "ticket_grades": get_ticket_grades(),
        "ranking_settings": get_ranking_settings(),
    })


@api_view("GET", "POST")
def branch_list(request):
    denied = _require_admin(request.user)
    if denied:
        return denied
    seed_config_defaults()

    if request.method == "GET":
        return success({"results": [branch_to_dict(b) for b in list_all_branches()]})

    data = parse_json(request)
    try:
        branch = create_branch(
            code=data.get("code"),
            label=data.get("label"),
            color=data.get("color") or "#6366f1",
            sort_order=data.get("sort_order") or 0,
            is_active=bool(data.get("is_active", True)),
            work_start=data.get("work_start"),
            work_end=data.get("work_end"),
            is_profit_center=data.get("is_profit_center", True),
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(branch_to_dict(branch), status=201)


@api_view("PUT", "DELETE")
def branch_detail(request, pk):
    denied = _require_admin(request.user)
    if denied:
        return denied
    try:
        branch = Branch.objects.get(pk=pk)
    except Branch.DoesNotExist:
        return fail("شعبه یافت نشد.", status=404)

    if request.method == "DELETE":
        deactivate_branch(branch)
        return success({"deleted": True})

    update_branch(branch, parse_json(request))
    return success(branch_to_dict(branch))


@api_view("GET", "POST")
def lookup_list(request):
    denied = _require_admin(request.user)
    if denied:
        return denied
    seed_config_defaults()

    if request.method == "GET":
        category = (request.GET.get("category") or "").strip()
        return success({"results": [lookup_to_dict(o) for o in list_lookups(category)]})

    data = parse_json(request)
    try:
        opt = create_lookup(
            category=data.get("category"),
            code=data.get("code"),
            label=data.get("label"),
            sort_order=data.get("sort_order") or 0,
            is_active=bool(data.get("is_active", True)),
            meta=data.get("meta") or {},
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(lookup_to_dict(opt), status=201)


@api_view("PUT", "DELETE")
def lookup_detail(request, pk):
    denied = _require_admin(request.user)
    if denied:
        return denied
    try:
        opt = LookupOption.objects.get(pk=pk)
    except LookupOption.DoesNotExist:
        return fail("گزینه یافت نشد.", status=404)

    if request.method == "DELETE":
        deactivate_lookup(opt)
        return success({"deleted": True})

    update_lookup(opt, parse_json(request))
    return success(lookup_to_dict(opt))


@api_view("GET", "POST")
def menu_section_list(request):
    denied = _require_admin(request.user)
    if denied:
        return denied
    seed_config_defaults()

    if request.method == "GET":
        return success({"results": [menu_section_to_dict(s) for s in list_all_menu_sections()]})

    data = parse_json(request)
    try:
        sec = create_menu_section(
            section_id=data.get("section_id"),
            label=data.get("label"),
            page_key=data.get("page_key"),
            icon=data.get("icon") or "📄",
            sort_order=data.get("sort_order") or 0,
            is_active=bool(data.get("is_active", True)),
            system_admin=bool(data.get("system_admin")),
            menu_permission_codes=data.get("menu_permission_codes") or [],
            section_permission_codes=data.get("section_permission_codes") or [],
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(menu_section_to_dict(sec), status=201)


@api_view("PUT", "DELETE")
def menu_section_detail(request, pk):
    denied = _require_admin(request.user)
    if denied:
        return denied
    try:
        sec = MenuSection.objects.get(pk=pk)
    except MenuSection.DoesNotExist:
        return fail("بخش منو یافت نشد.", status=404)

    if request.method == "DELETE":
        deactivate_menu_section(sec)
        return success({"deleted": True})

    update_menu_section(sec, parse_json(request))
    return success(menu_section_to_dict(sec))


@api_view("GET", "PUT", "DELETE")
def branding_logo(request):
    """لوگوی سایت — خواندن برای همه، تغییر فقط توسط مدیر سیستم."""
    if request.method == "GET":
        if not request.user.is_authenticated:
            return fail("Unauthorized", status=401)
        return success(get_branding())

    denied = _require_admin(request.user)
    if denied:
        return denied

    if request.method == "DELETE":
        return success(reset_logo())

    data = parse_json(request)
    try:
        branding = set_logo(
            data.get("data_url"),
            file_name=data.get("file_name") or "",
            updated_by=getattr(request.user, "username", ""),
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(branding)


@api_view("PUT")
def page_guide_detail(request, code):
    """ذخیره متن راهنمای یک صفحه — فقط مدیر سیستم."""
    denied = _require_admin(request.user)
    if denied:
        return denied
    data = parse_json(request)
    try:
        upsert_page_guide(code, data.get("text") or "")
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success({"code": code, "text": (data.get("text") or "").strip()})


@api_view("GET", "PUT")
def ranking_settings(request):
    if request.method == "GET":
        if not request.user.is_authenticated:
            return fail("Unauthorized", status=401)
        return success(get_ranking_settings())
    denied = _require_admin(request.user)
    if denied:
        return denied
    data = parse_json(request)
    try:
        return success(set_ranking_weights(data))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT")
def attendance_settings(request):
    if request.method == "GET":
        if not request.user.is_authenticated:
            return fail("Unauthorized", status=401)
        return success(get_attendance_settings())
    denied = _require_admin(request.user)
    if denied:
        return denied
    data = parse_json(request)
    try:
        if "enforced" in data or "enabled" in data:
            enabled = data.get("enforced")
            if enabled is None:
                enabled = data.get("enabled")
            set_attendance_enforced(bool(enabled))
        if "work_start" in data or "work_end" in data:
            set_attendance_work_hours(data.get("work_start"), data.get("work_end"))
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(get_attendance_settings())


@api_view("GET", "PUT")
def inventory_settings(request):
    if request.method == "GET":
        if not request.user.is_authenticated:
            return fail("Unauthorized", status=401)
        return success(get_inventory_settings())
    if not can_toggle_manual_stock_lock(request.user):
        return fail("Permission denied", status=403)
    data = parse_json(request)
    locked = data.get("manual_stock_locked")
    if locked is None:
        locked = data.get("locked")
    return success(set_manual_stock_locked(bool(locked)))


@api_view("GET", "PUT")
def ticket_grades(request):
    if request.method == "GET":
        if not request.user.is_authenticated:
            return fail("Unauthorized", status=401)
        return success(get_ticket_grades())
    denied = _require_admin(request.user)
    if denied:
        return denied
    data = parse_json(request)
    return success(
        set_ticket_grades(
            grades=data.get("grades"),
            default_grade=data.get("default_grade"),
        )
    )
