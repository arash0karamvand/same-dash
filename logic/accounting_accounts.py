"""طرح حساب‌ها (دفتر کل) — seed و کمک‌تابع‌های حساب."""

from backend.models import Account, DetailedAccount, SubsidiaryAccount

ACCOUNT_CLASS_LABELS = {
    "asset": "دارایی",
    "liability": "بدهی",
    "equity": "سرمایه",
    "revenue": "درآمد",
    "expense": "هزینه",
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

ENTRY_TYPE_ACCOUNT_SLUGS = {
    "sale": "product_sales",
    "receivable": "receivables",
    "payment": "bank",
    "refund": "raw_materials_purchase_return",
    "adjustment": "admin_overhead",
    "other": "other_revenue",
}

PAYMENT_METHOD_ACCOUNT_SLUGS = {
    "cash": "cash_documents",
    "check": "collection_at_bank",
    "card": "bank",
    "transfer": "bank",
}


def seed_accounts():
    """ایجاد یا به‌روزرسانی حساب‌های طرح حساب."""
    has_code = any(f.name == "code" for f in Account._meta.get_fields())
    for row in CHART_OF_ACCOUNTS:
        defaults = {
            "name": row["name"],
            "account_class": row["account_class"],
            "normal_balance": row["normal_balance"],
            "sort_order": row["sort_order"],
            "legacy_entry_type": row.get("legacy_entry_type", ""),
            "is_active": True,
        }
        if has_code:
            defaults["code"] = row.get("code", "")
        Account.objects.update_or_create(
            slug=row["slug"],
            defaults=defaults,
        )


def get_account(slug, *, required=True):
    account = Account.objects.filter(slug=slug, is_active=True).first()
    if account:
        return account
    if not Account.objects.exists():
        seed_accounts()
        account = Account.objects.filter(slug=slug, is_active=True).first()
    if account or not required:
        return account
    raise ValueError(f"حساب «{slug}» یافت نشد.")


def resolve_account_for_entry(*, account_id=None, account_slug=None, entry_type=None):
    if account_id:
        return Account.objects.get(pk=account_id, is_active=True)
    if account_slug:
        return get_account(account_slug)
    if entry_type == "manual":
        return get_account("other_revenue")
    if entry_type:
        account = Account.objects.filter(legacy_entry_type=entry_type, is_active=True).first()
        if account:
            return account
        slug = ENTRY_TYPE_ACCOUNT_SLUGS.get(entry_type)
        if slug:
            return get_account(slug)
    raise ValueError("حساب سند مشخص نشده است.")


def payment_account_for_sale(sale):
    method = getattr(sale, "payment_method", None) or "cash"
    slug = PAYMENT_METHOD_ACCOUNT_SLUGS.get(method, "bank")
    return get_account(slug)


def subsidiary_to_dict(sub):
    return {
        "id": sub.id,
        "account_id": sub.account_id,
        "code": sub.code,
        "full_code": sub.full_code,
        "name": sub.name,
        "is_active": sub.is_active,
        "general_code": sub.account.code or "",
        "general_name": sub.account.name,
    }


def detailed_to_dict(detail):
    return {
        "id": detail.id,
        "subsidiary_id": detail.subsidiary_id,
        "account_id": detail.subsidiary.account_id,
        "code": detail.code,
        "full_code": detail.full_code,
        "name": detail.name,
        "is_active": detail.is_active,
        "subsidiary_code": detail.subsidiary.full_code,
        "subsidiary_name": detail.subsidiary.name,
        "general_code": detail.subsidiary.account.code or "",
        "general_name": detail.subsidiary.account.name,
    }


def accounts_grouped():
    seed_accounts()
    groups = []
    for class_key, class_label in ACCOUNT_CLASS_LABELS.items():
        accounts = Account.objects.filter(account_class=class_key, is_active=True).order_by("sort_order", "name")
        groups.append(
            {
                "class": class_key,
                "class_label": class_label,
                "accounts": [account_to_dict(a) for a in accounts],
            }
        )
    return groups


def account_to_dict(account):
    return {
        "id": account.id,
        "slug": account.slug,
        "code": account.code or "",
        "name": account.name,
        "account_class": account.account_class,
        "account_class_label": account.get_account_class_display(),
        "normal_balance": account.normal_balance,
        "sort_order": account.sort_order,
        "legacy_entry_type": account.legacy_entry_type or None,
        "is_active": account.is_active,
    }


def resolve_line_accounts(*, account_id=None, subsidiary_id=None, detailed_id=None):
    """حل حساب کل/معین/تفصیلی برای یک ردیف سند."""
    detailed = subsidiary = account = None
    if detailed_id:
        detailed = DetailedAccount.objects.select_related("subsidiary", "subsidiary__account").get(
            pk=detailed_id, is_active=True
        )
        subsidiary = detailed.subsidiary
        account = subsidiary.account
    elif subsidiary_id:
        subsidiary = SubsidiaryAccount.objects.select_related("account").get(pk=subsidiary_id, is_active=True)
        account = subsidiary.account
    elif account_id:
        account = Account.objects.get(pk=account_id, is_active=True)
    else:
        raise ValueError("حداقل حساب کل باید مشخص شود.")
    return account, subsidiary, detailed


def list_document_models(params):
    """مدل‌های سند (حساب‌های دفتر کل) به همراه تعداد اسناد."""
    from django.db.models import Count, Q

    from backend.models import AccountingEntry
    from logic.accounting_entries import apply_entry_filters

    seed_accounts()
    accounts = Account.objects.filter(is_active=True).order_by("sort_order", "name")
    account_class = (params.get("account_class") or "").strip()
    if account_class:
        accounts = accounts.filter(account_class=account_class)

    entry_qs = apply_entry_filters(
        AccountingEntry.objects.filter(account__isnull=False).filter(
            Q(sale__isnull=True) | Q(sale__is_deleted=False)
        ),
        params,
    )
    counts = {
        row["account_id"]: row["count"]
        for row in entry_qs.values("account_id").annotate(count=Count("id"))
    }

    models = []
    for account in accounts:
        info = account_to_dict(account)
        info["account_code"] = account.code or str(account.sort_order).zfill(4)
        info["entry_count"] = counts.get(account.id, 0)
        models.append(info)

    return {"models": models, "accounts": accounts_grouped()}


def list_subsidiary_accounts(params):
    account_id = (params.get("account_id") or "").strip()
    qs = SubsidiaryAccount.objects.filter(is_active=True).select_related("account").order_by(
        "account__sort_order", "code"
    )
    if account_id.isdigit():
        qs = qs.filter(account_id=int(account_id))
    return [subsidiary_to_dict(s) for s in qs]


def create_subsidiary_account(*, account_id, code, name):
    code = (code or "").strip()
    name = (name or "").strip()
    if not account_id or not code or not name:
        raise ValueError("حساب کل، کد و عنوان معین الزامی است.")
    try:
        account = Account.objects.get(pk=account_id, is_active=True)
    except Account.DoesNotExist as exc:
        raise LookupError("حساب کل یافت نشد.") from exc
    if SubsidiaryAccount.objects.filter(account=account, code=code).exists():
        raise ValueError("این کد معین قبلاً ثبت شده است.")
    return SubsidiaryAccount.objects.create(account=account, code=code, name=name)


def list_detailed_accounts(params):
    subsidiary_id = (params.get("subsidiary_id") or "").strip()
    account_id = (params.get("account_id") or "").strip()
    qs = DetailedAccount.objects.filter(is_active=True).select_related(
        "subsidiary", "subsidiary__account"
    ).order_by("subsidiary__account__sort_order", "subsidiary__code", "code")
    if subsidiary_id.isdigit():
        qs = qs.filter(subsidiary_id=int(subsidiary_id))
    elif account_id.isdigit():
        qs = qs.filter(subsidiary__account_id=int(account_id))
    return [detailed_to_dict(d) for d in qs]


def create_detailed_account(*, subsidiary_id, code, name):
    code = (code or "").strip()
    name = (name or "").strip()
    if not subsidiary_id or not code or not name:
        raise ValueError("حساب معین، کد و عنوان تفصیلی الزامی است.")
    try:
        subsidiary = SubsidiaryAccount.objects.select_related("account").get(
            pk=subsidiary_id, is_active=True
        )
    except SubsidiaryAccount.DoesNotExist as exc:
        raise LookupError("حساب معین یافت نشد.") from exc
    if DetailedAccount.objects.filter(subsidiary=subsidiary, code=code).exists():
        raise ValueError("این کد تفصیلی قبلاً ثبت شده است.")
    return DetailedAccount.objects.create(subsidiary=subsidiary, code=code, name=name)


def update_general_account(*, account_id, name=None, is_active=None):
    try:
        account = Account.objects.get(pk=account_id)
    except Account.DoesNotExist as exc:
        raise LookupError("حساب کل یافت نشد.") from exc
    if name is not None:
        name = (name or "").strip()
        if not name:
            raise ValueError("عنوان حساب کل الزامی است.")
        account.name = name
    if is_active is not None:
        account.is_active = bool(is_active)
    account.save()
    return account


def update_subsidiary_account(*, sub_id, code=None, name=None, is_active=None):
    try:
        sub = SubsidiaryAccount.objects.select_related("account").get(pk=sub_id)
    except SubsidiaryAccount.DoesNotExist as exc:
        raise LookupError("حساب معین یافت نشد.") from exc
    if code is not None:
        code = (code or "").strip()
        if not code:
            raise ValueError("کد معین الزامی است.")
        if SubsidiaryAccount.objects.filter(account=sub.account, code=code).exclude(pk=sub.pk).exists():
            raise ValueError("این کد معین قبلاً ثبت شده است.")
        sub.code = code
    if name is not None:
        name = (name or "").strip()
        if not name:
            raise ValueError("عنوان حساب معین الزامی است.")
        sub.name = name
    if is_active is not None:
        sub.is_active = bool(is_active)
    sub.save()
    return sub


def update_detailed_account(*, detail_id, code=None, name=None, is_active=None):
    try:
        detail = DetailedAccount.objects.select_related("subsidiary", "subsidiary__account").get(pk=detail_id)
    except DetailedAccount.DoesNotExist as exc:
        raise LookupError("حساب تفصیلی یافت نشد.") from exc
    if code is not None:
        code = (code or "").strip()
        if not code:
            raise ValueError("کد تفصیلی الزامی است.")
        if DetailedAccount.objects.filter(subsidiary=detail.subsidiary, code=code).exclude(pk=detail.pk).exists():
            raise ValueError("این کد تفصیلی قبلاً ثبت شده است.")
        detail.code = code
    if name is not None:
        name = (name or "").strip()
        if not name:
            raise ValueError("عنوان حساب تفصیلی الزامی است.")
        detail.name = name
    if is_active is not None:
        detail.is_active = bool(is_active)
    detail.save()
    return detail
