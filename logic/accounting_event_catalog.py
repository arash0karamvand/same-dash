"""ماتریس رسمی پوشش رویدادهای دارای اثر مالی.

افزودن endpoint مالی جدید بدون ثبت policy در این ماتریس باید در تست‌ها رد شود.
"""

FINANCIAL_EVENT_POLICIES = {
    "sales.sale_finalized": {"draft": True, "reversal": "correction", "implementation": "event_gateway"},
    "sales.payment_received": {"draft": True, "reversal": "correction", "implementation": "event_gateway"},
    "sales.sale_returned": {"draft": True, "reversal": "correction", "implementation": "trade_service"},
    "sales.cash_discount": {"draft": True, "reversal": "correction", "implementation": "trade_service"},
    "treasury.deposit_received": {"draft": True, "reversal": "correction", "implementation": "event_gateway"},
    "treasury.deposit_allocated": {"draft": True, "reversal": "correction", "implementation": "event_gateway"},
    "treasury.check_registered": {"draft": True, "reversal": "correction", "implementation": "check_service"},
    "treasury.check_cleared": {"draft": True, "reversal": "correction", "implementation": "check_service"},
    "purchases.invoice_posted": {"draft": True, "reversal": "correction", "implementation": "payables_service"},
    "purchases.invoice_settled": {"draft": True, "reversal": "correction", "implementation": "payables_service"},
    "inventory.material_received": {"draft": True, "reversal": "correction", "implementation": "material_flag"},
    "inventory.material_consumed": {"draft": True, "reversal": "mirror", "implementation": "material_flag"},
    "inventory.stocktake_closed": {"draft": True, "reversal": "correction", "implementation": "event_gateway"},
    "production.overhead_allocated": {"draft": True, "reversal": "void_draft", "implementation": "costing_service"},
    "production.wip_completed": {"draft": True, "reversal": "correction", "implementation": "event_gateway"},
    "production.abnormal_spoilage": {"draft": True, "reversal": "correction", "implementation": "event_gateway"},
    "payroll.assistance_paid": {"draft": True, "reversal": "correction", "implementation": "event_gateway"},
    "treasury.petty_cash_paid": {"draft": True, "reversal": "correction", "implementation": "event_gateway"},
    "treasury.petty_cash_settled": {"draft": True, "reversal": "correction", "implementation": "event_gateway"},
    "freight.period_expense": {"draft": True, "reversal": "correction", "implementation": "inventory_costing"},
}


REQUIRED_FINANCIAL_DOMAINS = {
    "sales",
    "treasury",
    "purchases",
    "inventory",
    "production",
    "payroll",
    "freight",
}


def validate_event_catalog():
    errors = []
    domains = {key.split(".", 1)[0] for key in FINANCIAL_EVENT_POLICIES}
    for domain in sorted(REQUIRED_FINANCIAL_DOMAINS - domains):
        errors.append(f"دامنه {domain} policy حسابداری ندارد.")
    for key, policy in FINANCIAL_EVENT_POLICIES.items():
        if not policy.get("draft"):
            errors.append(f"{key}: سند خودکار باید پیش‌نویس باشد.")
        if not policy.get("reversal"):
            errors.append(f"{key}: سیاست برگشت تعریف نشده است.")
        if not policy.get("implementation"):
            errors.append(f"{key}: پیاده‌سازی مشخص نشده است.")
    return errors
