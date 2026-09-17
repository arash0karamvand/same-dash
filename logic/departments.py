"""دپارتمان‌های سازمانی — همان چهار پورتال، به‌علاوه استخر بدون‌دسترسی."""

from auth import roles

DEPARTMENT_MANAGERS = "managers"
DEPARTMENT_SHOP = "shop"
DEPARTMENT_OFFICE = "office"
DEPARTMENT_FACTORY = "factory"

DEPARTMENTS = (
    {"id": DEPARTMENT_MANAGERS, "label": "مدیران"},
    {"id": DEPARTMENT_SHOP, "label": "فروشگاه"},
    {"id": DEPARTMENT_OFFICE, "label": "اداری"},
    {"id": DEPARTMENT_FACTORY, "label": "کارخانه"},
)

DEPARTMENT_IDS = frozenset(item["id"] for item in DEPARTMENTS)
DEPARTMENT_LABELS = {item["id"]: item["label"] for item in DEPARTMENTS}

NONE_DEPARTMENT = ""
NONE_DEPARTMENT_LABEL = "بدون دسترسی"

ROLE_DEPARTMENT = {
    roles.CEO: DEPARTMENT_MANAGERS,
    roles.ADMIN: DEPARTMENT_MANAGERS,
    roles.CO_CEO: DEPARTMENT_MANAGERS,
    roles.BRANCH_SUPERVISOR: DEPARTMENT_SHOP,
    roles.SALES_EXPERT: DEPARTMENT_SHOP,
    roles.SALES_MANAGER: DEPARTMENT_SHOP,
    roles.OPERATOR: DEPARTMENT_SHOP,
    roles.ACCOUNTING_FINANCE: DEPARTMENT_OFFICE,
    roles.ACCOUNTANT: DEPARTMENT_OFFICE,
    roles.FACTORY_SUPERVISOR: DEPARTMENT_FACTORY,
    roles.FREIGHT_SUPERVISOR: DEPARTMENT_FACTORY,
    roles.PENDING: NONE_DEPARTMENT,
}


def normalize_department(value, *, allow_empty=True):
    raw = (value or "").strip()
    if raw in {"none", "pending"}:
        raw = NONE_DEPARTMENT
    if not raw:
        if allow_empty:
            return NONE_DEPARTMENT
        raise ValueError("دپارتمان الزامی است.")
    if raw not in DEPARTMENT_IDS:
        raise ValueError("دپارتمان نامعتبر است.")
    return raw


def department_label(department_id):
    if not department_id:
        return NONE_DEPARTMENT_LABEL
    return DEPARTMENT_LABELS.get(department_id, NONE_DEPARTMENT_LABEL)


def department_for_role(slug):
    if not slug or slug == roles.PENDING:
        return NONE_DEPARTMENT
    mapped = ROLE_DEPARTMENT.get(slug)
    if mapped is not None:
        return mapped
    try:
        from backend.models import RoleDefinition

        rd = RoleDefinition.objects.filter(slug=slug).only("department").first()
        if rd:
            return normalize_department(rd.department, allow_empty=True)
    except Exception:
        pass
    return NONE_DEPARTMENT


def get_user_primary_department(user):
    try:
        profile = user.access_profile
    except Exception:
        profile = None
    stored = (getattr(profile, "primary_department", None) or "").strip()
    if stored in DEPARTMENT_IDS:
        return stored
    return department_for_role(roles.get_user_role(user))


def set_user_primary_department(user, department):
    from backend.models import UserAccessProfile

    department = normalize_department(department, allow_empty=True)
    profile, _ = UserAccessProfile.objects.get_or_create(user=user)
    if profile.primary_department != department:
        profile.primary_department = department
        profile.save(update_fields=["primary_department"])
    return department


def set_primary_department_from_role(user, role=None):
    role = role or roles.get_user_role(user)
    return set_user_primary_department(user, department_for_role(role))


def portal_permission_codes(portal_id):
    from logic.module_catalog import PORTAL_MODULE_SPECS

    codes = set()
    for portal in PORTAL_MODULE_SPECS:
        if portal["id"] != portal_id:
            continue
        for mod in portal.get("modules") or []:
            codes.update(mod.get("menu_permissions") or [])
            codes.update(mod.get("section_permissions") or [])
        break
    return codes


