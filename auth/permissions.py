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
VIEW_SALES_SUMMARY = "view_sales_summary"
APPROVE_SALE_BRANCH = "approve_sale_branch"
APPROVE_SALE_ACCOUNTING = "approve_sale_accounting"
VIEW_FACTORY_ORDERS = "view_factory_orders"
MANAGE_FACTORY_ORDERS = "manage_factory_orders"
VIEW_FREIGHT_ORDERS = "view_freight_orders"
MANAGE_FREIGHT_ORDERS = "manage_freight_orders"
VIEW_WAREHOUSE_ORDERS = "view_warehouse_orders"
MANAGE_WAREHOUSE_ORDERS = "manage_warehouse_orders"
VIEW_PICKUP_ORDERS = "view_pickup_orders"
MANAGE_PICKUP_ORDERS = "manage_pickup_orders"
VIEW_CYCLE_WATCH = "view_cycle_watch"

VIEW_ACCOUNTING = "view_accounting"
CREATE_ACCOUNTING = "create_accounting"
EDIT_ACCOUNTING = "edit_accounting"
DELETE_ACCOUNTING = "delete_accounting"
APPROVE_ACCOUNTING = "approve_accounting"
VIEW_FACTORY_ACCOUNTING = "view_factory_accounting"
CREATE_FACTORY_ACCOUNTING = "create_factory_accounting"
EDIT_FACTORY_ACCOUNTING = "edit_factory_accounting"
DELETE_FACTORY_ACCOUNTING = "delete_factory_accounting"
APPROVE_FACTORY_ACCOUNTING = "approve_factory_accounting"
TRANSFER_FACTORY_ACCOUNTING_TO_OFFICE = "transfer_factory_accounting_to_office"
VIEW_REPORTS = "view_reports"

