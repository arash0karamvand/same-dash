"""Seed اولیه تنظیمات داینامیک — شعب، منو، گزینه‌ها، نقش‌ها."""

from django.db import connection
from django.db.utils import OperationalError

from auth import roles
from auth.permissions import (
    ALL_PERMISSIONS,
    APPROVE_ACCOUNTING,
    APPROVE_MATERIALS,
    APPROVE_SALE_ACCOUNTING,
    APPROVE_SALE_BRANCH,
    CREATE_ACCOUNTING,
    CREATE_CUSTOMER,
    CREATE_MATERIALS,
    CREATE_SALE,
    EDIT_ACCOUNTING,
    EDIT_CUSTOMER,
    EDIT_SALE,
    MANAGE_FACTORY_ORDERS,
    MANAGE_FREIGHT_ORDERS,
    MANAGE_FACTORY_PRODUCTS,
    MANAGE_MATERIALS,
    MANAGE_PRODUCTS,
    MENU_SECTIONS,
    PERMISSION_GROUPS,
    PERMISSION_LABELS,
    SEND_SMS,
    SELF_CHECK_IN,
    VIEW_ACCOUNTING,
    VIEW_ATTENDANCE,
    VIEW_AUDIT_LOGS,
    VIEW_CUSTOMERS,
    VIEW_DASHBOARD,
    VIEW_EMPLOYEE_RANKING,
    VIEW_FACTORY_ORDERS,
    VIEW_FACTORY_PRODUCTS,
    VIEW_FREIGHT_ORDERS,
    VIEW_INSTALLMENTS,
    VIEW_LOYALTY,
    VIEW_MANAGERS,
    VIEW_MATERIALS,
    VIEW_ORG_CHART,
    VIEW_OWN_SALES,
    VIEW_PRODUCTS,
    VIEW_REPORTS,
    VIEW_SALES,
    VIEW_SALES_SUMMARY,
    VIEW_SELLERS,
    VIEW_SMS_LOGS,
)
from auth.permissions import sanitize_role_permissions
from backend.models import Branch, LookupOption, MenuSection, OrgRank, RoleDefinition

DEFAULT_BRANCHES = [
    {"code": "branch_1", "label": "کمرد", "color": "#6366f1", "sort_order": 0},
    {"code": "branch_2", "label": "پاسداران", "color": "#10b981", "sort_order": 1},
]

DEFAULT_LOOKUPS = [
    ("payment_method", "cash", "نقدی", 0, {"color": "#10b981"}),
    ("payment_method", "card", "کارت‌خوان", 1, {"color": "#6366f1"}),
    ("payment_method", "check", "چک", 2, {"color": "#f59e0b"}),
    ("payment_status", "paid", "پرداخت‌شده", 0, {"color": "#10b981"}),
    ("payment_status", "unpaid", "پرداخت‌نشده", 1, {"color": "#ef4444"}),
    ("payment_status", "installment", "قسطی", 2, {"color": "#f59e0b"}),
    ("order_kind", "normal", "فروش عادی", 0, {}),
    ("order_kind", "pre_invoice", "پیش‌فاکتور (بیعانه + تایید/لغو)", 1, {}),
    ("order_kind", "deposit", "بیعانیه (پرداخت روز قبل تحویل)", 2, {}),
    ("order_status", "confirmed", "تایید شده", 0, {"color": "#10b981"}),
    ("order_status", "pending", "در انتظار", 1, {"color": "#f59e0b"}),
    ("order_status", "cancelled", "لغو شده", 2, {"color": "#94a3b8"}),
    ("discount_type", "percent", "درصدی", 0, {}),
    ("discount_type", "amount", "مبلغ ثابت", 1, {}),
    ("discount_type", "wallet", "موجودی حساب", 2, {}),
    ("staff_kind", "seller", "فروشنده", 0, {}),
    ("staff_kind", "manager", "مدیر", 1, {}),
    ("attendance_status", "present", "حاضر", 0, {}),
    ("attendance_status", "absent", "غایب", 1, {}),
    ("approval_status", "pending", "در انتظار", 0, {}),
    ("approval_status", "approved", "تایید شده", 1, {}),
    ("approval_status", "rejected", "رد شده", 2, {}),
    ("workflow_stage", "pending_branch", "صف فروشگاه", 0, {"color": "#f59e0b"}),
    ("workflow_stage", "branch_approved", "صف اداری", 1, {"color": "#6366f1"}),
    ("workflow_stage", "accounting_approved", "ارسال به کارخانه", 2, {"color": "#8b5cf6"}),
    ("workflow_stage", "in_production", "در حال ساخت", 3, {"color": "#0ea5e9"}),
    ("workflow_stage", "production_done", "آماده باربری", 4, {"color": "#14b8a6"}),
    ("workflow_stage", "in_freight", "در باربری", 5, {"color": "#f97316"}),
    ("workflow_stage", "completed", "تکمیل شده", 6, {"color": "#10b981"}),
]

