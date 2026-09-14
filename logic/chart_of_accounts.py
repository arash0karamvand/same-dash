"""دفتر کل استاندارد ایران — منبع واحد کد، slug، mapping و قوانین ثبت."""

from __future__ import annotations

from types import SimpleNamespace

CHART_VERSION = "1.0.0"

ACCOUNT_CLASS_LABELS = {
    "asset": "دارایی",
    "liability": "بدهی",
    "equity": "سرمایه",
    "revenue": "درآمد",
    "expense": "هزینه",
}

NORMAL_BALANCE_LABELS = {
    "debit": "بدهکار",
    "credit": "بستانکار",
}

ENTRY_TYPE_LABELS = {
    "manual": "دستی",
    "sale": "فروش",
    "receivable": "دریافتنی",
    "payment": "دریافت / پرداخت",
    "refund": "برگشت",
    "adjustment": "تعدیل",
    "other": "سایر",
}

PAYMENT_METHOD_LABELS = {
    "cash": "نقدی",
    "check": "چک",
    "card": "کارت‌خوان",
    "transfer": "انتقال بانکی",
}

CHART_OF_ACCOUNTS = [
    {"slug": "cash_documents", "code": "1120", "name": "اسناد نزد صندوق", "account_class": "asset", "normal_balance": "debit", "sort_order": 10, "legacy_entry_type": "payment"},
    {"slug": "petty_cash", "code": "1130", "name": "تنخواه گردان", "account_class": "asset", "normal_balance": "debit", "sort_order": 20},
    {"slug": "bank", "code": "1210", "name": "بانک", "account_class": "asset", "normal_balance": "debit", "sort_order": 30, "legacy_entry_type": "payment"},
    {"slug": "collection_at_bank", "code": "1220", "name": "اسناد در جریان وصول نزد بانک", "account_class": "asset", "normal_balance": "debit", "sort_order": 40},
    {"slug": "receivables", "code": "1310", "name": "حساب‌ها و اسناد (دریافتی)", "account_class": "asset", "normal_balance": "debit", "sort_order": 50, "legacy_entry_type": "receivable"},
    {"slug": "other_receivables", "code": "1320", "name": "سایر حساب‌ها (دریافتی)", "account_class": "asset", "normal_balance": "debit", "sort_order": 60},
    {"slug": "raw_materials_inventory", "code": "1510", "name": "موجودی مواد اولیه", "account_class": "asset", "normal_balance": "debit", "sort_order": 70},
    {"slug": "wip_inventory", "code": "1520", "name": "موجودی کالای در جریان ساخت", "account_class": "asset", "normal_balance": "debit", "sort_order": 80},
    {"slug": "semi_finished_inventory", "code": "1530", "name": "موجودی کالای نیمه‌ساخت", "account_class": "asset", "normal_balance": "debit", "sort_order": 90},
    {"slug": "finished_goods_inventory", "code": "1540", "name": "موجودی محصول", "account_class": "asset", "normal_balance": "debit", "sort_order": 100},
    {"slug": "prepayments", "code": "1710", "name": "پیش‌پرداخت‌ها و سپرده‌ها", "account_class": "asset", "normal_balance": "debit", "sort_order": 110},
    {"slug": "investment_projects", "code": "1740", "name": "سرمایه‌گذاری و پروژه", "account_class": "asset", "normal_balance": "debit", "sort_order": 120},
    {"slug": "deposits_sureties", "code": "1750", "name": "ودایع و سپرده‌ها", "account_class": "asset", "normal_balance": "debit", "sort_order": 130},
    {"slug": "bank_payables", "code": "4110", "name": "اسناد پرداختنی بانک", "account_class": "liability", "normal_balance": "credit", "sort_order": 210},
    {"slug": "accounts_payable", "code": "4311", "name": "حساب‌ها و اسناد (پرداختنی)", "account_class": "liability", "normal_balance": "credit", "sort_order": 220},
    {"slug": "other_payables", "code": "4321", "name": "سایر حساب‌های پرداختنی", "account_class": "liability", "normal_balance": "credit", "sort_order": 230},
    {"slug": "long_term_loans", "code": "5110", "name": "وام‌های پرداختنی بلندمدت", "account_class": "liability", "normal_balance": "credit", "sort_order": 240},
    {"slug": "retained_earnings", "code": "6320", "name": "سود و (زیان) انباشته", "account_class": "equity", "normal_balance": "credit", "sort_order": 310},
    {"slug": "raw_materials_sales", "code": "7210", "name": "فروش موجودی مواد اولیه", "account_class": "revenue", "normal_balance": "credit", "sort_order": 410},
    {"slug": "semi_finished_sales", "code": "7230", "name": "فروش موجودی کالای نیمه‌ساخته", "account_class": "revenue", "normal_balance": "credit", "sort_order": 420},
    {"slug": "product_sales", "code": "7240", "name": "فروش موجودی محصول", "account_class": "revenue", "normal_balance": "credit", "sort_order": 430, "legacy_entry_type": "sale"},
    {"slug": "other_revenue", "code": "7510", "name": "سایر درآمدها", "account_class": "revenue", "normal_balance": "credit", "sort_order": 440, "legacy_entry_type": "other"},
    {"slug": "purchase_discount", "code": "7520", "name": "تخفیف از خرید", "account_class": "revenue", "normal_balance": "credit", "sort_order": 450},
    {"slug": "production_payroll", "code": "8110", "name": "هزینه‌های حقوق و دستمزد تولید", "account_class": "expense", "normal_balance": "debit", "sort_order": 510},
    {"slug": "production_overhead", "code": "8111", "name": "هزینه‌های سربار تولید", "account_class": "expense", "normal_balance": "debit", "sort_order": 520},
    {"slug": "admin_payroll", "code": "8210", "name": "هزینه‌های حقوق و دستمزد اداری", "account_class": "expense", "normal_balance": "debit", "sort_order": 530},
    {"slug": "admin_overhead", "code": "8211", "name": "هزینه‌های سربار اداری", "account_class": "expense", "normal_balance": "debit", "sort_order": 540, "legacy_entry_type": "adjustment"},
    {"slug": "distribution_sales_expense", "code": "8220", "name": "هزینه‌های توزیع و فروش", "account_class": "expense", "normal_balance": "debit", "sort_order": 550},
    {"slug": "financial_expense", "code": "8310", "name": "هزینه‌های مالی", "account_class": "expense", "normal_balance": "debit", "sort_order": 560},
    {"slug": "raw_materials_purchase_return", "code": "9430", "name": "برگشت از خرید موجودی مواد اولیه", "account_class": "expense", "normal_balance": "debit", "sort_order": 570, "legacy_entry_type": "refund"},
    {"slug": "memorandum_accounts", "code": "9710", "name": "حساب‌های انتظامی", "account_class": "asset", "normal_balance": "debit", "sort_order": 580},
    {"slug": "memorandum_counterpart", "code": "9720", "name": "طرف حساب‌های انتظامی", "account_class": "liability", "normal_balance": "credit", "sort_order": 590},
    {
        "slug": "raw_materials_purchase_return_cogs",
        "code": "9930",
        "name": "بهای تمام‌شده برگشت از خرید موجودی مواد اولیه",
        "account_class": "expense",
        "normal_balance": "debit",
        "sort_order": 600,
    },
]