VIEW_LOYALTY = "view_loyalty"
MANAGE_LOYALTY = "manage_loyalty"
RECALCULATE_LEVELS = "recalculate_levels"
VIEW_RFM = "view_rfm"
MANAGE_RFM = "manage_rfm"

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
VIEW_SELLERS = "view_sellers"
VIEW_MANAGERS = "view_managers"
MANAGE_MANAGERS = "manage_managers"
DELETE_MANAGERS = "delete_managers"
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
VIEW_FACTORY_PRODUCTS = "view_factory_products"
MANAGE_FACTORY_PRODUCTS = "manage_factory_products"
VIEW_MATERIALS = "view_materials"
CREATE_MATERIALS = "create_materials"
APPROVE_MATERIALS = "approve_materials"
MANAGE_MATERIALS = "manage_materials"
VIEW_FRAMES = "view_frames"
MANAGE_FRAMES = "manage_frames"

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
    VIEW_SALES_SUMMARY: "تعداد فروش بدون مبلغ",
    APPROVE_SALE_BRANCH: "ارسال به اداری (سرپرست شعبه)",
    APPROVE_SALE_ACCOUNTING: "تایید اداری و انتخاب مسیر ارسال",
    VIEW_FACTORY_ORDERS: "مشاهده سفارش‌های کارخانه",
    MANAGE_FACTORY_ORDERS: "مدیریت ساخت کارخانه",
    VIEW_FREIGHT_ORDERS: "مشاهده سفارش‌های باربری",
    MANAGE_FREIGHT_ORDERS: "مدیریت باربری",
    VIEW_WAREHOUSE_ORDERS: "مشاهده سفارش‌های انبار",
    MANAGE_WAREHOUSE_ORDERS: "تکمیل ارسال انبار",
    VIEW_PICKUP_ORDERS: "مشاهده تحویل حضوری",
    MANAGE_PICKUP_ORDERS: "تحویل حضوری به مشتری",
    VIEW_CYCLE_WATCH: "نظارت چرخه سفارش",
    DELETE_SALE: "حذف فروش",
    VIEW_ACCOUNTING: "مشاهده حسابداری",
    CREATE_ACCOUNTING: "ثبت سند حسابداری",
    EDIT_ACCOUNTING: "ویرایش سند حسابداری",
    DELETE_ACCOUNTING: "حذف سند حسابداری",
    APPROVE_ACCOUNTING: "تایید حسابداری",
    VIEW_FACTORY_ACCOUNTING: "مشاهده حسابداری کارخانه",
    CREATE_FACTORY_ACCOUNTING: "ثبت سند حسابداری کارخانه",
    EDIT_FACTORY_ACCOUNTING: "ویرایش سند حسابداری کارخانه",
    DELETE_FACTORY_ACCOUNTING: "حذف سند حسابداری کارخانه",
    APPROVE_FACTORY_ACCOUNTING: "تایید حسابداری کارخانه",
    TRANSFER_FACTORY_ACCOUNTING_TO_OFFICE: "انتقال سند کارخانه به حسابداری اداری",
    VIEW_REPORTS: "گزارش‌ها",
    VIEW_LOYALTY: "مشاهده باشگاه",
    MANAGE_LOYALTY: "مدیریت باشگاه",
    RECALCULATE_LEVELS: "بازمحاسبه سطح",
    VIEW_RFM: "مشاهده تحلیل RFM",
    MANAGE_RFM: "مدیریت قوانین RFM",
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
    VIEW_SELLERS: "مشاهده فروشندگان",
    VIEW_MANAGERS: "مشاهده مدیران",
    MANAGE_MANAGERS: "مدیریت مدیران",
    DELETE_MANAGERS: "حذف مدیر",
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
    VIEW_FACTORY_PRODUCTS: "مشاهده محصولات کارخانه",
    MANAGE_FACTORY_PRODUCTS: "مدیریت محصولات کارخانه",
    VIEW_MATERIALS: "مشاهده متریال",
    CREATE_MATERIALS: "ثبت متریال (کارخانه)",
    APPROVE_MATERIALS: "تایید و حذف متریال (اداری)",
    MANAGE_MATERIALS: "مدیریت کامل متریال",
    VIEW_FRAMES: "مشاهده کلاف‌ها",
    MANAGE_FRAMES: "مدیریت کلاف‌ها",
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
    VIEW_SALES_SUMMARY,
    APPROVE_SALE_BRANCH,
    APPROVE_SALE_ACCOUNTING,
    VIEW_FACTORY_ORDERS,
    MANAGE_FACTORY_ORDERS,
    VIEW_FREIGHT_ORDERS,
    MANAGE_FREIGHT_ORDERS,
    VIEW_WAREHOUSE_ORDERS,
    MANAGE_WAREHOUSE_ORDERS,
    VIEW_PICKUP_ORDERS,
    MANAGE_PICKUP_ORDERS,
    VIEW_CYCLE_WATCH,
    VIEW_ACCOUNTING,
    CREATE_ACCOUNTING,
    EDIT_ACCOUNTING,
    DELETE_ACCOUNTING,
    APPROVE_ACCOUNTING,
    VIEW_FACTORY_ACCOUNTING,
    CREATE_FACTORY_ACCOUNTING,
    EDIT_FACTORY_ACCOUNTING,
    DELETE_FACTORY_ACCOUNTING,
    APPROVE_FACTORY_ACCOUNTING,
    TRANSFER_FACTORY_ACCOUNTING_TO_OFFICE,
    VIEW_REPORTS,
    VIEW_LOYALTY,
    MANAGE_LOYALTY,
    RECALCULATE_LEVELS,
    VIEW_RFM,
    MANAGE_RFM,
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
    VIEW_SELLERS,
    VIEW_MANAGERS,
    MANAGE_MANAGERS,
    DELETE_MANAGERS,
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
    VIEW_FACTORY_PRODUCTS,
    MANAGE_FACTORY_PRODUCTS,
    VIEW_MATERIALS,
    CREATE_MATERIALS,
    APPROVE_MATERIALS,
    MANAGE_MATERIALS,
    VIEW_FRAMES,
    MANAGE_FRAMES,
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

