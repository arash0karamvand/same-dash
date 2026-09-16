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
    TRANSFER_FACTORY_ACCOUNTING_TO_OFFICE,
    VIEW_ACCOUNTING,
    VIEW_ATTENDANCE,
    VIEW_AUDIT_LOGS,
    VIEW_CUSTOMERS,
    VIEW_DASHBOARD,
    VIEW_EMPLOYEE_RANKING,
    VIEW_FACTORY_ORDERS,
    VIEW_FACTORY_ACCOUNTING,
    VIEW_FACTORY_PRODUCTS,
    VIEW_FREIGHT_ORDERS,
    VIEW_INSTALLMENTS,
    VIEW_LOYALTY,
    VIEW_RFM,
    MANAGE_RFM,
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
from backend.models import (
    AccountingMode,
    ApprovalStatus,
    AttendanceStatus,
    Branch,
    InstallmentStatus,
    JournalEntryStatus,
    JournalEntryType,
    LookupOption,
    MaterialStatus,
    MenuSection,
    OrderKind,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    OrgRank,
    Permission,
    RoleDefinition,
    SmsStatus,
    SmsType,
)

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
    ("workflow_stage", "in_warehouse", "در انبار", 6, {"color": "#64748b"}),
    ("workflow_stage", "ready_for_pickup", "آماده تحویل حضوری", 7, {"color": "#22c55e"}),
    ("workflow_stage", "merchant_assigned", "بازرگان — صف کارخانه", 8, {"color": "#a855f7"}),
    ("workflow_stage", "completed", "تکمیل شده", 9, {"color": "#10b981"}),
]