def portal_has_any_module(permissions, portal_id):
    from logic.module_catalog import PORTAL_MODULE_SPECS

    perms = set(permissions or [])
    for portal in PORTAL_MODULE_SPECS:
        if portal["id"] != portal_id:
            continue
        for mod in portal.get("modules") or []:
            codes = set(mod.get("menu_permissions") or []) | set(mod.get("section_permissions") or [])
            if codes and codes & perms:
                return True
        return False
    return False


def merge_portal_extras(current_extras, portal_id, selected):
    portal_codes = portal_permission_codes(portal_id)
    kept = [code for code in (current_extras or []) if code not in portal_codes]
    added = [code for code in (selected or []) if code in portal_codes]
    return sorted(set(kept) | set(added))


def accessible_departments(permissions):
    perms = set(permissions or [])
    return [
        {"id": item["id"], "label": item["label"]}
        for item in DEPARTMENTS
        if portal_has_any_module(perms, item["id"])
    ]


def users_in_department(department_id, *, exclude_user=None):
    """اعضای فعال دپارتمان با primary_department همان کد — بدون pending."""
    from django.contrib.auth import get_user_model

    department_id = normalize_department(department_id, allow_empty=False)
    User = get_user_model()
    qs = (
        User.objects.filter(is_active=True)
        .select_related("access_profile")
        .prefetch_related("groups")
        .exclude(groups__name=roles.PENDING)
    )
    if exclude_user is not None:
        qs = qs.exclude(pk=exclude_user.pk)
    return [user for user in qs if get_user_primary_department(user) == department_id]


def recipient_fields(user):
    department = get_user_primary_department(user)
    dept_label = department_label(department)
    role = roles.get_user_role(user)
    try:
        from backend.models import RoleDefinition

        rd = RoleDefinition.objects.filter(slug=role).only("label").first()
        role_label = rd.label if rd else roles.ROLE_LABELS.get(role, "")
    except Exception:
        role_label = roles.ROLE_LABELS.get(role, "")
    if not department:
        hint = NONE_DEPARTMENT_LABEL
    elif role_label:
        hint = f"{dept_label} / {role_label}"
    else:
        hint = dept_label
    return {
        "department": department,
        "department_label": dept_label,
        "role_label": role_label or "",
        "hint": hint,
    }


def assign_user_department(
    actor,
    target,
    *,
    department,
    mode="replace",
    role=None,
    branch=None,
    selected_permissions=None,
):
    """انتقال به دپارتمان — replace دسترسی را قطع می‌کند، keep نقش و extra را نگه می‌دارد."""
    from auth.permissions import (
        get_user_extra_permissions,
        has_full_access,
        is_system_admin,
        sanitize_user_extra_permissions,
    )
    from auth.views import apply_user_access, role_needs_branch, set_user_extra_permissions

    if target == actor:
        raise ValueError("نمی‌توانید دپارتمان خودتان را از اینجا تغییر دهید.")

    department = normalize_department(department, allow_empty=False)
    mode = (mode or "replace").strip()
    if mode not in ("replace", "keep"):
        raise ValueError("حالت تخصیص نامعتبر است.")

    if has_full_access(target):
        if department != DEPARTMENT_MANAGERS:
            raise ValueError("کاربران با دسترسی کامل فقط در دپارتمان مدیران می‌مانند.")
        if mode == "replace":
            raise ValueError("قطع دسترسی برای این کاربر مجاز نیست.")
        set_user_primary_department(target, department)
        return

    if mode == "replace":
        role = (role or "").strip()
        if not role:
            raise ValueError("انتخاب نقش الزامی است.")
        if role == roles.ADMIN and not is_system_admin(actor):
            raise PermissionError("فقط مدیر سیستم می‌تواند نقش مدیر سیستم بدهد.")
        role_dept = department_for_role(role)
        if role_dept and role_dept != department:
            raise ValueError("این نقش متعلق به دپارتمان انتخاب‌شده نیست.")
        from auth.branches import DEFAULT_BRANCH

        chosen = branch
        if role_needs_branch(role) and not chosen:
            profile = getattr(target, "staff_profile", None)
            chosen = profile.branch_id if profile else DEFAULT_BRANCH
        set_user_extra_permissions(target, [])
        apply_user_access(target, role, chosen if role_needs_branch(role) else None)
        set_user_primary_department(target, department)
        return

    extras = list(get_user_extra_permissions(target))
    selected = sanitize_user_extra_permissions(selected_permissions or [])
    if not portal_has_any_module(selected, department):
        raise ValueError("باید حتماً یکی را انتخاب کنی")
    set_user_extra_permissions(target, merge_portal_extras(extras, department, selected))
    set_user_primary_department(target, department)