# گروه‌بندی برای صفحه نقش‌ها و دسترسی‌ها
PERMISSION_GROUPS = [
    {
        "id": "customers",
        "label": "مشتریان",
        "permissions": [
            VIEW_CUSTOMERS,
            CREATE_CUSTOMER,
            EDIT_CUSTOMER,
            DELETE_CUSTOMER,
        ],
    },
    {
        "id": "workflow",
        "label": "گردش سفارش (فروشگاه / اداری / کارخانه)",
        "permissions": [
            VIEW_SALES,
            VIEW_SALES_SUMMARY,
            CREATE_SALE,
            EDIT_SALE,
            DELETE_SALE,
            APPROVE_SALE_BRANCH,
            APPROVE_SALE_ACCOUNTING,
            VIEW_FACTORY_ORDERS,
            MANAGE_FACTORY_ORDERS,
            VIEW_WAREHOUSE_ORDERS,
            MANAGE_WAREHOUSE_ORDERS,
            VIEW_PICKUP_ORDERS,
            MANAGE_PICKUP_ORDERS,
            VIEW_CYCLE_WATCH,
        ],
    },
    {
        "id": "sellers",
        "label": "فروشندگان",
        "permissions": [VIEW_SELLERS, MANAGE_STAFF, DELETE_STAFF],
    },
    {
        "id": "managers",
        "label": "مدیران",
        "permissions": [VIEW_MANAGERS, MANAGE_MANAGERS, DELETE_MANAGERS],
    },
    {
        "id": "attendance",
        "label": "حضور و غیاب",
        "permissions": [VIEW_ATTENDANCE, MANAGE_ATTENDANCE, SELF_CHECK_IN],
    },
    {
        "id": "accounting",
        "label": "حسابداری",
        "permissions": [
            VIEW_ACCOUNTING,
            CREATE_ACCOUNTING,
            EDIT_ACCOUNTING,
            DELETE_ACCOUNTING,
            APPROVE_ACCOUNTING,
            VIEW_FACTORY_ACCOUNTING,
            CREATE_FACTORY_ACCOUNTING,
            EDIT_FACTORY_ACCOUNTING,
            DELETE_FACTORY_ACCOUNTING,
            APPROVE_FACTORY_ACCOUNTING,
            TRANSFER_FACTORY_ACCOUNTING_TO_OFFICE,
            VIEW_REPORTS,
            VIEW_INSTALLMENTS,
            MANAGE_INSTALLMENTS,
        ],
    },
    {
        "id": "loyalty",
        "label": "باشگاه و RFM",
        "permissions": [
            VIEW_LOYALTY,
            MANAGE_LOYALTY,
            RECALCULATE_LEVELS,
            VIEW_RFM,
            MANAGE_RFM,
            MANAGE_REMINDERS,
        ],
    },
    {
        "id": "products",
        "label": "محصولات",
        "permissions": [
            VIEW_PRODUCTS,
            MANAGE_PRODUCTS,
            VIEW_FACTORY_PRODUCTS,
            MANAGE_FACTORY_PRODUCTS,
            VIEW_MATERIALS,
            CREATE_MATERIALS,
            APPROVE_MATERIALS,
            MANAGE_MATERIALS,
            VIEW_FRAMES,
            MANAGE_FRAMES,
        ],
    },
    {
        "id": "sms",
        "label": "پیامک",
        "permissions": [SEND_SMS, MANAGE_SMS_CLUB, MANAGE_BIRTHDAY_SMS, VIEW_SMS_LOGS],
    },
    {
        "id": "wallet",
        "label": "کیف پول",
        "permissions": [VIEW_WALLET, MANAGE_WALLET],
    },
    {
        "id": "system",
        "label": "سیستم",
        "permissions": [VIEW_DASHBOARD, VIEW_AUDIT_LOGS, VIEW_ORG_CHART],
    },
]


