"""کاتالوگ ماژولار پورتال‌ها — منبع واحد برای نقش‌ها و منو."""

from auth import permissions as P


def _mod(module_id, label, icon, page_key, menu_permissions, section_permissions, **extra):
    return {
        "id": module_id,
        "label": label,
        "icon": icon,
        "page_key": page_key,
        "menu_permissions": list(menu_permissions),
        "section_permissions": sorted(set(section_permissions)),
        **extra,
    }


def _notifications_mod(portal_id, nav_group=None):
    extra = {"nav_group": nav_group} if nav_group else {}
    return _mod(
        f"{portal_id}_notifications",
        "اعلان‌ها",
        "✉️",
        "notifications",
        [],
        [],
        **extra,
    )
PORTAL_MODULE_SPECS = [
    {
        "id": "managers",
        "label": "مدیران",
        "icon": "👔",
        "page_key": "managers",
        "default_page": "dashboard",
        "modules": [
            _mod(
                "managers_dashboard",
                "داشبورد",
                "📊",
                "dashboard",
                [P.VIEW_DASHBOARD],
                [P.VIEW_DASHBOARD],
                executive_only=True,
            ),
            _notifications_mod("managers"),
            _mod(
                "managers_orders",
                "صف ارسال به اداری",
                "📋",
                "orders",
                [P.VIEW_SALES, P.APPROVE_SALE_BRANCH],
                [P.VIEW_SALES, P.APPROVE_SALE_BRANCH, P.EDIT_SALE],
                executive_only=True,
            ),
            _mod(
                "managers_users",
                "کاربران",
                "🛡️",
                "users",
                [P.MANAGE_USERS],
                [P.MANAGE_USERS],
                system_admin=True,
            ),
            _mod(
                "managers_roles",
                "نقش‌ها و دسترسی",
                "🔐",
                "roles",
                [P.MANAGE_ROLES],
                [P.MANAGE_ROLES],
                system_admin=True,
            ),
            _mod(
                "managers_settings",
                "تنظیمات سیستم",
                "⚙️",
                "settings",
                [P.MANAGE_USERS],
                [P.MANAGE_USERS],
                system_admin=True,
            ),
            _mod(
                "managers_cycle",
                "چرخه",
                "🔁",
                "cycle",
                [P.MANAGE_USERS],
                [P.MANAGE_USERS],
                system_admin=True,
            ),
            _mod(
                "managers_cycle_watch",
                "نظارت چرخه",
                "👁️",
                "cycle-watch",
                [P.VIEW_CYCLE_WATCH],
                [P.VIEW_CYCLE_WATCH],
                cycle_watch=True,
            ),
            _mod(
                "managers_orgchart",
                "چارت سازمانی",
                "🏢",
                "orgchart",
                [P.VIEW_ORG_CHART],
                [P.VIEW_ORG_CHART, P.MANAGE_ORG_RANKS],
            ),
            _mod(
                "managers_managers",
                "مدیران پرسنل",
                "👥",
                "managers",
                [P.VIEW_MANAGERS, P.MANAGE_MANAGERS],
                [P.VIEW_MANAGERS, P.MANAGE_MANAGERS, P.DELETE_MANAGERS],
            ),
            _mod(
                "managers_sellers",
                "فروشندگان",
                "🧑‍💼",
                "sellers",
                [P.VIEW_SELLERS, P.MANAGE_STAFF],
                [P.VIEW_SELLERS, P.MANAGE_STAFF, P.DELETE_STAFF],
            ),
            _mod(
                "managers_ranking",
                "رده‌بندی کارکنان",
                "🏆",
                "ranking",
                [P.VIEW_EMPLOYEE_RANKING],
                [P.VIEW_EMPLOYEE_RANKING],
            ),
            _mod(
                "managers_attendance",
                "حضور و غیاب",
                "📅",
                "attendance",
                [P.VIEW_ATTENDANCE],
                [P.VIEW_ATTENDANCE, P.MANAGE_ATTENDANCE, P.SELF_CHECK_IN],
            ),
            _mod(
                "managers_rfm",
                "تحلیل RFM",
                "📊",
                "rfm",
                [
                    P.VIEW_RFM,
                    P.VIEW_LOYALTY,
                    P.SEND_SMS,
                    P.VIEW_SMS_LOGS,
                    P.MANAGE_SMS_CLUB,
                    P.MANAGE_BIRTHDAY_SMS,
                    P.MANAGE_REMINDERS,
                ],
                [
                    P.VIEW_RFM,
                    P.MANAGE_RFM,
                    P.VIEW_LOYALTY,
                    P.MANAGE_LOYALTY,
                    P.RECALCULATE_LEVELS,
                    P.SEND_SMS,
                    P.MANAGE_SMS_CLUB,
                    P.MANAGE_BIRTHDAY_SMS,
                    P.VIEW_SMS_LOGS,
                    P.MANAGE_REMINDERS,
                ],
            ),
            _mod(
                "managers_logs",
                "لاگ‌ها",
                "📜",
                "logs",
                [P.VIEW_AUDIT_LOGS],
                [P.VIEW_AUDIT_LOGS],
            ),
            _mod(
                "managers_filter",
                "فیلتر",
                "🔍",
                "filter",
                [P.VIEW_DASHBOARD, P.VIEW_AUDIT_LOGS],
                [P.VIEW_DASHBOARD, P.VIEW_AUDIT_LOGS],
            ),
        ],
    },
    {
        "id": "shop",
        "label": "فروشگاه",
        "icon": "🏪",
        "page_key": "shop",
        "default_page": "shop",
        "modules": [
            _notifications_mod("shop"),
            _mod(
                "shop_orders",
                "سفارش‌ها",
                "🧾",
                "shop",
                [P.CREATE_SALE, P.APPROVE_SALE_BRANCH, P.VIEW_SALES_SUMMARY, P.VIEW_SALES],
                [
                    P.VIEW_SALES,
                    P.VIEW_SALES_SUMMARY,
                    P.CREATE_SALE,
                    P.EDIT_SALE,
                    P.DELETE_SALE,
                    P.APPROVE_SALE_BRANCH,
                ],
            ),
            _mod(
                "shop_customers",
                "مشتریان",
                "👥",
                "customers",
                [P.VIEW_CUSTOMERS],
                [
                    P.VIEW_CUSTOMERS,
                    P.CREATE_CUSTOMER,
                    P.EDIT_CUSTOMER,
                    P.DELETE_CUSTOMER,
                    P.VIEW_WALLET,
                    P.MANAGE_WALLET,
                ],
            ),
            _mod(
                "shop_products",
                "محصولات",
                "📦",
                "products",
                [P.VIEW_PRODUCTS],
                [P.VIEW_PRODUCTS, P.MANAGE_PRODUCTS],
            ),
            _mod(
                "shop_pickup",
                "تحویل حضوری",
                "🏪",
                "pickup",
                [P.VIEW_PICKUP_ORDERS, P.MANAGE_PICKUP_ORDERS, P.CREATE_SALE, P.APPROVE_SALE_BRANCH],
                [P.VIEW_PICKUP_ORDERS, P.MANAGE_PICKUP_ORDERS, P.CREATE_SALE, P.APPROVE_SALE_BRANCH],
            ),
        ],
    },
    {
        "id": "office",
        "label": "اداری",
        "icon": "🏢",
        "page_key": "office",
        "default_page": "office",
        "modules": [
            _notifications_mod("office", "CRM"),
            _mod(
                "office_customers",
                "مشتریان",
                "👥",
                "customers",
                [P.VIEW_CUSTOMERS],
                [P.VIEW_CUSTOMERS, P.EDIT_CUSTOMER, P.CREATE_CUSTOMER],
                nav_group="CRM",
            ),
            _mod(
                "office_rfm",
                "تحلیل RFM",
                "📊",
                "rfm",
                [
                    P.VIEW_RFM,
                    P.VIEW_LOYALTY,
                    P.SEND_SMS,
                    P.VIEW_SMS_LOGS,
                    P.MANAGE_SMS_CLUB,
                    P.MANAGE_BIRTHDAY_SMS,
                    P.MANAGE_REMINDERS,
                ],
                [
                    P.VIEW_RFM,
                    P.MANAGE_RFM,
                    P.VIEW_LOYALTY,
                    P.MANAGE_LOYALTY,
                    P.RECALCULATE_LEVELS,
                    P.SEND_SMS,
                    P.MANAGE_SMS_CLUB,
                    P.MANAGE_BIRTHDAY_SMS,
                    P.VIEW_SMS_LOGS,
                    P.MANAGE_REMINDERS,
                ],
                nav_group="CRM",
            ),
            _mod(
                "office_approve",
                "تایید سفارش",
                "📋",
                "office",
                [P.APPROVE_SALE_ACCOUNTING],
                [P.APPROVE_SALE_ACCOUNTING, P.EDIT_SALE, P.VIEW_SALES],
                nav_group="CRM",
            ),
            _mod(
                "office_orders_track",
                "سفارش‌ها",
                "📦",
                "office-orders",
                [P.APPROVE_SALE_ACCOUNTING, P.VIEW_SALES],
                [P.APPROVE_SALE_ACCOUNTING, P.VIEW_SALES],
                nav_group="CRM",
            ),
            _mod(
                "office_products",
                "محصولات",
                "📦",
                "products",
                [P.VIEW_PRODUCTS],
                [P.VIEW_PRODUCTS, P.MANAGE_PRODUCTS],
                nav_group="CRM",
            ),
            _mod(
                "office_factory",
                "کارخانه — ساخت",
                "🔧",
                "factory",
                [P.VIEW_FACTORY_ORDERS],
                [P.VIEW_FACTORY_ORDERS, P.MANAGE_FACTORY_ORDERS],
                nav_group="CRM",
            ),
            _mod(
                "office_factory_built",
                "کارخانه — ساخته‌شده",
                "✅",
                "factory-built",
                [P.VIEW_FACTORY_ORDERS],
                [P.VIEW_FACTORY_ORDERS],
                nav_group="CRM",
            ),
            _mod(
                "office_freight",
                "کارخانه — باربری",
                "🚚",
                "freight",
                [P.VIEW_FREIGHT_ORDERS],
                [P.VIEW_FREIGHT_ORDERS, P.MANAGE_FREIGHT_ORDERS],
                nav_group="CRM",
            ),
            _mod(
                "office_warehouse",
                "انبار",
                "📦",
                "warehouse",
                [P.VIEW_WAREHOUSE_ORDERS, P.MANAGE_WAREHOUSE_ORDERS, P.APPROVE_SALE_ACCOUNTING],
                [P.VIEW_WAREHOUSE_ORDERS, P.MANAGE_WAREHOUSE_ORDERS, P.APPROVE_SALE_ACCOUNTING],
                nav_group="CRM",
            ),
            _mod(
                "office_filter",
                "فیلتر",
                "🔍",
                "filter",
                [
                    P.VIEW_ACCOUNTING,
                    P.APPROVE_SALE_ACCOUNTING,
                    P.VIEW_SALES,
                    P.VIEW_CUSTOMERS,
                    P.VIEW_INSTALLMENTS,
                ],
                [
                    P.VIEW_ACCOUNTING,
                    P.APPROVE_SALE_ACCOUNTING,
                    P.VIEW_SALES,
                    P.VIEW_CUSTOMERS,
                    P.VIEW_INSTALLMENTS,
                ],
                nav_group="CRM",
            ),
            _mod(
                "office_accounting",
                "حسابداری",
                "💰",
                "accounting",
                [P.VIEW_ACCOUNTING, P.VIEW_FACTORY_ACCOUNTING],
                [
                    P.VIEW_ACCOUNTING,
                    P.CREATE_ACCOUNTING,
                    P.EDIT_ACCOUNTING,
                    P.DELETE_ACCOUNTING,
                    P.APPROVE_ACCOUNTING,
                    P.VIEW_REPORTS,
                    P.VIEW_FACTORY_ACCOUNTING,
                    P.TRANSFER_FACTORY_ACCOUNTING_TO_OFFICE,
                ],
                nav_group="مالی",
            ),
            _mod(
                "office_checks",
                "چک و اقساط",
                "📋",
                "checks",
                [P.VIEW_INSTALLMENTS],
                [P.VIEW_INSTALLMENTS, P.MANAGE_INSTALLMENTS],
                nav_group="مالی",
            ),
            _mod(
                "office_materials",
                "تایید متریال",
                "🧵",
                "materials",
                [P.APPROVE_MATERIALS],
                [P.APPROVE_MATERIALS, P.VIEW_MATERIALS, P.MANAGE_MATERIALS],
                nav_group="مالی",
            ),
        ],
    },
    {
        "id": "factory",
        "label": "کارخانه",
        "icon": "🏭",
        "page_key": "factory",
        "default_page": "factory",
        "modules": [
            _notifications_mod("factory"),
            _mod(
                "factory_production",
                "ساخت",
                "🔧",
                "factory",
                [P.VIEW_FACTORY_ORDERS],
                [P.VIEW_FACTORY_ORDERS, P.MANAGE_FACTORY_ORDERS],
                nav_group="خط سفارش",
            ),
            _mod(
                "factory_built",
                "ساخته‌شده‌ها",
                "✅",
                "factory-built",
                [P.VIEW_FACTORY_ORDERS],
                [P.VIEW_FACTORY_ORDERS],
                nav_group="خط سفارش",
            ),
            _mod(
                "factory_freight",
                "باربری",
                "🚚",
                "freight",
                [P.VIEW_FREIGHT_ORDERS, P.MANAGE_FREIGHT_ORDERS],
                [P.VIEW_FREIGHT_ORDERS, P.MANAGE_FREIGHT_ORDERS],
                nav_group="خط سفارش",
            ),
            _mod(
                "factory_frames",
                "تولید کلاف",
                "🪵",
                "factory-frames",
                [P.VIEW_FRAMES, P.MANAGE_FRAMES],
                [P.VIEW_FRAMES, P.MANAGE_FRAMES],
                nav_group="کارگاه‌های تولید",
            ),
            _mod(
                "factory_carpentry",
                "نجاری",
                "🔧",
                "factory-carpentry",
                [P.VIEW_BETA_CARPENTRY, P.MANAGE_BETA_CARPENTRY],
                [P.VIEW_BETA_CARPENTRY, P.MANAGE_BETA_CARPENTRY],
                nav_group="کارگاه‌های تولید",
            ),
            _mod(
                "factory_paint",
                "رنگ‌کاری",
                "🧵",
                "factory-paint",
                [P.VIEW_BETA_PAINT, P.MANAGE_BETA_PAINT],
                [P.VIEW_BETA_PAINT, P.MANAGE_BETA_PAINT],
                nav_group="کارگاه‌های تولید",
            ),
            _mod(
                "factory_fabric",
                "پارچه",
                "🧵",
                "factory-fabric",
                [P.VIEW_BETA_FABRIC, P.MANAGE_BETA_FABRIC],
                [P.VIEW_BETA_FABRIC, P.MANAGE_BETA_FABRIC],
                nav_group="کارگاه‌های تولید",
            ),
            _mod(
                "factory_foam",
                "اسفنج",
                "📦",
                "factory-foam",
                [P.VIEW_BETA_FOAM, P.MANAGE_BETA_FOAM],
                [P.VIEW_BETA_FOAM, P.MANAGE_BETA_FOAM],
                nav_group="کارگاه‌های تولید",
            ),
            _mod(
                "factory_cushion",
                "کوسن",
                "📦",
                "factory-cushion",
                [P.VIEW_BETA_CUSHION, P.MANAGE_BETA_CUSHION],
                [P.VIEW_BETA_CUSHION, P.MANAGE_BETA_CUSHION],
                nav_group="کارگاه‌های تولید",
            ),
            _mod(
                "factory_upholstery",
                "رویه‌کوبی",
                "📦",
                "factory-upholstery",
                [P.VIEW_BETA_UPHOLSTERY, P.MANAGE_BETA_UPHOLSTERY],
                [P.VIEW_BETA_UPHOLSTERY, P.MANAGE_BETA_UPHOLSTERY],
                nav_group="کارگاه‌های تولید",
            ),
            _mod(
                "factory_assembly",
                "مونتاژ",
                "🔧",
                "factory-assembly",
                [P.VIEW_BETA_ASSEMBLY, P.MANAGE_BETA_ASSEMBLY],
                [P.VIEW_BETA_ASSEMBLY, P.MANAGE_BETA_ASSEMBLY],
                nav_group="کارگاه‌های تولید",
            ),
            _mod(
                "factory_qc",
                "کنترل کیفیت",
                "✅",
                "factory-qc",
                [P.VIEW_BETA_QC, P.MANAGE_BETA_QC],
                [P.VIEW_BETA_QC, P.MANAGE_BETA_QC],
                nav_group="کارگاه‌های تولید",
            ),
            _mod(
                "factory_clearance",
                "ترخیص",
                "📦",
                "factory-clearance",
                [P.VIEW_BETA_CLEARANCE, P.MANAGE_BETA_CLEARANCE],
                [P.VIEW_BETA_CLEARANCE, P.MANAGE_BETA_CLEARANCE],
                nav_group="کارگاه‌های تولید",
            ),
            _mod(
                "factory_products",
                "محصولات",
                "📦",
                "products",
                [P.VIEW_FACTORY_PRODUCTS],
                [P.VIEW_FACTORY_PRODUCTS, P.MANAGE_FACTORY_PRODUCTS],
                nav_group="کاتالوگ و مواد",
            ),
            _mod(
                "factory_materials",
                "متریال",
                "🧵",
                "materials",
                [P.VIEW_MATERIALS],
                [P.VIEW_MATERIALS, P.CREATE_MATERIALS, P.MANAGE_MATERIALS],
                nav_group="کاتالوگ و مواد",
            ),
            _mod(
                "factory_paint_recipes",
                "رنگ‌ها",
                "🎨",
                "factory-paint-recipes",
                [P.VIEW_FACTORY_PRODUCTS, P.VIEW_MATERIALS],
                [P.VIEW_FACTORY_PRODUCTS, P.MANAGE_FACTORY_PRODUCTS, P.VIEW_MATERIALS, P.MANAGE_MATERIALS],
                nav_group="کاتالوگ و مواد",
            ),
            _mod(
                "factory_fabric_recipes",
                "پارچه‌ها",
                "🧵",
                "factory-fabric-recipes",
                [P.VIEW_FACTORY_PRODUCTS, P.VIEW_MATERIALS],
                [P.VIEW_FACTORY_PRODUCTS, P.MANAGE_FACTORY_PRODUCTS, P.VIEW_MATERIALS, P.MANAGE_MATERIALS],
                nav_group="کاتالوگ و مواد",
            ),
            _mod(
                "factory_foam_recipes",
                "اسفنج‌ها",
                "📦",
                "factory-foam-recipes",
                [P.VIEW_FACTORY_PRODUCTS, P.VIEW_MATERIALS],
                [P.VIEW_FACTORY_PRODUCTS, P.MANAGE_FACTORY_PRODUCTS, P.VIEW_MATERIALS, P.MANAGE_MATERIALS],
                nav_group="کاتالوگ و مواد",
            ),
            _mod(
                "factory_webbing_recipes",
                "تسمه‌ها",
                "🧵",
                "factory-webbing-recipes",
                [P.VIEW_FACTORY_PRODUCTS, P.VIEW_MATERIALS],
                [P.VIEW_FACTORY_PRODUCTS, P.MANAGE_FACTORY_PRODUCTS, P.VIEW_MATERIALS, P.MANAGE_MATERIALS],
                nav_group="کاتالوگ و مواد",
            ),
            _mod(
                "factory_cushion_recipes",
                "کوسن‌ها",
                "📦",
                "factory-cushion-recipes",
                [P.VIEW_FACTORY_PRODUCTS, P.VIEW_MATERIALS],
                [P.VIEW_FACTORY_PRODUCTS, P.MANAGE_FACTORY_PRODUCTS, P.VIEW_MATERIALS, P.MANAGE_MATERIALS],
                nav_group="کاتالوگ و مواد",
            ),
        ],
    },
]