ACCOUNT_SLUGS = SimpleNamespace(
    CASH_DOCUMENTS="cash_documents",
    PETTY_CASH="petty_cash",
    BANK="bank",
    COLLECTION_AT_BANK="collection_at_bank",
    RECEIVABLES="receivables",
    OTHER_RECEIVABLES="other_receivables",
    RAW_MATERIALS_INVENTORY="raw_materials_inventory",
    WIP_INVENTORY="wip_inventory",
    SEMI_FINISHED_INVENTORY="semi_finished_inventory",
    FINISHED_GOODS_INVENTORY="finished_goods_inventory",
    PREPAYMENTS="prepayments",
    INVESTMENT_PROJECTS="investment_projects",
    DEPOSITS_SURETIES="deposits_sureties",
    BANK_PAYABLES="bank_payables",
    ACCOUNTS_PAYABLE="accounts_payable",
    OTHER_PAYABLES="other_payables",
    LONG_TERM_LOANS="long_term_loans",
    RETAINED_EARNINGS="retained_earnings",
    RAW_MATERIALS_SALES="raw_materials_sales",
    SEMI_FINISHED_SALES="semi_finished_sales",
    PRODUCT_SALES="product_sales",
    OTHER_REVENUE="other_revenue",
    PURCHASE_DISCOUNT="purchase_discount",
    PRODUCTION_PAYROLL="production_payroll",
    PRODUCTION_OVERHEAD="production_overhead",
    ADMIN_PAYROLL="admin_payroll",
    ADMIN_OVERHEAD="admin_overhead",
    DISTRIBUTION_SALES_EXPENSE="distribution_sales_expense",
    FINANCIAL_EXPENSE="financial_expense",
    RAW_MATERIALS_PURCHASE_RETURN="raw_materials_purchase_return",
    MEMORANDUM_ACCOUNTS="memorandum_accounts",
    MEMORANDUM_COUNTERPART="memorandum_counterpart",
    RAW_MATERIALS_PURCHASE_RETURN_COGS="raw_materials_purchase_return_cogs",
)