ORG_BUILTIN_ROLES = [
    {
        "slug": roles.CEO,
        "label": "مدیرعامل (CEO)",
        "description": "دسترسی کامل به همه بخش‌ها",
        "parent_slug": None,
        "needs_branch": False,
        "color": "#b91c1c",
        "sort_order": 0,
        "grants_full_access": True,
        "is_locked": True,
    },
    {
        "slug": roles.ADMIN,
        "label": "مدیر سیستم",
        "description": "دسترسی کامل + مدیریت سیستم",
        "parent_slug": roles.CEO,
        "needs_branch": False,
        "color": "#ef4444",
        "sort_order": 1,
        "grants_full_access": True,
        "is_locked": True,
    },
    {
        "slug": roles.CO_CEO,
        "label": "معاون مدیرعامل",
        "description": "مشاهده حسابداری و دریافت گزارش‌ها (قابل تنظیم)",
        "parent_slug": roles.CEO,
        "needs_branch": False,
        "color": "#8b5cf6",
        "sort_order": 2,
        "permissions": sorted([
            VIEW_DASHBOARD, VIEW_ACCOUNTING, VIEW_REPORTS, VIEW_INSTALLMENTS, SEND_SMS,
            VIEW_SALES,
        ]),
    },
    {
        "slug": roles.BRANCH_SUPERVISOR,
        "label": "سرپرست شعبه",
        "description": "فروشگاه شعبه (کمرد/پاسداران) — ثبت و ارسال به اداری",
        "parent_slug": roles.CO_CEO,
        "needs_branch": True,
        "color": "#0ea5e9",
        "sort_order": 3,
        "permissions": sorted([
            VIEW_DASHBOARD, VIEW_CUSTOMERS, CREATE_CUSTOMER, CREATE_SALE, EDIT_SALE,
            APPROVE_SALE_BRANCH, VIEW_PRODUCTS, SELF_CHECK_IN,
        ]),
    },
    {
        "slug": roles.ACCOUNTING_FINANCE,
        "label": "اداری",
        "description": "بخش اداری — تایید حسابداری و ارسال به کارخانه",
        "parent_slug": roles.CO_CEO,
        "needs_branch": False,
        "color": "#10b981",
        "sort_order": 4,
        "permissions": sorted([
            VIEW_DASHBOARD, VIEW_ACCOUNTING, CREATE_ACCOUNTING, EDIT_ACCOUNTING,
            APPROVE_ACCOUNTING, APPROVE_SALE_ACCOUNTING, EDIT_SALE, VIEW_REPORTS, VIEW_INSTALLMENTS,
            VIEW_CUSTOMERS, EDIT_CUSTOMER, VIEW_PRODUCTS, MANAGE_PRODUCTS,
            VIEW_MATERIALS, CREATE_MATERIALS, APPROVE_MATERIALS,
            VIEW_FACTORY_ORDERS, VIEW_FREIGHT_ORDERS,
        ]),
    },
    {
        "slug": roles.SALES_EXPERT,
        "label": "کارشناس فروش",
        "description": "ثبت سفارش؛ فقط جمع فروش ماهانه",
        "parent_slug": roles.BRANCH_SUPERVISOR,
        "needs_branch": True,
        "color": "#6366f1",
        "sort_order": 5,
        "permissions": sorted([
            VIEW_DASHBOARD, VIEW_CUSTOMERS, CREATE_CUSTOMER, CREATE_SALE,
            VIEW_SALES_SUMMARY, VIEW_PRODUCTS, SELF_CHECK_IN,
        ]),
    },
    {
        "slug": roles.FACTORY_SUPERVISOR,
        "label": "سرپرست کارخانه",
        "description": "دریافت و ساخت سفارش — بدون قیمت",
        "parent_slug": roles.CO_CEO,
        "needs_branch": False,
        "color": "#78716c",
        "sort_order": 6,
        "permissions": sorted([
            VIEW_DASHBOARD, VIEW_FACTORY_ORDERS, MANAGE_FACTORY_ORDERS,
            VIEW_FACTORY_PRODUCTS, MANAGE_FACTORY_PRODUCTS,
            VIEW_MATERIALS, CREATE_MATERIALS,
        ]),
    },
    {
        "slug": roles.FREIGHT_SUPERVISOR,
        "label": "سرپرست باربری",
        "description": "فقط تحویل‌های امروز — اطلاعات مشتری بدون مبلغ",
        "parent_slug": roles.CO_CEO,
        "needs_branch": False,
        "color": "#ea580c",
        "sort_order": 7,
        "permissions": sorted([VIEW_DASHBOARD, VIEW_FREIGHT_ORDERS, MANAGE_FREIGHT_ORDERS]),
    },
]

ORG_RANKS = [
    ("مدیرعامل", "#b91c1c", 0),
    ("مدیر سیستم", "#ef4444", 1),
    ("معاون مدیرعامل", "#8b5cf6", 2),
    ("سرپرست شعبه", "#0ea5e9", 3),
    ("اداری", "#10b981", 4),
    ("کارشناس فروش", "#6366f1", 5),
    ("سرپرست کارخانه", "#78716c", 6),
    ("سرپرست باربری", "#ea580c", 7),
]


def _table_exists(model):
    try:
        return model._meta.db_table in connection.introspection.table_names()
    except Exception:
        return False