def _codes_for_pool(codes, pool):
    return [c for c in codes if c in pool]


def _module_for_matrix(mod, pool, *, include_empty=False):
    menu_codes = _codes_for_pool(mod["menu_permissions"], pool)
    section_codes = sorted(set(_codes_for_pool(mod["section_permissions"], pool)))
    if not menu_codes and not section_codes and not include_empty:
        return None
    item = {
        "id": mod["id"],
        "label": mod["label"],
        "icon": mod["icon"],
        "page_key": mod["page_key"],
        "executive_only": bool(mod.get("executive_only")),
        "system_admin": bool(mod.get("system_admin")),
        "cycle_watch": bool(mod.get("cycle_watch")),
        "menu_permission_codes": menu_codes,
        "section_permission_codes": section_codes,
        "menu_permissions": [
            {"code": c, "label": P.PERMISSION_LABELS.get(c, c)} for c in menu_codes
        ],
        "section_permissions": [
            {"code": c, "label": P.PERMISSION_LABELS.get(c, c)} for c in section_codes
        ],
    }
    if mod.get("nav_group"):
        item["nav_group"] = mod["nav_group"]
    return item


def portal_modules_for_matrix(assignable_only=False, *, include_empty_modules=False):
    pool = P.ASSIGNABLE_PERMISSIONS if assignable_only else P.ALL_PERMISSIONS
    portals = []
    for portal in PORTAL_MODULE_SPECS:
        modules = []
        for mod in portal["modules"]:
            if assignable_only and mod.get("system_admin"):
                continue
            item = _module_for_matrix(mod, pool, include_empty=include_empty_modules)
            if item:
                modules.append(item)
        if not modules:
            continue
        all_section = sorted({c for m in modules for c in m["section_permission_codes"]})
        all_menu = sorted({c for m in modules for c in m["menu_permission_codes"]})
        portals.append(
            {
                "id": portal["id"],
                "label": portal["label"],
                "icon": portal["icon"],
                "page_key": portal["page_key"],
                "default_page": portal.get("default_page"),
                "executive_only": bool(portal.get("executive_only")),
                "menu_permission_codes": all_menu,
                "section_permission_codes": all_section,
                "modules": modules,
            }
        )
    return portals


