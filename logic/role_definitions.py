"""نقش‌های قابل تنظیم در دیتابیس — همگام با گروه‌های Django."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from django.db.utils import OperationalError

from auth import roles
from auth.permissions import ROLE_PERMISSIONS, sanitize_role_permissions
from backend.models import LookupOption, RoleDefinition

SUPPRESSED_ROLE_CATEGORY = "suppressed_role"


def is_role_suppressed(slug):
    try:
        return LookupOption.objects.filter(
            category=SUPPRESSED_ROLE_CATEGORY,
            code=slug,
            is_active=True,
        ).exists()
    except OperationalError:
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
        from logic.config_seed import seed_org_ranks, seed_org_roles
        seed_org_ranks()
        seed_org_roles()

        for rd in RoleDefinition.objects.filter(is_builtin=False):
            cleaned = sanitize_role_permissions(rd.slug, rd.permissions or [])
            if cleaned != (rd.permissions or []):
                rd.permissions = cleaned
                rd.save(update_fields=["permissions"])
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
