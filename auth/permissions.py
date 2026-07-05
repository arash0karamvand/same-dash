"""ماتریس دسترسی نقش‌ها — تمام تصمیم‌های امنیتی سمت سرور."""

from auth.roles import (
    ADMIN,
    PENDING,
    get_user_role,
)

# نقش‌هایی که به شعبه نیاز دارند — از RoleDefinition.needs_branch خوانده می‌شود.
BRANCH_ROLES = set()

# --- مجوزهای ریز ---
VIEW_CUSTOMERS = "view_customers"
CREATE_CUSTOMER = "create_customer"
EDIT_CUSTOMER = "edit_customer"
DELETE_CUSTOMER = "delete_customer"

VIEW_SALES = "view_sales"
VIEW_OWN_SALES = "view_own_sales"
VIEW_EMPLOYEE_RANKING = "view_employee_ranking"
CREATE_SALE = "create_sale"
EDIT_SALE = "edit_sale"

VIEW_ACCOUNTING = "view_accounting"
CREATE_ACCOUNTING = "create_accounting"
EDIT_ACCOUNTING = "edit_accounting"
DELETE_ACCOUNTING = "delete_accounting"
APPROVE_ACCOUNTING = "approve_accounting"
VIEW_REPORTS = "view_reports"

VIEW_LOYALTY = "view_loyalty"
MANAGE_LOYALTY = "manage_loyalty"
RECALCULATE_LEVELS = "recalculate_levels"

SEND_SMS = "send_sms"
MANAGE_SMS_CLUB = "manage_sms_club"
MANAGE_BIRTHDAY_SMS = "manage_birthday_sms"
VIEW_SMS_LOGS = "view_sms_logs"
VIEW_WALLET = "view_wallet"
MANAGE_WALLET = "manage_wallet"
VIEW_DASHBOARD = "view_dashboard"
MANAGE_USERS = "manage_users"
DELETE_SALE = "delete_sale"
VIEW_ATTENDANCE = "view_attendance"
MANAGE_ATTENDANCE = "manage_attendance"
MANAGE_STAFF = "manage_staff"
DELETE_STAFF = "delete_staff"
SELF_CHECK_IN = "self_check_in"
VIEW_AUDIT_LOGS = "view_audit_logs"
VIEW_INSTALLMENTS = "view_installments"
MANAGE_INSTALLMENTS = "manage_installments"
MANAGE_ROLES = "manage_roles"
MANAGE_ORG_RANKS = "manage_org_ranks"
RESET_BUSINESS_DATA = "reset_business_data"
VIEW_ORG_CHART = "view_org_chart"
MANAGE_REMINDERS = "manage_reminders"
VIEW_PRODUCTS = "view_products"
MANAGE_PRODUCTS = "manage_products"

PERMISSION_LABELS = {
    VIEW_CUSTOMERS: "مشاهده مشتریان",
    CREATE_CUSTOMER: "ثبت مشتری",
    EDIT_CUSTOMER: "ویرایش مشتری",
    DELETE_CUSTOMER: "حذف مشتری",
    VIEW_SALES: "مشاهده همه فروش‌ها",
    VIEW_OWN_SALES: "مشاهده فروش خود (شعبه)",
    VIEW_EMPLOYEE_RANKING: "رده‌بندی کارکنان",
    CREATE_SALE: "ثبت فروش",
    EDIT_SALE: "ویرایش فروش",
    DELETE_SALE: "حذف فروش",
    VIEW_ACCOUNTING: "مشاهده حسابداری",
    CREATE_ACCOUNTING: "ثبت سند حسابداری",
    EDIT_ACCOUNTING: "ویرایش سند حسابداری",
    DELETE_ACCOUNTING: "حذف سند حسابداری",
    APPROVE_ACCOUNTING: "تایید حسابداری",
    VIEW_REPORTS: "گزارش‌ها",
    VIEW_LOYALTY: "مشاهده باشگاه",
    MANAGE_LOYALTY: "مدیریت باشگاه",
    RECALCULATE_LEVELS: "بازمحاسبه سطح",
    SEND_SMS: "ارسال پیامک",
    MANAGE_SMS_CLUB: "تنظیمات پیامک باشگاه",
    MANAGE_BIRTHDAY_SMS: "تنظیمات پیامک تولد",
    VIEW_SMS_LOGS: "مشاهده لاگ پیامک",
    VIEW_WALLET: "مشاهده کیف پول",
    MANAGE_WALLET: "مدیریت کیف پول",
    VIEW_DASHBOARD: "داشبورد",
    MANAGE_USERS: "مدیریت کاربران",
    VIEW_ATTENDANCE: "مشاهده حضور",
    MANAGE_ATTENDANCE: "مدیریت حضور",
    MANAGE_STAFF: "مدیریت فروشندگان",
    DELETE_STAFF: "حذف فروشنده",
    SELF_CHECK_IN: "ثبت حضور شخصی",
    VIEW_AUDIT_LOGS: "لاگ فعالیت",
    VIEW_INSTALLMENTS: "مشاهده اقساط",
    MANAGE_INSTALLMENTS: "مدیریت اقساط",
    MANAGE_ROLES: "مدیریت نقش‌ها و دسترسی",
    MANAGE_ORG_RANKS: "مدیریت رتبه سازمانی",
    RESET_BUSINESS_DATA: "پاکسازی داده‌های کسب‌وکار",
    VIEW_ORG_CHART: "چارت سازمانی",
    MANAGE_REMINDERS: "یادآوری دوره‌ای باشگاه",
    VIEW_PRODUCTS: "مشاهده محصولات",
    MANAGE_PRODUCTS: "مدیریت محصولات",
}