def can_see_managers_portal(user):
    """کاربرانی که پورتال مدیران را در منو می‌بینند."""
    return _has_managers_portal_module(user)


def can_send_leave_mission(user):
    """ارسال مرخصی/ماموریت — پورتال مدیران، بدون نشت از صفحه فیلتر داشبورد."""
    return _has_managers_portal_module(
        user,
        skip_module_ids={"managers_filter", "managers_dashboard", "managers_notifications"},
    )


def _has_managers_portal_module(user, *, skip_module_ids=None):
    if not user or not getattr(user, "is_authenticated", False):
        return False

    from auth.org_roles import is_executive_user
    from auth.permissions import has_permission, is_system_admin

    if is_executive_user(user):
        return True

    skip = skip_module_ids or set()
    managers = next((portal for portal in PORTAL_MODULE_SPECS if portal["id"] == "managers"), None)
    if not managers:
        return False
    for mod in managers["modules"]:
        if mod.get("id") in skip:
            continue
        menu = [code for code in (mod.get("menu_permissions") or []) if code]
        if not menu:
            continue
        if mod.get("executive_only"):
            continue
        if mod.get("system_admin") and not is_system_admin(user):
            continue
        if any(has_permission(user, code) for code in menu):
            return True
    return False


def module_tree_for_config():
    """درخت ماژول برای فرانت — شامل صفحات بدون مجوز مثل اعلان‌ها."""
    return portal_modules_for_matrix(assignable_only=False, include_empty_modules=True)


def sync_menu_section_permissions():
    """section_permissions پورتال‌ها را از کاتالوگ ماژول به‌روز می‌کند."""
    by_id = {p["id"]: p for p in PORTAL_MODULE_SPECS}
    for sec in P.MENU_SECTIONS:
        portal = by_id.get(sec["id"])
        if not portal:
            continue
        merged = set(sec.get("section_permissions") or [])
        menus = set(sec.get("menu_permissions") or [])
        for mod in portal["modules"]:
            merged.update(mod["section_permissions"])
            menus.update(mod["menu_permissions"])
        sec["section_permissions"] = sorted(merged)
        sec["menu_permissions"] = sorted(menus)


sync_menu_section_permissions()