# بخش‌های منوی پنل — چهار پورتال اصلی
MENU_SECTIONS = [
    {
        "id": "managers",
        "label": "مدیران",
        "icon": "👔",
        "page_key": "managers",
        "menu_permissions": [VIEW_DASHBOARD],
        "section_permissions": [
            VIEW_DASHBOARD,
            MANAGE_USERS,
            MANAGE_ROLES,
            VIEW_ORG_CHART,
            MANAGE_ORG_RANKS,
            VIEW_MANAGERS,
            MANAGE_MANAGERS,
            DELETE_MANAGERS,
            VIEW_SELLERS,
            MANAGE_STAFF,
            DELETE_STAFF,
            VIEW_EMPLOYEE_RANKING,
            VIEW_ATTENDANCE,
            MANAGE_ATTENDANCE,
            SELF_CHECK_IN,
            VIEW_LOYALTY,
            MANAGE_LOYALTY,
            RECALCULATE_LEVELS,
            MANAGE_REMINDERS,
            SEND_SMS,
            MANAGE_SMS_CLUB,
            MANAGE_BIRTHDAY_SMS,
            VIEW_SMS_LOGS,
            VIEW_AUDIT_LOGS,
        ],
    },
    {
        "id": "shop",
        "label": "فروشگاه",
        "icon": "🏪",
        "page_key": "shop",
        "menu_permissions": [CREATE_SALE, APPROVE_SALE_BRANCH, VIEW_SALES_SUMMARY],
        "section_permissions": [
            VIEW_SALES,
            VIEW_SALES_SUMMARY,
            CREATE_SALE,
            EDIT_SALE,
            DELETE_SALE,
            APPROVE_SALE_BRANCH,
            VIEW_CUSTOMERS,
            CREATE_CUSTOMER,
            EDIT_CUSTOMER,
            DELETE_CUSTOMER,
            VIEW_WALLET,
            MANAGE_WALLET,
            VIEW_PRODUCTS,
            MANAGE_PRODUCTS,
        ],
    },
    {
        "id": "office",
        "label": "اداری",
        "icon": "🏢",
        "page_key": "office",
        "menu_permissions": [APPROVE_SALE_ACCOUNTING, VIEW_ACCOUNTING, VIEW_CUSTOMERS, VIEW_RFM, VIEW_FACTORY_ORDERS],
        "section_permissions": [
            APPROVE_SALE_ACCOUNTING,
            EDIT_SALE,
            VIEW_ACCOUNTING,
            CREATE_ACCOUNTING,
            EDIT_ACCOUNTING,
            DELETE_ACCOUNTING,
            APPROVE_ACCOUNTING,
            VIEW_REPORTS,
            VIEW_INSTALLMENTS,
            MANAGE_INSTALLMENTS,
            VIEW_CUSTOMERS,
            EDIT_CUSTOMER,
            VIEW_RFM,
            MANAGE_RFM,
            VIEW_PRODUCTS,
            MANAGE_PRODUCTS,
            VIEW_MATERIALS,
            VIEW_FACTORY_ORDERS,
            VIEW_FREIGHT_ORDERS,
            APPROVE_MATERIALS,
            VIEW_FRAMES,
            MANAGE_FRAMES,
            VIEW_WAREHOUSE_ORDERS,
            MANAGE_WAREHOUSE_ORDERS,
        ],
    },
    {
        "id": "factory",
        "label": "کارخانه",
        "icon": "🏭",
        "page_key": "factory",
        "menu_permissions": [VIEW_FACTORY_ORDERS],
        "section_permissions": [
            VIEW_FACTORY_ORDERS,
            MANAGE_FACTORY_ORDERS,
            VIEW_FACTORY_PRODUCTS,
            MANAGE_FACTORY_PRODUCTS,
            VIEW_MATERIALS,
            CREATE_MATERIALS,
            VIEW_FACTORY_ACCOUNTING,
            CREATE_FACTORY_ACCOUNTING,
            EDIT_FACTORY_ACCOUNTING,
            DELETE_FACTORY_ACCOUNTING,
            APPROVE_FACTORY_ACCOUNTING,
        ],
    },
]


