"""کمک‌تابع‌های مشترک تست."""

from django.contrib.auth.models import Group

from auth import roles
from backend.models import RoleDefinition
from logic.role_definitions import seed_builtin_roles, sync_group_for_role

# مجموعه مجوزهای نقش‌های legacy برای تست‌ها
OPERATOR_PERMISSIONS = sorted([
    "view_customers",
    "create_customer",
    "create_sale",
    "view_own_sales",
    "view_loyalty",
    "view_dashboard",
    "send_sms",
    "manage_sms_club",
    "view_sms_logs",
    "view_wallet",
    "manage_wallet",
    "view_products",
    "self_check_in",
])

SALES_MANAGER_PERMISSIONS = sorted([
    "view_customers",
    "create_customer",
    "edit_customer",
    "delete_customer",
    "view_sales",
    "create_sale",
    "edit_sale",
    "delete_sale",
    "view_loyalty",
    "manage_loyalty",
    "recalculate_levels",
    "send_sms",
    "manage_sms_club",
    "manage_birthday_sms",
    "view_sms_logs",
    "view_wallet",
    "manage_wallet",
    "view_dashboard",
    "view_installments",
    "manage_installments",
    "manage_staff",
    "view_products",
    "manage_products",
    "view_employee_ranking",
    "self_check_in",
])

ACCOUNTANT_PERMISSIONS = sorted([
    "view_customers",
    "view_sales",
    "view_accounting",
    "create_accounting",
    "edit_accounting",
    "delete_accounting",
    "approve_accounting",
    "view_reports",
    "view_loyalty",
    "view_installments",
    "manage_installments",
    "manage_staff",
    "view_dashboard",
    "send_sms",
    "manage_sms_club",
    "view_sms_logs",
    "view_wallet",
    "manage_wallet",
    "view_products",
    "self_check_in",
])


def ensure_test_role(slug, permissions, *, label=None, needs_branch=False, department=""):
    seed_builtin_roles()
    rd, _ = RoleDefinition.objects.update_or_create(
        slug=slug,
        defaults={
            "label": label or slug,
            "permissions": permissions,
            "is_builtin": False,
            "needs_branch": needs_branch,
            "department": department or "",
        },
    )
    sync_group_for_role(slug)
    return rd


def ensure_legacy_test_roles():
    ensure_test_role(roles.OPERATOR, OPERATOR_PERMISSIONS, label="فروشنده", needs_branch=True)
    ensure_test_role(roles.SALES_MANAGER, SALES_MANAGER_PERMISSIONS, label="مدیر فروش", needs_branch=True)
    ensure_test_role(roles.ACCOUNTANT, ACCOUNTANT_PERMISSIONS, label="حسابدار", needs_branch=True)
    Group.objects.get_or_create(name=roles.PENDING)
