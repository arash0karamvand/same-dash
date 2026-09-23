"""دفتر کل استاندارد ایران — seed از catalog_defaults؛ runtime از Account در MySQL."""

from __future__ import annotations

from types import SimpleNamespace

from logic.catalog_defaults import (
    ACCOUNT_ROLE_BY_CODE,
    CHART_VERSION,
    CODE_PREFIX_TO_CLASS,
    POSTING_RULES,  # seed-only; runtime via dynamic_choices.posting_rules()
)
from logic.dynamic_choices import entry_type_account_map, payment_method_account_map

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

ACCOUNT_SLUGS = SimpleNamespace(
    CASH_DOCUMENTS="cash_documents",
    PETTY_CASH="petty_cash",
    BANK="bank",
    COLLECTION_AT_BANK="collection_at_bank",
    RECEIVABLES="receivables",
    OTHER_RECEIVABLES="other_receivables",
    VAT_RECEIVABLE="vat_receivable",
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
    VAT_PAYABLE="vat_payable",
    LONG_TERM_LOANS="long_term_loans",
    RETAINED_EARNINGS="retained_earnings",
    RAW_MATERIALS_SALES="raw_materials_sales",
    SEMI_FINISHED_SALES="semi_finished_sales",
    PRODUCT_SALES="product_sales",
    SALES_ALLOWANCES="sales_allowances",
    OTHER_REVENUE="other_revenue",
    PURCHASE_DISCOUNT="purchase_discount",
    PRODUCTION_PAYROLL="production_payroll",
    PRODUCTION_OVERHEAD="production_overhead",
    COGS="cogs",
    ADMIN_PAYROLL="admin_payroll",
    ADMIN_OVERHEAD="admin_overhead",
    DISTRIBUTION_SALES_EXPENSE="distribution_sales_expense",
    FINANCIAL_EXPENSE="financial_expense",
    RAW_MATERIALS_PURCHASE_RETURN="raw_materials_purchase_return",
    MEMORANDUM_ACCOUNTS="memorandum_accounts",
    MEMORANDUM_COUNTERPART="memorandum_counterpart",
    RAW_MATERIALS_PURCHASE_RETURN_COGS="raw_materials_purchase_return_cogs",
)


def _fallback_entry_type_map():
    return {
        "sale": ACCOUNT_SLUGS.PRODUCT_SALES,
        "receivable": ACCOUNT_SLUGS.RECEIVABLES,
        "payment": ACCOUNT_SLUGS.BANK,
        "refund": ACCOUNT_SLUGS.RAW_MATERIALS_PURCHASE_RETURN,
        "adjustment": ACCOUNT_SLUGS.ADMIN_OVERHEAD,
        "other": ACCOUNT_SLUGS.OTHER_REVENUE,
        "manual": ACCOUNT_SLUGS.OTHER_REVENUE,
    }


def _fallback_payment_map():
    return {
        "cash": ACCOUNT_SLUGS.CASH_DOCUMENTS,
        "check": ACCOUNT_SLUGS.COLLECTION_AT_BANK,
        "card": ACCOUNT_SLUGS.BANK,
        "transfer": ACCOUNT_SLUGS.BANK,
    }


def get_entry_type_to_slug():
    mapped = entry_type_account_map()
    return mapped or _fallback_entry_type_map()


def get_payment_method_to_slug():
    mapped = payment_method_account_map()
    return mapped or _fallback_payment_map()


PAYMENT_METHOD_TO_SLUG = get_payment_method_to_slug()
ENTRY_TYPE_TO_SLUG = get_entry_type_to_slug()

PAYMENT_ACCOUNT_SLUGS = frozenset(PAYMENT_METHOD_TO_SLUG.values()) | {ACCOUNT_SLUGS.PETTY_CASH}
CHECK_ACCOUNT_SLUGS = PAYMENT_ACCOUNT_SLUGS