from auth.org_roles import is_executive_user


def _accounting_active_office_sale(sale):
    """سفارش در صف اداری یا کارخانه (قبل از تکمیل نهایی)."""
    from backend.models import FactoryOrder, OfficeOrder

    office = OfficeOrder.objects.filter(source_sale=sale, is_deleted=False).first()
    if not office:
        return False
    if office.status == OfficeOrder.STATUS_PENDING:
        return True
    factory = FactoryOrder.objects.filter(source_sale=sale, is_deleted=False).first()
    if not factory:
        return office.status == OfficeOrder.STATUS_RELEASED
    return factory.workflow_stage != FactoryOrder.WORKFLOW_STAGE_COMPLETED


def menu_sections_for_matrix(assignable_only=False):
    """بخش‌های منو برای صفحه نقش‌ها — هم‌تراز با کاتالوگ ماژول."""
    from logic.module_catalog import portal_modules_for_matrix

    return portal_modules_for_matrix(assignable_only=assignable_only)


def permission_groups_for_matrix(assignable_only=False):
    """گروه‌های مجوز برای UI — با بخش «سایر» برای موارد بدون گروه."""
    pool = ASSIGNABLE_PERMISSIONS if assignable_only else ALL_PERMISSIONS
    grouped_codes = set()
    groups = []
    for group in PERMISSION_GROUPS:
        codes = [code for code in group["permissions"] if code in pool]
        grouped_codes.update(codes)
        if codes:
            groups.append(
                {
                    "id": group["id"],
                    "label": group["label"],
                    "permissions": [
                        {"code": code, "label": PERMISSION_LABELS.get(code, code)} for code in codes
                    ],
                }
            )
    other = sorted(pool - grouped_codes)
    if other:
        groups.append(
            {
                "id": "other",
                "label": "سایر",
                "permissions": [
                    {"code": code, "label": PERMISSION_LABELS.get(code, code)} for code in other
                ],
            }
        )
    return groups


def is_system_admin(user):
    """مدیر سیستم (نقش admin یا superuser)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) == ADMIN


def has_full_access(user):
    """مدیرعامل یا مدیر سیستم — دسترسی کامل."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    from auth.org_roles import is_full_access_role

    return is_full_access_role(get_user_role(user))


def sanitize_role_permissions(slug, permissions):
    """حذف مجوزهای مخصوص مدیر سیستم از نقش‌های غیر admin."""
    from auth.org_roles import is_full_access_role

    perms = set(permissions or []) & ALL_PERMISSIONS
    if slug == ADMIN or is_full_access_role(slug):
        return sorted(ALL_PERMISSIONS)
    return sorted(perms - ADMIN_ONLY_PERMISSIONS)


def get_user_extra_permissions(user):
    """مجوزهای اضافی تخصیص‌یافته مستقیم به کاربر."""
    from backend.models import UserAccessProfile

    try:
        profile = user.access_profile
    except UserAccessProfile.DoesNotExist:
        return set()
    return set(profile.extra_permissions or []) & ALL_PERMISSIONS


def sanitize_user_extra_permissions(permissions):
    """فقط مجوزهای قابل تخصیص — بدون مجوزهای مخصوص مدیر سیستم."""
    return sorted(set(permissions or []) & ASSIGNABLE_PERMISSIONS)


def get_effective_user_permissions(user):
    """مجوزهای مؤثر = نقش + اضافه‌های کاربر."""
    from logic.role_definitions import get_role_permissions

    if has_full_access(user):
        return ALL_PERMISSIONS
    role = get_user_role(user)
    if role == PENDING:
        base = set()
    else:
        base = set(get_role_permissions(role))
    extra = get_user_extra_permissions(user)
    try:
        from logic.order_cycle import extra_permissions_from_cycle

        extra = extra | extra_permissions_from_cycle(user)
    except Exception:
        pass
    return base | extra


