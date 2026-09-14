"""نقش‌های قابل تنظیم در دیتابیس — همگام با گروه‌های Django."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from django.db.utils import OperationalError

from auth import roles
from auth.permissions import ROLE_PERMISSIONS, sanitize_role_permissions
from backend.models import LookupOption, Permission, RoleDefinition

SUPPRESSED_ROLE_CATEGORY = "suppressed_role"


def is_role_suppressed(slug):
    from django.db.utils import OperationalError, ProgrammingError

    try:
        return LookupOption.objects.filter(
            category=SUPPRESSED_ROLE_CATEGORY,
            code=slug,
            is_active=True,
        ).exists()
    except (OperationalError, ProgrammingError):
        return False


def suppress_role_slug(slug):
    """جلوگیری از بازساخت خودکار نقش پیش‌فرض حذف‌شده."""
    try:
        LookupOption.objects.update_or_create(
            category=SUPPRESSED_ROLE_CATEGORY,
            code=slug,
            defaults={
                "label": slug,
                "sort_order": 0,
                "is_active": True,
                "meta": {},
            },
        )
    except OperationalError:
        pass


def reassign_users_to_pending(slug):
    """کاربران نقش حذف‌شده را به pending منتقل کن."""
    _ensure_pending_group()
    try:
        group = Group.objects.filter(name=slug).first()
        if not group:
            return 0
        users = list(User.objects.filter(groups=group))
        for user in users:
            roles.assign_role(user, roles.PENDING)
        return len(users)
    except Exception:
        return 0


def delete_role_definition(rd):
    """حذف نقش، گروه Django و انتقال کاربران."""
    slug = rd.slug
    moved = reassign_users_to_pending(slug)
    if rd.is_builtin:
        suppress_role_slug(slug)
    Group.objects.filter(name=slug).delete()
    rd.delete()
    return moved

User = get_user_model()

LEGACY_BUILTIN_SLUGS = {
    roles.ACCOUNTANT,
    roles.SALES_MANAGER,
    roles.OPERATOR,
    roles.PENDING,
}


def _ensure_pending_group():
    Group.objects.get_or_create(name=roles.PENDING)


def remove_legacy_builtin_roles():
    _ensure_pending_group()
    pending_group = Group.objects.get(name=roles.PENDING)
    obsolete_defs = RoleDefinition.objects.filter(slug__in=LEGACY_BUILTIN_SLUGS, is_builtin=True)
    slugs = list(obsolete_defs.values_list("slug", flat=True))
    if not slugs:
        return

    for slug in slugs:
        try:
            group = Group.objects.get(name=slug)
        except Group.DoesNotExist:
            continue
        for user in User.objects.filter(groups=group):
            user.groups.remove(group)
            if roles.get_user_role(user) == roles.PENDING:
                user.groups.add(pending_group)
        group.delete()

    obsolete_defs.delete()


def seed_builtin_roles():
    """همگام‌سازی نقش‌ها — سازگار با migrationهای قدیمی."""
    try:
        remove_legacy_builtin_roles()
        _ensure_pending_group()
        from logic.config_seed import seed_config_defaults

        seed_config_defaults()

        for rd in RoleDefinition.objects.filter(is_builtin=False):
            cleaned = sanitize_role_permissions(rd.slug, rd.permissions or [])
            if cleaned != (rd.permissions or []):
                rd.permissions = cleaned
                rd.save()
            sync_group_for_role(rd.slug)
    except OperationalError:
        _ensure_pending_group()


def get_role_permissions(slug):
    if slug == roles.PENDING:
        return set()
    from auth.org_roles import is_full_access_role

    if is_full_access_role(slug):
        from auth.permissions import ALL_PERMISSIONS
        return set(ALL_PERMISSIONS)
    try:
        rd = RoleDefinition.objects.get(slug=slug)
        return set(rd.permissions or [])
    except RoleDefinition.DoesNotExist:
        return ROLE_PERMISSIONS.get(slug, set())


def role_definition_to_dict(rd):
    return {
        "slug": rd.slug,
        "label": rd.label,
        "description": rd.description,
        "permissions": rd.permissions or [],
        "is_builtin": rd.is_builtin,
        "needs_branch": rd.needs_branch,
        "grants_full_access": rd.grants_full_access,
        "is_locked": rd.is_locked,
        "color": rd.color,
        "sort_order": rd.sort_order,
        "parent_slug": rd.parent.slug if rd.parent_id else None,
    }


def sync_group_for_role(slug):
    Group.objects.get_or_create(name=slug)


def slugify_role(text):
    import re

    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    return text.strip("_")[:40] or "role"


def org_rank_to_dict(rank):
    return {
        "id": rank.id,
        "name": rank.name,
        "branch": rank.branch_id,
        "color": rank.color,
        "sort_order": rank.sort_order,
        "is_active": rank.is_active,
    }


def list_role_definitions():
    return RoleDefinition.objects.select_related("parent").order_by("sort_order")


def create_role_definition(data):
    from auth.permissions import ALL_PERMISSIONS, sanitize_role_permissions

    label = (data.get("label") or "").strip()
    if not label:
        raise ValueError("عنوان نقش الزامی است.")
    slug = (data.get("slug") or slugify_role(label)).strip()
    if RoleDefinition.objects.filter(slug=slug).exists():
        raise ValueError("این شناسه نقش قبلاً ثبت شده.")
    if slug == roles.ADMIN:
        raise PermissionError("نقش مدیر سیستم از این مسیر قابل ساخت نیست.")
    if slug in {roles.CEO, roles.CO_CEO, roles.BRANCH_SUPERVISOR, roles.ACCOUNTING_FINANCE, roles.SALES_EXPERT}:
        raise PermissionError("نقش‌های سازمانی پیش‌فرض از این مسیر قابل ساخت نیست.")

    perms = sanitize_role_permissions(slug, data.get("permissions") or [])
    invalid = set(perms) - ALL_PERMISSIONS
    if invalid:
        raise ValueError(f"مجوز نامعتبر: {', '.join(sorted(invalid))}")

    parent = None
    parent_slug = (data.get("parent_slug") or "").strip()
    if parent_slug:
        parent = RoleDefinition.objects.filter(slug=parent_slug).first()

    rd = RoleDefinition.objects.create(
        slug=slug,
        label=label,
        description=(data.get("description") or "").strip(),
        is_builtin=False,
        needs_branch=bool(data.get("needs_branch")),
        color=(data.get("color") or "#6366f1").strip()[:20],
        sort_order=int(data.get("sort_order") or 50),
        parent=parent,
    )
    rd.permission_set.set(
        [
            Permission.objects.get_or_create(code=code, defaults={"label": code})[0]
            for code in perms
        ]
    )
    sync_group_for_role(slug)
    return rd


def update_role_definition(rd, data):
    from auth.org_roles import is_locked_role
    from auth.permissions import ALL_PERMISSIONS, sanitize_role_permissions

    slug = rd.slug
    permission_codes = None
    if is_locked_role(slug):
        raise PermissionError("مجوزهای این نقش قابل تغییر نیست.")

    if "label" in data:
        rd.label = (data.get("label") or rd.label).strip()
    if "description" in data:
        rd.description = (data.get("description") or "").strip()
    if "permissions" in data:
        perms = sanitize_role_permissions(slug, data.get("permissions") or [])
        invalid = set(perms) - ALL_PERMISSIONS
        if invalid:
            raise ValueError(f"مجوز نامعتبر: {', '.join(sorted(invalid))}")
        permission_codes = perms
    if "needs_branch" in data:
        rd.needs_branch = bool(data.get("needs_branch"))
    if "color" in data:
        rd.color = (data.get("color") or rd.color).strip()[:20]
    if "sort_order" in data:
        rd.sort_order = int(data.get("sort_order") or rd.sort_order)
    if "parent_slug" in data:
        ps = (data.get("parent_slug") or "").strip()
        rd.parent = RoleDefinition.objects.filter(slug=ps).first() if ps else None
    rd.save()
    if permission_codes is not None:
        rd.permission_set.set(
            [
                Permission.objects.get_or_create(code=code, defaults={"label": code})[0]
                for code in permission_codes
            ]
        )
    sync_group_for_role(slug)
    return rd


def create_org_rank(data):
    from backend.models import OrgRank

    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("نام رتبه الزامی است.")
    return OrgRank.objects.create(
        name=name,
        branch_id=(data.get("branch") or "").strip() or None,
        color=(data.get("color") or "#6366f1").strip()[:20],
        sort_order=int(data.get("sort_order") or 0),
    )


def update_org_rank(rank, data):
    if "name" in data:
        rank.name = (data.get("name") or rank.name).strip()
    if "branch" in data:
        rank.branch_id = (data.get("branch") or "").strip() or None
    if "color" in data:
        rank.color = (data.get("color") or rank.color).strip()[:20]
    if "sort_order" in data:
        rank.sort_order = int(data.get("sort_order") or rank.sort_order)
    rank.save()
    return rank


def deactivate_org_rank(rank):
    rank.is_active = False
    rank.save(update_fields=["is_active"])
    return rank


def list_active_org_ranks():
    from backend.models import OrgRank

    return OrgRank.objects.filter(is_active=True).order_by("sort_order", "name")


def build_permission_matrix_payload():
    from auth.permissions import (
        ALL_PERMISSIONS,
        ASSIGNABLE_PERMISSIONS,
        PERMISSION_LABELS,
        menu_sections_for_matrix,
        permission_groups_for_matrix,
    )
    from logic.config_seed import seed_config_defaults
    from logic.module_catalog import portal_modules_for_matrix

    seed_builtin_roles()
    seed_config_defaults()
    return {
        "permissions": [
            {"code": code, "label": PERMISSION_LABELS.get(code, code)}
            for code in sorted(ALL_PERMISSIONS)
        ],
        "assignable_permissions": [
            {"code": code, "label": PERMISSION_LABELS.get(code, code)}
            for code in sorted(ASSIGNABLE_PERMISSIONS)
        ],
        "permission_groups": permission_groups_for_matrix(assignable_only=False),
        "assignable_permission_groups": permission_groups_for_matrix(assignable_only=True),
        "menu_sections": menu_sections_for_matrix(assignable_only=False),
        "assignable_menu_sections": menu_sections_for_matrix(assignable_only=True),
        "portal_modules": portal_modules_for_matrix(assignable_only=False),
        "assignable_portal_modules": portal_modules_for_matrix(assignable_only=True),
        "roles": [role_definition_to_dict(r) for r in RoleDefinition.objects.order_by("sort_order")],
    }
