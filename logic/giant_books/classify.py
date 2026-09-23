"""طبقه‌بندی حساب برای صورت‌های مالی.

پیشوند کدها همان کدینگ دفتر ایران است. اسلاگ‌های خاص قبل از پیشوند اعمال می‌شوند
تا سرمایه‌گذاری (۱۷۴۰) داخل دارایی عملیاتیِ ۱۷ نرود.
"""

CASH_SLUGS = {"cash_documents", "petty_cash", "bank", "collection_at_bank"}
INVESTING_SLUGS = {"investment_projects"}
OPERATING_LIABILITY_SLUGS = {"bank_payables", "accounts_payable", "other_payables"}
FINANCING_LIABILITY_SLUGS = {"long_term_loans"}

CASH_PREFIXES = ("111", "112", "113", "121", "122")
OPERATING_ASSET_PREFIXES = ("13", "15", "17")
OPERATING_LIABILITY_PREFIXES = ("41", "43")


def root_code(path, code):
    text = (path or code or "").strip()
    return text.split("/")[0]


def bucket(account_class, slug, path, code):
    slug = slug or ""
    root = root_code(path, code)
    if account_class == "revenue":
        return "revenue"
    if account_class == "expense":
        return "expense"
    if account_class == "equity":
        return "equity"
    if account_class == "asset":
        if slug in INVESTING_SLUGS:
            return "investing_asset"
        if slug in CASH_SLUGS or root.startswith(CASH_PREFIXES):
            return "cash"
        if root.startswith(OPERATING_ASSET_PREFIXES):
            return "operating_asset"
        return "investing_asset"
    if account_class == "liability":
        if slug in FINANCING_LIABILITY_SLUGS:
            return "financing_liability"
        if slug in OPERATING_LIABILITY_SLUGS or root.startswith(OPERATING_LIABILITY_PREFIXES):
            return "operating_liability"
        return "financing_liability"
    return "equity"