def has_permission(user, permission):
    """بررسی مجوز کاربر برای یک عملیات."""
    if has_full_access(user):
        return True
    return permission in get_effective_user_permissions(user)


def can_edit_sale(user, sale):
    """اصلاح فقط در صف مسئولیت — مدیران همه."""
    from auth.org_roles import is_accounting_finance, is_branch_supervisor, is_executive_user
    from logic.sale_workflow import STAGE_BRANCH_APPROVED, STAGE_PENDING_BRANCH

    if sale.order_status == sale.ORDER_STATUS_CANCELLED:
        return False

    if is_executive_user(user) and has_permission(user, EDIT_SALE):
        return True

    if is_branch_supervisor(user) or (
        has_permission(user, APPROVE_SALE_BRANCH) and not is_executive_user(user)
    ):
        return (
            has_permission(user, EDIT_SALE)
            and sale.workflow_stage_id == STAGE_PENDING_BRANCH
        )

    if is_accounting_finance(user) or (
        has_permission(user, APPROVE_SALE_ACCOUNTING) and not is_executive_user(user)
    ):
        return (
            has_permission(user, EDIT_SALE) or has_permission(user, APPROVE_SALE_ACCOUNTING)
        ) and _accounting_active_office_sale(sale)

    if not has_permission(user, EDIT_SALE):
        return False
    if sale.workflow_stage_id not in {STAGE_PENDING_BRANCH, sale.WORKFLOW_STAGE_COMPLETED}:
        return False
    if sale.order_status == sale.ORDER_STATUS_CONFIRMED:
        return False
    return True


def can_view_sale(user, sale):
    """معلق‌ها فقط مدیران و مسئول همان مرحله."""
    from auth.org_roles import (
        is_accounting_finance,
        is_branch_supervisor,
        is_executive_user,
        is_factory_supervisor,
        is_freight_supervisor,
        sales_expert_summary_only,
    )
    from logic.sale_workflow import (
        STAGE_ACCOUNTING_APPROVED,
        STAGE_BRANCH_APPROVED,
        STAGE_IN_FREIGHT,
        STAGE_IN_PRODUCTION,
        STAGE_PENDING_BRANCH,
        STAGE_PRODUCTION_DONE,
    )
    from logic.sellers import effective_sale_branch, get_user_branch

    if is_executive_user(user):
        return True

    if sales_expert_summary_only(user):
        return False

    if is_accounting_finance(user) or (
        has_permission(user, APPROVE_SALE_ACCOUNTING) and not is_executive_user(user)
    ):
        return _accounting_active_office_sale(sale)

    if is_factory_supervisor(user) or (
        has_permission(user, VIEW_FACTORY_ORDERS) and not has_permission(user, APPROVE_SALE_ACCOUNTING)
    ):
        from backend.models import FactoryOrder

        return FactoryOrder.objects.filter(
            source_sale=sale,
            workflow_stage__in={
                FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
                FactoryOrder.WORKFLOW_STAGE_IN_PRODUCTION,
            },
        ).exists()

    if is_freight_supervisor(user) or has_permission(user, VIEW_FREIGHT_ORDERS):
        from backend.models import FactoryOrder
        from django.utils import timezone

        today = timezone.localdate()
        return FactoryOrder.objects.filter(
            source_sale=sale,
            delivery_date=today,
            workflow_stage__in={
                FactoryOrder.WORKFLOW_STAGE_PRODUCTION_DONE,
                FactoryOrder.WORKFLOW_STAGE_IN_FREIGHT,
            },
        ).exists()

    if is_branch_supervisor(user) or has_permission(user, APPROVE_SALE_BRANCH):
        branch = get_user_branch(user) or effective_sale_branch(user)
        if not branch or sale.branch_id != branch:
            return False
        return (
            sale.workflow_stage_id == STAGE_PENDING_BRANCH
        )

    return False