ENTRY_TYPE_TO_SLUG = {
    "sale": ACCOUNT_SLUGS.PRODUCT_SALES,
    "receivable": ACCOUNT_SLUGS.RECEIVABLES,
    "payment": ACCOUNT_SLUGS.BANK,
    "refund": ACCOUNT_SLUGS.RAW_MATERIALS_PURCHASE_RETURN,
    "adjustment": ACCOUNT_SLUGS.ADMIN_OVERHEAD,
    "other": ACCOUNT_SLUGS.OTHER_REVENUE,
    "manual": ACCOUNT_SLUGS.OTHER_REVENUE,
}

PAYMENT_METHOD_TO_SLUG = {
    "cash": ACCOUNT_SLUGS.CASH_DOCUMENTS,
    "check": ACCOUNT_SLUGS.COLLECTION_AT_BANK,
    "card": ACCOUNT_SLUGS.BANK,
    "transfer": ACCOUNT_SLUGS.BANK,
}

PAYMENT_ACCOUNT_SLUGS = frozenset(PAYMENT_METHOD_TO_SLUG.values()) | {ACCOUNT_SLUGS.PETTY_CASH}
CHECK_ACCOUNT_SLUGS = PAYMENT_ACCOUNT_SLUGS

CODE_PREFIX_TO_CLASS = {
    "1": "asset",
    "4": "liability",
    "5": "liability",
    "6": "equity",
    "7": "revenue",
    "8": "expense",
    "9": "expense",
}

# Fowler Posting Rule — side: debit|credit, slug or account_key, amount_key
POSTING_RULES = {
    "sale": [
        {"side": "credit", "slug": ACCOUNT_SLUGS.PRODUCT_SALES, "amount_key": "final_amount"},
        {"side": "debit", "slug": ACCOUNT_SLUGS.RECEIVABLES, "amount_key": "outstanding", "min_amount": True},
        {"side": "debit", "account_key": "payment_account", "amount_key": "paid", "min_amount": True},
    ],
    "payment": [
        {"side": "debit", "account_key": "payment_account", "amount_key": "amount"},
        {"side": "credit", "slug": ACCOUNT_SLUGS.RECEIVABLES, "amount_key": "amount"},
    ],
    "check_register": [
        {"side": "debit", "account_key": "registration_account", "amount_key": "amount"},
        {"side": "credit", "slug": ACCOUNT_SLUGS.RECEIVABLES, "amount_key": "amount"},
    ],
    "check_clear": [
        {"side": "debit", "account_key": "deposit_account", "amount_key": "amount"},
        {"side": "credit", "account_key": "registration_account", "amount_key": "amount"},
    ],
    "material_receipt": [
        {"side": "debit", "slug": ACCOUNT_SLUGS.RAW_MATERIALS_INVENTORY, "amount_key": "value"},
        {"side": "credit", "slug": ACCOUNT_SLUGS.ACCOUNTS_PAYABLE, "amount_key": "value"},
    ],
    "material_consumption": [
        {"side": "debit", "slug": ACCOUNT_SLUGS.WIP_INVENTORY, "amount_key": "cost"},
        {"side": "credit", "slug": ACCOUNT_SLUGS.RAW_MATERIALS_INVENTORY, "amount_key": "cost"},
    ],
    "material_consumption_reverse": [
        {"side": "debit", "slug": ACCOUNT_SLUGS.RAW_MATERIALS_INVENTORY, "amount_key": "cost"},
        {"side": "credit", "slug": ACCOUNT_SLUGS.WIP_INVENTORY, "amount_key": "cost"},
    ],
}