REFERENCE_ROWS = {
    PaymentMethod: [
        ("cash", "نقدی"), ("card", "کارت‌خوان"), ("check", "چک"),
    ],
    PaymentStatus: [("paid", "پرداخت‌شده"), ("unpaid", "پرداخت‌نشده"), ("installment", "قسطی")],
    OrderKind: [("normal", "فروش عادی"), ("pre_invoice", "پیش‌فاکتور"), ("deposit", "بیعانیه")],
    OrderStatus: [("confirmed", "تایید شده"), ("pending", "در انتظار"), ("cancelled", "لغو شده")],
    AccountingMode: [("automatic", "حسابداری خودکار"), ("manual", "حسابداری دستی")],
    InstallmentStatus: [("pending", "در انتظار"), ("paid", "پرداخت‌شده"), ("cancelled", "لغوشده")],
    AttendanceStatus: [("present", "حاضر"), ("absent", "غایب")],
    ApprovalStatus: [("pending", "در انتظار تایید"), ("approved", "تایید شده"), ("rejected", "رد شده")],
    MaterialStatus: [("pending", "در انتظار تایید اداری"), ("approved", "تایید شده"), ("rejected", "رد شده")],
    SmsStatus: [
        ("pending", "در صف"), ("sent", "ارسال شد"), ("failed", "ناموفق"),
        ("mock_sent", "شبیه‌سازی"), ("pending_provider_config", "در انتظار تنظیم درگاه"),
    ],
    SmsType: [
        ("manual", "دستی"), ("welcome", "خوش‌آمدگویی"), ("level_up", "ارتقای سطح"),
        ("promotion", "تبلیغاتی"), ("birthday", "تبریک تولد"), ("order_placed", "ثبت سفارش"),
        ("discount", "تخفیف ویژه"), ("reminder", "یادآوری باشگاه"),
        ("rfm", "بخش‌بندی RFM"),
    ],
    JournalEntryType: [
        ("manual", "دستی"), ("sale", "فروش"), ("receivable", "دریافتنی"),
        ("payment", "دریافت / پرداخت"), ("refund", "برگشت"),
        ("adjustment", "تعدیل"), ("other", "سایر"),
    ],
    JournalEntryStatus: [("draft", "پیش‌نویس"), ("posted", "ثبت قطعی"), ("void", "باطل")],
}

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
            VIEW_FACTORY_ACCOUNTING, TRANSFER_FACTORY_ACCOUNTING_TO_OFFICE,
            VIEW_CUSTOMERS, EDIT_CUSTOMER, VIEW_RFM, MANAGE_RFM, VIEW_PRODUCTS, MANAGE_PRODUCTS,
            VIEW_MATERIALS, CREATE_MATERIALS, APPROVE_MATERIALS,
            VIEW_FACTORY_ORDERS, VIEW_FREIGHT_ORDERS,
        ]),
    },
    {
        "slug": roles.SALES_EXPERT,
        "label": "کارشناس فروش",
        "description": "ثبت سفارش؛ تعداد فروش بدون مبلغ",
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
            branch, created = Branch.objects.update_or_create(
                code=spec["code"],
                defaults={
                    "label": spec["label"],
                    "color": spec.get("color", "#6366f1"),
                    "sort_order": spec.get("sort_order", 0),
                },
            )
            if created:
                branch.is_active = True
                branch.save(update_fields=["is_active"])
    except OperationalError:
        return


def seed_lookups():
    if not _table_exists(LookupOption):
        return
    try:
        for category, code, label, sort_order, meta in DEFAULT_LOOKUPS:
            opt, created = LookupOption.objects.update_or_create(
                category=category,
                code=code,
                defaults={
                    "label": label,
                    "sort_order": sort_order,
                    "meta": meta or {},
                },
            )
            if created:
                opt.is_active = True
                opt.save(update_fields=["is_active"])
    except OperationalError:
        return


def seed_reference_tables():
    for model, rows in REFERENCE_ROWS.items():
        if not _table_exists(model):
            continue
        for sort_order, (code, label) in enumerate(rows):
            model.objects.update_or_create(
                code=code,
                defaults={"label": label, "sort_order": sort_order, "is_active": True},
            )


def seed_menu_sections():
    if not _table_exists(MenuSection):
        return
    try:
        for sec in MENU_SECTIONS:
            existing_sort = (
                MenuSection.objects.filter(section_id=sec["id"])
                .values_list("sort_order", flat=True)
                .first()
            )
            menu_sec, created = MenuSection.objects.update_or_create(
                section_id=sec["id"],
                defaults={
                    "label": sec["label"],
                    "icon": sec.get("icon", "📄"),
                    "page_key": sec["page_key"],
                    "sort_order": existing_sort if existing_sort is not None else 0,
                    "system_admin": bool(sec.get("system_admin")),
                },
            )
            menu_permissions = [
                Permission.objects.get_or_create(
                    code=code, defaults={"label": PERMISSION_LABELS.get(code, code)}
                )[0]
                for code in sec.get("menu_permissions", [])
            ]
            section_permissions = [
                Permission.objects.get_or_create(
                    code=code, defaults={"label": PERMISSION_LABELS.get(code, code)}
                )[0]
                for code in sorted(set(sec.get("section_permissions", [])))
            ]
            menu_sec.menu_permissions.set(menu_permissions)
            menu_sec.section_permissions.set(section_permissions)
            if created:
                menu_sec.is_active = True
                menu_sec.save(update_fields=["is_active"])
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
            branch=None,
            defaults={"color": color, "sort_order": sort_order, "is_active": True},
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


def _spec_permissions(spec):
    slug = spec["slug"]
    if spec.get("grants_full_access"):
        return sanitize_role_permissions(slug, ALL_PERMISSIONS)
    return sanitize_role_permissions(slug, spec.get("permissions") or [])


def _permission_objects(perms):
    return [
        Permission.objects.get_or_create(
            code=code, defaults={"label": PERMISSION_LABELS.get(code, code)}
        )[0]
        for code in perms
    ]


def _is_locked_spec(spec):
    return bool(spec.get("is_locked") or spec.get("grants_full_access"))


def _sync_existing_role_structure(rd, spec, perms):
    """Keep structural flags; do not overwrite admin edits on unlocked roles."""
    updates = []
    if not rd.is_builtin:
        rd.is_builtin = True
        updates.append("is_builtin")
    locked = _is_locked_spec(spec)
    if locked and _column_exists("backend_roledefinition", "grants_full_access"):
        if spec.get("grants_full_access") and not rd.grants_full_access:
            rd.grants_full_access = True
            updates.append("grants_full_access")
        if spec.get("is_locked") and not rd.is_locked:
            rd.is_locked = True
            updates.append("is_locked")
    if updates:
        rd.save(update_fields=updates)
    if locked:
        rd.permission_set.set(_permission_objects(perms))


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
    created_slugs = set()
    for spec in ORG_BUILTIN_ROLES:
        slug = spec["slug"]
        if _is_role_suppressed(slug):
            continue

        parent = None
        parent_slug = spec.get("parent_slug")
        if parent_slug:
            parent = RoleDefinition.objects.filter(slug=parent_slug).first() or slug_to_parent.get(parent_slug)

        perms = _spec_permissions(spec)
        rd, created = RoleDefinition.objects.get_or_create(
            slug=slug,
            defaults=_role_defaults(spec, perms, parent),
        )
        if created:
            rd.permission_set.set(_permission_objects(perms))
            created_slugs.add(slug)
        else:
            _sync_existing_role_structure(rd, spec, perms)

        slug_to_parent[slug] = rd
        sync_group_for_role(slug)

    for spec in ORG_BUILTIN_ROLES:
        slug = spec["slug"]
        if slug not in created_slugs:
            continue
        parent_slug = spec.get("parent_slug")
        if parent_slug:
            parent = RoleDefinition.objects.filter(slug=parent_slug).first()
            if parent:
                child = RoleDefinition.objects.filter(slug=slug).first()
                if child and child.parent_id != parent.id:
                    child.parent = parent
                    child.save(update_fields=["parent"])


def seed_config_defaults():
    """همه تنظیمات داینامیک — idempotent."""
    seed_branches()
    seed_lookups()
    seed_reference_tables()
    seed_menu_sections()
    seed_org_ranks()
    seed_org_roles()
    try:
        for code, label in PERMISSION_LABELS.items():
            Permission.objects.filter(code=code).exclude(label=label).update(label=label)
    except OperationalError:
        pass
    try:
        from logic.order_cycle import seed_order_cycle

        seed_order_cycle()
    except Exception:
        pass
    try:
        from logic.rfm import seed_rfm_defaults

        seed_rfm_defaults()
    except Exception:
        pass


def permission_catalog():
    """کاتالوگ مجوزها برای UI."""
    from logic.module_catalog import module_tree_for_config

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
        "module_tree": module_tree_for_config(),
    }