def seed_branches():
    if not _table_exists(Branch):
        return
    try:
        for spec in DEFAULT_BRANCHES:
            Branch.objects.update_or_create(
                code=spec["code"],
                defaults={
                    "label": spec["label"],
                    "color": spec.get("color", "#6366f1"),
                    "sort_order": spec.get("sort_order", 0),
                    "is_active": True,
                },
            )
    except OperationalError:
        return


def seed_lookups():
    if not _table_exists(LookupOption):
        return
    try:
        for category, code, label, sort_order, meta in DEFAULT_LOOKUPS:
            LookupOption.objects.update_or_create(
                category=category,
                code=code,
                defaults={
                    "label": label,
                    "sort_order": sort_order,
                    "is_active": True,
                    "meta": meta or {},
                },
            )
    except OperationalError:
        return


def seed_menu_sections():
    if not _table_exists(MenuSection):
        return
    try:
        for sec in MENU_SECTIONS:
            MenuSection.objects.update_or_create(
                section_id=sec["id"],
                defaults={
                    "label": sec["label"],
                    "icon": sec.get("icon", "📄"),
                    "page_key": sec["page_key"],
                    "sort_order": MenuSection.objects.filter(section_id=sec["id"]).values_list("sort_order", flat=True).first() or 0,
                    "is_active": True,
                    "system_admin": bool(sec.get("system_admin")),
                    "menu_permission_codes": list(sec.get("menu_permissions", [])),
                    "section_permission_codes": sorted(set(sec.get("section_permissions", []))),
                },
            )
        for idx, sec in enumerate(MENU_SECTIONS):
            MenuSection.objects.filter(section_id=sec["id"]).update(sort_order=idx)
        active_ids = {sec["id"] for sec in MENU_SECTIONS}
        MenuSection.objects.exclude(section_id__in=active_ids).update(is_active=False)
    except OperationalError:
        return


def seed_org_ranks():
    for name, color, sort_order in ORG_RANKS:
        OrgRank.objects.update_or_create(
            name=name,
            defaults={"color": color, "sort_order": sort_order, "is_active": True, "branch": ""},
        )


def _column_exists(table, column):
    try:
        with connection.cursor() as cursor:
            cols = [c.name for c in connection.introspection.get_table_description(cursor, table)]
        return column in cols
    except Exception:
        return False


def _role_defaults(spec, perms, parent):
    data = {
        "label": spec["label"],
        "description": spec.get("description") or "",
        "permissions": perms,
        "is_builtin": True,
        "needs_branch": bool(spec.get("needs_branch")),
        "color": spec.get("color") or "#6366f1",
        "sort_order": int(spec.get("sort_order") or 50),
        "parent": parent,
    }
    if _column_exists("backend_roledefinition", "grants_full_access"):
        data["grants_full_access"] = bool(spec.get("grants_full_access"))
        data["is_locked"] = bool(spec.get("is_locked"))
    return data


def _is_role_suppressed(slug):
    from django.db.utils import OperationalError, ProgrammingError

    try:
        return LookupOption.objects.filter(
            category="suppressed_role",
            code=slug,
            is_active=True,
        ).exists()
    except (OperationalError, ProgrammingError):
        return False


def seed_org_roles():
    from logic.role_definitions import sync_group_for_role

    slug_to_parent = {}
    for spec in ORG_BUILTIN_ROLES:
        slug = spec["slug"]
        if _is_role_suppressed(slug):
            continue
        if spec.get("grants_full_access"):
            perms = sanitize_role_permissions(slug, ALL_PERMISSIONS)
        else:
            perms = sanitize_role_permissions(slug, spec.get("permissions") or [])

        parent = None
        parent_slug = spec.get("parent_slug")
        if parent_slug:
            parent = RoleDefinition.objects.filter(slug=parent_slug).first() or slug_to_parent.get(parent_slug)

        rd, _ = RoleDefinition.objects.update_or_create(
            slug=slug,
            defaults=_role_defaults(spec, perms, parent),
        )
        slug_to_parent[slug] = rd
        sync_group_for_role(slug)

    for spec in ORG_BUILTIN_ROLES:
        parent_slug = spec.get("parent_slug")
        if parent_slug:
            parent = RoleDefinition.objects.filter(slug=parent_slug).first()
            if parent:
                RoleDefinition.objects.filter(slug=spec["slug"]).update(parent=parent)


def seed_config_defaults():
    """همه تنظیمات داینامیک — idempotent."""
    seed_branches()
    seed_lookups()
    seed_menu_sections()
    seed_org_ranks()
    seed_org_roles()


def permission_catalog():
    """کاتالوگ مجوزها برای UI."""
    return {
        "permissions": [
            {"code": code, "label": PERMISSION_LABELS.get(code, code)}
            for code in sorted(PERMISSION_LABELS)
        ],
        "permission_groups": [
            {
                "id": g["id"],
                "label": g["label"],
                "permissions": [
                    {"code": c, "label": PERMISSION_LABELS.get(c, c)} for c in g["permissions"]
                ],
            }
            for g in PERMISSION_GROUPS
        ],
    }