def _accounts_from_db(*, ledger=None):
    from logic.accounting_accounts import _accounts

    if ledger is None:
        from logic.ledger import OFFICE_LEDGER

        ledger = OFFICE_LEDGER
    return list(_accounts(ledger).filter(is_active=True).order_by("sort_order", "code"))


def _slug_code_map(*, ledger=None):
    rows = _accounts_from_db(ledger=ledger)
    return {row.slug: row.code for row in rows}


def slug_for_code(code: str, *, ledger=None) -> str:
    """slug نقش سیستمی (فروش، دریافتنی، …) برای کد کل؛ حساب خودش از اکسل ساخته می‌شود."""
    from logic.accounting_accounts import _accounts

    if ledger is None:
        from logic.ledger import OFFICE_LEDGER

        ledger = OFFICE_LEDGER
    root = (code or "").split("/")[0].strip()
    role_slug = ACCOUNT_ROLE_BY_CODE.get(root)
    if role_slug and not _accounts(ledger).filter(slug=role_slug).exclude(code=root).exists():
        return role_slug
    return f"excel_{root}"


def code_for_slug(slug: str) -> str | None:
    return _slug_code_map().get(slug)


def infer_account_class(code: str) -> str:
    first = (code or "0").split("/")[0][0]
    return CODE_PREFIX_TO_CLASS.get(first, "asset")


def infer_normal_balance(account_class: str) -> str:
    if account_class in {"liability", "equity", "revenue"}:
        return "credit"
    return "debit"


def chart_row_for_slug(slug: str) -> dict | None:
    from logic.ledger import OFFICE_LEDGER

    account = _accounts_from_db(ledger=OFFICE_LEDGER)
    for row in account:
        if row.slug == slug:
            return {
                "slug": row.slug,
                "code": row.code,
                "name": row.name,
                "account_class": row.account_class,
                "normal_balance": row.normal_balance,
                "sort_order": row.sort_order,
                "legacy_entry_type": row.legacy_entry_type,
            }
    return None


def validate_chart_integrity() -> list[str]:
    from logic.dynamic_choices import posting_rules

    errors = []
    rows = _accounts_from_db()
    if not rows:
        return errors
    slugs = [row.slug for row in rows]
    codes = [row.code for row in rows]
    if len(slugs) != len(set(slugs)):
        errors.append("slugهای تکراری در دفتر کل وجود دارد.")
    if len(codes) != len(set(codes)):
        errors.append("کدهای تکراری در دفتر کل وجود دارد.")
    slug_set = set(slugs)
    rules = posting_rules()
    for rule_name, rule_lines in rules.items():
        for rule in rule_lines:
            slug = rule.get("slug")
            if slug and slug not in slug_set:
                errors.append(f"قانون {rule_name}: slug «{slug}» در دفتر کل نیست.")
    for slug in PAYMENT_METHOD_TO_SLUG.values():
        if slug not in slug_set:
            errors.append(f"slug روش پرداخت «{slug}» در دفتر کل نیست.")
    for slug in ENTRY_TYPE_TO_SLUG.values():
        if slug not in slug_set:
            errors.append(f"slug نوع سند «{slug}» در دفتر کل نیست.")
    return errors


def accounting_meta() -> dict:
    from logic.dynamic_choices import choice_options

    account_classes = choice_options("account_class") or [
        {"value": key, "label": label} for key, label in ACCOUNT_CLASS_LABELS.items()
    ]
    normal_balances = choice_options("normal_balance") or [
        {"value": key, "label": label} for key, label in NORMAL_BALANCE_LABELS.items()
    ]
    entry_types = choice_options("journal_entry_type") or [
        {"value": key, "label": label} for key, label in ENTRY_TYPE_LABELS.items()
    ]
    payment_methods = choice_options("payment_method") or [
        {"value": key, "label": label} for key, label in PAYMENT_METHOD_LABELS.items()
    ]
    rows = _accounts_from_db()
    return {
        "chart_version": CHART_VERSION,
        "account_count": len(rows),
        "account_classes": account_classes,
        "normal_balances": normal_balances,
        "entry_types": entry_types,
        "payment_methods": payment_methods,
    }
