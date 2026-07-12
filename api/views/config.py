"""API تنظیمات داینامیک — شعب، گزینه‌ها، منو."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import is_system_admin
from backend.models import Branch, LookupOption, MenuSection
from logic.branches import branch_to_dict, get_active_branches, invalidate_branch_cache
from logic.config_seed import permission_catalog, seed_config_defaults
from logic.lookups import get_all_lookups, invalidate_lookup_cache, lookup_to_dict
from logic.menu_config import get_menu_sections, invalidate_menu_cache, menu_section_to_dict


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
    })


# --- Branches ---

@api_view("GET", "POST")
def branch_list(request):
    denied = _require_admin(request.user)
    if denied:
        return denied
    seed_config_defaults()

    if request.method == "GET":
        qs = Branch.objects.order_by("sort_order", "label")
        return success({"results": [branch_to_dict(b) for b in qs]})

    data = parse_json(request)
    code = (data.get("code") or "").strip()
    label = (data.get("label") or "").strip()
    if not code or not label:
        return fail("کد و نام شعبه الزامی است.", status=400)
    if Branch.objects.filter(code=code).exists():
        return fail("این کد شعبه قبلاً ثبت شده.", status=400)

    branch = Branch.objects.create(
        code=code,
        label=label,
        color=(data.get("color") or "#6366f1").strip()[:20],
        sort_order=int(data.get("sort_order") or 0),
        is_active=bool(data.get("is_active", True)),
    )
    invalidate_branch_cache()
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
        branch.is_active = False
        branch.save(update_fields=["is_active"])
        invalidate_branch_cache()
        return success({"deleted": True})

    data = parse_json(request)
    if "label" in data:
        branch.label = (data.get("label") or branch.label).strip()
    if "color" in data:
        branch.color = (data.get("color") or branch.color).strip()[:20]
    if "sort_order" in data:
        branch.sort_order = int(data.get("sort_order") or branch.sort_order)
    if "is_active" in data:
        branch.is_active = bool(data.get("is_active"))
    branch.save()
    invalidate_branch_cache()
    return success(branch_to_dict(branch))


# --- Lookups ---

@api_view("GET", "POST")
def lookup_list(request):
    denied = _require_admin(request.user)
    if denied:
        return denied
    seed_config_defaults()

    if request.method == "GET":
        category = (request.GET.get("category") or "").strip()
        qs = LookupOption.objects.order_by("category", "sort_order", "label")
        if category:
            qs = qs.filter(category=category)
        return success({"results": [lookup_to_dict(o) for o in qs]})

    data = parse_json(request)
    category = (data.get("category") or "").strip()
    code = (data.get("code") or "").strip()
    label = (data.get("label") or "").strip()
    if not category or not code or not label:
        return fail("دسته، کد و عنوان الزامی است.", status=400)
    if LookupOption.objects.filter(category=category, code=code).exists():
        return fail("این گزینه قبلاً ثبت شده.", status=400)

    opt = LookupOption.objects.create(
        category=category,
        code=code,
        label=label,
        sort_order=int(data.get("sort_order") or 0),
        is_active=bool(data.get("is_active", True)),
        meta=data.get("meta") or {},
    )
    invalidate_lookup_cache()
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
        opt.is_active = False
        opt.save(update_fields=["is_active"])
        invalidate_lookup_cache()
        return success({"deleted": True})

    data = parse_json(request)
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
    return success(lookup_to_dict(opt))


# --- Menu sections ---

@api_view("GET", "POST")
def menu_section_list(request):
    denied = _require_admin(request.user)
    if denied:
        return denied
    seed_config_defaults()

    if request.method == "GET":
        qs = MenuSection.objects.order_by("sort_order", "label")
        return success({"results": [menu_section_to_dict(s) for s in qs]})

    data = parse_json(request)
    section_id = (data.get("section_id") or "").strip()
    label = (data.get("label") or "").strip()
    page_key = (data.get("page_key") or "").strip()
    if not section_id or not label or not page_key:
        return fail("شناسه، عنوان و کلید صفحه الزامی است.", status=400)
    if MenuSection.objects.filter(section_id=section_id).exists():
        return fail("این شناسه بخش قبلاً ثبت شده.", status=400)

    sec = MenuSection.objects.create(
        section_id=section_id,
        label=label,
        page_key=page_key,
        icon=(data.get("icon") or "📄").strip()[:16],
        sort_order=int(data.get("sort_order") or 0),
        is_active=bool(data.get("is_active", True)),
        system_admin=bool(data.get("system_admin")),
        menu_permission_codes=data.get("menu_permission_codes") or [],
        section_permission_codes=data.get("section_permission_codes") or [],
    )
    invalidate_menu_cache()
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
        sec.is_active = False
        sec.save(update_fields=["is_active"])
        invalidate_menu_cache()
        return success({"deleted": True})

    data = parse_json(request)
    for field, key in [
        ("label", "label"), ("icon", "icon"), ("page_key", "page_key"),
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
        sec.menu_permission_codes = data.get("menu_permission_codes") or []
    if "section_permission_codes" in data:
        sec.section_permission_codes = data.get("section_permission_codes") or []
    sec.save()
    invalidate_menu_cache()
    return success(menu_section_to_dict(sec))
