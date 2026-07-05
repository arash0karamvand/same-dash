"""تعریف نقش‌ها و گروه‌های Django.

نقش پیش‌فرض:
    admin — مدیر سیستم (دسترسی کامل)

وضعیت بدون نقش:
    pending — بدون دسترسی تا تخصیص نقش توسط مدیر

سایر نقش‌ها توسط مدیر سیستم در پنل «نقش‌ها و دسترسی» ساخته می‌شوند.
"""

from django.contrib.auth.models import Group

ADMIN = "admin"
ACCOUNTANT = "accountant"
SALES_MANAGER = "sales_manager"
OPERATOR = "operator"
PENDING = "pending"

# ثابت‌های legacy — فقط برای سازگاری تست/مهاجرت.
LEGACY_ROLES = [ACCOUNTANT, SALES_MANAGER, OPERATOR]

ROLES = [ADMIN, PENDING, *LEGACY_ROLES]

ROLE_LABELS = {
    ADMIN: "مدیر سیستم",
    ACCOUNTANT: "حسابدار",
    SALES_MANAGER: "مدیر فروش",
    OPERATOR: "فروشنده",
    PENDING: "در انتظار تایید",
}

ROLE_DESCRIPTIONS = {
    ADMIN: "دسترسی کامل — کاربران، لاگ‌ها، حضور و همه ماژول‌ها",
    ACCOUNTANT: "حسابدار (نقش سفارشی)",
    SALES_MANAGER: "مدیر فروش (نقش سفارشی)",
    OPERATOR: "فروشنده (نقش سفارشی)",
    PENDING: "بدون دسترسی تا زمان تخصیص نقش توسط مدیر",
}

DEFAULT_ROLE = PENDING


def ensure_roles():
    """ایجاد گروه‌های نقش در دیتابیس (idempotent)."""
    try:
        from backend.models import RoleDefinition
        from logic.role_definitions import seed_builtin_roles

        seed_builtin_roles()
        for rd in RoleDefinition.objects.all():
            Group.objects.get_or_create(name=rd.slug)
    except Exception:
        Group.objects.get_or_create(name=ADMIN)
    Group.objects.get_or_create(name=PENDING)


def get_all_role_slugs():
    slugs = []
    try:
        from backend.models import RoleDefinition

        slugs = list(RoleDefinition.objects.values_list("slug", flat=True))
    except Exception:
        pass
    if PENDING not in slugs:
        slugs.append(PENDING)
    return slugs or [ADMIN, PENDING]


def assign_role(user, role):
    """تنظیم نقش کاربر (گروه‌های قبلی حذف و نقش جدید اعمال می‌شود)."""
    slugs = get_all_role_slugs()
    if role not in slugs and role != PENDING:
        raise ValueError("نقش نامعتبر است.")
    ensure_roles()
    user.groups.remove(*Group.objects.filter(name__in=slugs + LEGACY_ROLES))
    user.groups.add(Group.objects.get(name=role))
    user.is_staff = role == ADMIN
    user.save(update_fields=["is_staff"])
    return role


def get_user_role(user):
    """نقش فعلی کاربر."""
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return ADMIN
    user_groups = set(user.groups.values_list("name", flat=True))
    try:
        from backend.models import RoleDefinition

        for rd in RoleDefinition.objects.order_by("sort_order"):
            if rd.slug in user_groups:
                return rd.slug
    except Exception:
        pass
    if PENDING in user_groups:
        return PENDING
    for role in LEGACY_ROLES:
        if role in user_groups:
            return role
    return PENDING


def is_staff_user(user):
    """کاربر دارای نقش فعال (غیر از pending)."""
    role = get_user_role(user)
    return role is not None and role != PENDING


def has_role(user, *allowed_roles):
    """آیا نقش کاربر در میان نقش‌های مجاز است؟"""
    return get_user_role(user) in allowed_roles