_SLUG_BY_CODE = {row["code"]: row["slug"] for row in CHART_OF_ACCOUNTS}
_CODE_BY_SLUG = {row["slug"]: row["code"] for row in CHART_OF_ACCOUNTS}


def slug_for_code(code: str) -> str:
    root = (code or "").split("/")[0].strip()
    return _SLUG_BY_CODE.get(root, f"excel_{root}")


def code_for_slug(slug: str) -> str | None:
    return _CODE_BY_SLUG.get(slug)


def infer_account_class(code: str) -> str:
    first = (code or "0").split("/")[0][0]
    return CODE_PREFIX_TO_CLASS.get(first, "asset")


def infer_normal_balance(account_class: str) -> str:
    if account_class in {"liability", "equity", "revenue"}:
        return "credit"
    return "debit"


def chart_row_for_slug(slug: str) -> dict | None:
    for row in CHART_OF_ACCOUNTS:
        if row["slug"] == slug:
            return row
    return None


def validate_chart_integrity() -> list[str]:
    errors = []
    slugs = [row["slug"] for row in CHART_OF_ACCOUNTS]
    codes = [row["code"] for row in CHART_OF_ACCOUNTS]
    if len(slugs) != len(set(slugs)):
        errors.append("slugهای تکراری در دفتر کل وجود دارد.")
    if len(codes) != len(set(codes)):
        errors.append("کدهای تکراری در دفتر کل وجود دارد.")
    if len(CHART_OF_ACCOUNTS) != 33:
        errors.append(f"تعداد حساب‌های کل باید ۳۳ باشد؛ فعلاً {len(CHART_OF_ACCOUNTS)}.")
    for rule_name, rules in POSTING_RULES.items():
        for rule in rules:
            slug = rule.get("slug")
            if slug and slug not in _CODE_BY_SLUG:
                errors.append(f"قانون {rule_name}: slug «{slug}» در دفتر کل نیست.")
    for slug in PAYMENT_METHOD_TO_SLUG.values():
        if slug not in _CODE_BY_SLUG:
            errors.append(f"slug روش پرداخت «{slug}» در دفتر کل نیست.")
    for slug in ENTRY_TYPE_TO_SLUG.values():
        if slug not in _CODE_BY_SLUG:
            errors.append(f"slug نوع سند «{slug}» در دفتر کل نیست.")
    return errors


def accounting_meta() -> dict:
    return {
        "chart_version": CHART_VERSION,
        "account_count": len(CHART_OF_ACCOUNTS),
        "account_classes": [
            {"value": key, "label": label} for key, label in ACCOUNT_CLASS_LABELS.items()
        ],
        "normal_balances": [
            {"value": key, "label": label} for key, label in NORMAL_BALANCE_LABELS.items()
        ],
        "entry_types": [
            {"value": key, "label": label} for key, label in ENTRY_TYPE_LABELS.items()
        ],
        "payment_methods": [
            {"value": key, "label": label} for key, label in PAYMENT_METHOD_LABELS.items()
        ],
    }
