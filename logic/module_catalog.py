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


def _notifications_mod(portal_id):
    return _mod(
        f"{portal_id}_notifications",
        "اعلان‌ها",
        "✉️",
        "notifications",
        [],
        [],
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
                "managers_levels",
                "باشگاه و سطوح",
                "🏅",
                "levels",
                [P.VIEW_LOYALTY],
                [
                    P.VIEW_LOYALTY,
                    P.MANAGE_LOYALTY,
                    P.RECALCULATE_LEVELS,
                    P.MANAGE_REMINDERS,
                ],
            ),
            _mod(
                "managers_sms",
                "پیامک",
                "✉️",
                "sms",
                [P.SEND_SMS, P.VIEW_SMS_LOGS],
                [P.SEND_SMS, P.MANAGE_SMS_CLUB, P.MANAGE_BIRTHDAY_SMS, P.VIEW_SMS_LOGS],
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
            _notifications_mod("office"),
            _mod(
                "office_approve",
                "تایید سفارش",
                "📋",
                "office",
                [P.APPROVE_SALE_ACCOUNTING],
                [P.APPROVE_SALE_ACCOUNTING, P.EDIT_SALE, P.VIEW_SALES],
            ),
            _mod(
                "office_orders_track",
                "سفارش‌ها",
                "📦",
                "office-orders",
                [P.APPROVE_SALE_ACCOUNTING, P.VIEW_SALES],
                [P.APPROVE_SALE_ACCOUNTING, P.VIEW_SALES],
            ),
            _mod(
                "office_customers",
                "مشتریان",
                "👥",
                "customers",
                [P.VIEW_CUSTOMERS],
                [P.VIEW_CUSTOMERS, P.EDIT_CUSTOMER, P.CREATE_CUSTOMER],
            ),
            _mod(
                "office_rfm",
                "تحلیل RFM",
                "📊",
                "rfm",
                [P.VIEW_RFM],
                [P.VIEW_RFM, P.MANAGE_RFM, P.SEND_SMS],
            ),
            _mod(
                "office_products",
                "محصولات",
                "📦",
                "products",
                [P.VIEW_PRODUCTS],
                [P.VIEW_PRODUCTS, P.MANAGE_PRODUCTS],
            ),
            _mod(
                "office_materials",
                "تایید متریال",
                "🧵",
                "materials",
                [P.APPROVE_MATERIALS],
                [P.APPROVE_MATERIALS, P.VIEW_MATERIALS, P.MANAGE_MATERIALS],
            ),
            _mod(
                "office_accounting",
                "حسابداری",
                "💰",
                "accounting",
                [P.VIEW_ACCOUNTING],
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
            ),
            _mod(
                "office_factory_accounting",
                "حسابداری کارخانه",
                "🏭",
                "factory-accounting",
                [P.VIEW_FACTORY_ACCOUNTING],
                [
                    P.VIEW_FACTORY_ACCOUNTING,
                    P.CREATE_FACTORY_ACCOUNTING,
                    P.EDIT_FACTORY_ACCOUNTING,
                    P.DELETE_FACTORY_ACCOUNTING,
                    P.APPROVE_FACTORY_ACCOUNTING,
                ],
            ),
            _mod(
                "office_checks",
                "چک و اقساط",
                "📋",
                "checks",
                [P.VIEW_INSTALLMENTS],
                [P.VIEW_INSTALLMENTS, P.MANAGE_INSTALLMENTS],
            ),
            _mod(
                "office_factory",
                "کارخانه — ساخت",
                "🔧",
                "factory",
                [P.VIEW_FACTORY_ORDERS],
                [P.VIEW_FACTORY_ORDERS, P.MANAGE_FACTORY_ORDERS],
            ),
            _mod(
                "office_factory_built",
                "کارخانه — ساخته‌شده",
                "✅",
                "factory-built",
                [P.VIEW_FACTORY_ORDERS],
                [P.VIEW_FACTORY_ORDERS],
            ),
            _mod(
                "office_freight",
                "کارخانه — باربری",
                "🚚",
                "freight",
                [P.VIEW_FREIGHT_ORDERS],
                [P.VIEW_FREIGHT_ORDERS, P.MANAGE_FREIGHT_ORDERS],
            ),
            _mod(
                "office_warehouse",
                "انبار",
                "📦",
                "warehouse",
                [P.VIEW_WAREHOUSE_ORDERS, P.MANAGE_WAREHOUSE_ORDERS, P.APPROVE_SALE_ACCOUNTING],
                [P.VIEW_WAREHOUSE_ORDERS, P.MANAGE_WAREHOUSE_ORDERS, P.APPROVE_SALE_ACCOUNTING],
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
            ),
            _mod(
                "factory_built",
                "ساخته‌شده‌ها",
                "✅",
                "factory-built",
                [P.VIEW_FACTORY_ORDERS],
                [P.VIEW_FACTORY_ORDERS],
            ),
            _mod(
                "factory_freight",
                "باربری",
                "🚚",
                "freight",
                [P.VIEW_FREIGHT_ORDERS, P.MANAGE_FREIGHT_ORDERS],
                [P.VIEW_FREIGHT_ORDERS, P.MANAGE_FREIGHT_ORDERS],
            ),
            _mod(
                "factory_products",
                "محصولات",
                "📦",
                "products",
                [P.VIEW_FACTORY_PRODUCTS],
                [P.VIEW_FACTORY_PRODUCTS, P.MANAGE_FACTORY_PRODUCTS],
            ),
            _mod(
                "factory_materials",
                "متریال",
                "🧵",
                "materials",
                [P.VIEW_MATERIALS],
                [P.VIEW_MATERIALS, P.CREATE_MATERIALS, P.MANAGE_MATERIALS],
            ),
            _mod(
                "factory_accounting",
                "حسابداری",
                "💰",
                "factory-accounting",
                [P.VIEW_FACTORY_ACCOUNTING],
                [
                    P.VIEW_FACTORY_ACCOUNTING,
                    P.CREATE_FACTORY_ACCOUNTING,
                    P.EDIT_FACTORY_ACCOUNTING,
                    P.DELETE_FACTORY_ACCOUNTING,
                    P.APPROVE_FACTORY_ACCOUNTING,
                ],
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
    return {
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