ALL_PERMISSIONS = {
    VIEW_CUSTOMERS,
    CREATE_CUSTOMER,
    EDIT_CUSTOMER,
    DELETE_CUSTOMER,
    VIEW_SALES,
    VIEW_OWN_SALES,
    VIEW_EMPLOYEE_RANKING,
    CREATE_SALE,
    EDIT_SALE,
    VIEW_ACCOUNTING,
    CREATE_ACCOUNTING,
    EDIT_ACCOUNTING,
    DELETE_ACCOUNTING,
    APPROVE_ACCOUNTING,
    VIEW_REPORTS,
    VIEW_LOYALTY,
    MANAGE_LOYALTY,
    RECALCULATE_LEVELS,
    SEND_SMS,
    MANAGE_SMS_CLUB,
    MANAGE_BIRTHDAY_SMS,
    VIEW_SMS_LOGS,
    VIEW_WALLET,
    MANAGE_WALLET,
    VIEW_DASHBOARD,
    MANAGE_USERS,
    DELETE_SALE,
    VIEW_ATTENDANCE,
    MANAGE_ATTENDANCE,
    MANAGE_STAFF,
    DELETE_STAFF,
    SELF_CHECK_IN,
    VIEW_AUDIT_LOGS,
    VIEW_INSTALLMENTS,
    MANAGE_INSTALLMENTS,
    MANAGE_ROLES,
    MANAGE_ORG_RANKS,
    RESET_BUSINESS_DATA,
    VIEW_ORG_CHART,
    MANAGE_REMINDERS,
    VIEW_PRODUCTS,
    MANAGE_PRODUCTS,
}

ROLE_PERMISSIONS = {
    ADMIN: ALL_PERMISSIONS,
    PENDING: set(),
}

# فقط مدیر سیستم — قابل تخصیص به نقش‌های دیگر نیست.
ADMIN_ONLY_PERMISSIONS = {
    MANAGE_ROLES,
    MANAGE_USERS,
    MANAGE_ORG_RANKS,
    RESET_BUSINESS_DATA,
}

ASSIGNABLE_PERMISSIONS = ALL_PERMISSIONS - ADMIN_ONLY_PERMISSIONS


def is_system_admin(user):
    """مدیر سیستم (نقش admin یا superuser)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) == ADMIN


def sanitize_role_permissions(slug, permissions):
    """حذف مجوزهای مخصوص مدیر سیستم از نقش‌های غیر admin."""
    perms = set(permissions or []) & ALL_PERMISSIONS
    if slug == ADMIN:
        return sorted(ALL_PERMISSIONS)
    return sorted(perms - ADMIN_ONLY_PERMISSIONS)


def has_permission(user, permission):
    """بررسی مجوز کاربر برای یک عملیات."""
    role = get_user_role(user)
    if role == ADMIN:
        return True
    from logic.role_definitions import get_role_permissions

    return permission in get_role_permissions(role)


def can_view_sale(user, sale):
    """آیا کاربر مجاز به مشاهده این فروش است؟"""
    if has_permission(user, VIEW_SALES):
        return True
    if has_permission(user, VIEW_OWN_SALES):
        from logic.sellers import effective_sale_branch

        branch = effective_sale_branch(user)
        if branch and sale.branch:
            return sale.branch == branch
        return sale.recorded_by_id == user.id
    return False
