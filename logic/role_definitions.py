"""نقش‌های قابل تنظیم در دیتابیس — همگام با گروه‌های Django."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from auth import roles
from auth.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS, sanitize_role_permissions
from backend.models import RoleDefinition

User = get_user_model()

# نقش‌های پیش‌فرض قدیمی که دیگر seed نمی‌شوند.
LEGACY_BUILTIN_SLUGS = {
    roles.ACCOUNTANT,
    roles.SALES_MANAGER,
    roles.OPERATOR,
    roles.PENDING,
}


def _ensure_pending_group():
    Group.objects.get_or_create(name=roles.PENDING)


def remove_legacy_builtin_roles():
    """حذف نقش‌های پیش‌فرض قدیمی (غیر از admin) و انتقال کاربران به pending."""
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
    """فقط نقش مدیر سیستم پیش‌فرض است؛ بقیه توسط admin تعریف می‌شوند."""
    remove_legacy_builtin_roles()
    _ensure_pending_group()

    admin_meta = {
        "label": roles.ROLE_LABELS[roles.ADMIN],
        "description": roles.ROLE_DESCRIPTIONS[roles.ADMIN],
        "needs_branch": False,
        "color": "#ef4444",
        "sort_order": 0,
    }
    RoleDefinition.objects.update_or_create(
        slug=roles.ADMIN,
        defaults={
            "label": admin_meta["label"],
            "description": admin_meta["description"],
            "permissions": sanitize_role_permissions(roles.ADMIN, ALL_PERMISSIONS),
            "is_builtin": True,
            "needs_branch": admin_meta["needs_branch"],
            "color": admin_meta["color"],
            "sort_order": admin_meta["sort_order"],
        },
    )
    Group.objects.get_or_create(name=roles.ADMIN)

    for rd in RoleDefinition.objects.filter(is_builtin=False):
        cleaned = sanitize_role_permissions(rd.slug, rd.permissions or [])
        if cleaned != (rd.permissions or []):
            rd.permissions = cleaned
            rd.save(update_fields=["permissions"])
        sync_group_for_role(rd.slug)


def get_role_permissions(slug):
    if slug == roles.PENDING:
        return set()
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
        "color": rd.color,
        "sort_order": rd.sort_order,
        "parent_slug": rd.parent.slug if rd.parent_id else None,
    }


def sync_group_for_role(slug):
    Group.objects.get_or_create(name=slug)
