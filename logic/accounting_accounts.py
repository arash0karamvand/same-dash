"""Chart of accounts CRUD and seed — definitions live in chart_of_accounts.py."""

from django.db.models import Max

from backend.models import Account, AccountClosure
from logic.chart_of_accounts import (
    ACCOUNT_CLASS_LABELS,
    CHART_OF_ACCOUNTS,
    ENTRY_TYPE_TO_SLUG,
    PAYMENT_METHOD_TO_SLUG,
)
from logic.ledger import OFFICE_LEDGER

# Backward-compatible aliases
ENTRY_TYPE_ACCOUNT_SLUGS = ENTRY_TYPE_TO_SLUG
PAYMENT_METHOD_ACCOUNT_SLUGS = PAYMENT_METHOD_TO_SLUG


def _accounts(ledger=OFFICE_LEDGER):
    return Account.objects.filter(ledger__code=ledger.id)


def _depth(depth, ledger=OFFICE_LEDGER):
    qs = _accounts(ledger)
    if depth == 0:
        return qs.filter(parent__isnull=True)
    if depth == 1:
        return qs.filter(parent__isnull=False, parent__parent__isnull=True)
    if depth == 2:
        return qs.filter(
            parent__isnull=False,
            parent__parent__isnull=False,
            parent__parent__parent__isnull=True,
        )
    return qs.none()


def seed_accounts(*, ledger=OFFICE_LEDGER):
    ledger_row = ledger.model
    for row in CHART_OF_ACCOUNTS:
        Account.objects.update_or_create(
            ledger=ledger_row,
            slug=row["slug"],
            defaults={**row, "is_active": True, "parent": None},
        )


def get_account(slug, *, required=True, ledger=OFFICE_LEDGER):
    account = _accounts(ledger).filter(slug=slug, is_active=True).first()
    if not account:
        seed_accounts(ledger=ledger)
        account = _accounts(ledger).filter(slug=slug, is_active=True).first()
    if not account and required:
        raise ValueError(f"حساب «{slug}» یافت نشد.")
    return account


def resolve_account_for_entry(*, account_id=None, account_slug=None, entry_type=None, ledger=OFFICE_LEDGER):
    qs = _accounts(ledger).filter(is_active=True)
    if account_id:
        return qs.get(pk=account_id)
    if account_slug:
        return get_account(account_slug, ledger=ledger)
    slug = ENTRY_TYPE_TO_SLUG.get(entry_type)
    if slug:
        return get_account(slug, ledger=ledger)
    raise ValueError("حساب سند مشخص نشده است.")


def payment_account_for_sale(sale, *, ledger=OFFICE_LEDGER):
    return get_account(
        PAYMENT_METHOD_TO_SLUG.get(sale.payment_method or "cash", "bank"),
        ledger=ledger,
    )


def resolve_sale_accounting_mode(requested, payment_method):
    from backend.models import Sale

    mode = (requested or Sale.ACCOUNTING_MODE_AUTOMATIC).strip()
    if mode not in (Sale.ACCOUNTING_MODE_AUTOMATIC, Sale.ACCOUNTING_MODE_MANUAL):
        raise ValueError("نوع ثبت حسابداری نامعتبر است.")
    return mode if mode == Sale.ACCOUNTING_MODE_MANUAL or payment_method in PAYMENT_METHOD_TO_SLUG else Sale.ACCOUNTING_MODE_MANUAL


def payment_account_label_for_sale(sale):
    account = payment_account_for_sale(sale)
    return f"{account.code} — {account.name}".strip(" —")


def account_to_dict(account):
    return {
        "id": account.id,
        "slug": account.slug,
        "code": account.code,
        "full_code": account.full_code,
        "name": account.name,
        "account_class": account.account_class,
        "account_class_label": account.get_account_class_display(),
        "normal_balance": account.normal_balance,
        "sort_order": account.sort_order,
        "legacy_entry_type": account.legacy_entry_type or None,
        "is_active": account.is_active,
        "parent_id": account.parent_id,
    }


def subsidiary_to_dict(sub):
    parent = sub.parent
    return {
        "id": sub.id,
        "account_id": parent.id,
        "code": sub.code,
        "full_code": sub.full_code,
        "name": sub.name,
        "is_active": sub.is_active,
        "general_code": parent.code,
        "general_name": parent.name,
    }


def detailed_to_dict(detail):
    sub, general = detail.parent, detail.parent.parent
    return {
        "id": detail.id,
        "subsidiary_id": sub.id,
        "account_id": general.id,
        "code": detail.code,
        "full_code": detail.full_code,
        "name": detail.name,
        "is_active": detail.is_active,
        "subsidiary_code": sub.full_code,
        "subsidiary_name": sub.name,
        "general_code": general.code,
        "general_name": general.name,
    }


def accounts_grouped(*, ledger=OFFICE_LEDGER):
    seed_accounts(ledger=ledger)
    groups = []
    for key, label in ACCOUNT_CLASS_LABELS.items():
        qs = _depth(0, ledger).filter(account_class=key, is_active=True).order_by("sort_order", "name")
        groups.append({"class": key, "class_label": label, "accounts": [account_to_dict(a) for a in qs]})
    return groups


def resolve_line_accounts(*, account_id=None, subsidiary_id=None, detailed_id=None, ledger=OFFICE_LEDGER):
    qs = _accounts(ledger).filter(is_active=True)
    selected = None
    expected_depth = None
    try:
        if detailed_id:
            selected, expected_depth = qs.get(pk=detailed_id), 2
        elif subsidiary_id:
            selected, expected_depth = qs.get(pk=subsidiary_id), 1
        elif account_id:
            selected, expected_depth = qs.get(pk=account_id), 0
        else:
            raise ValueError("حداقل حساب کل باید مشخص شود.")
    except Account.DoesNotExist as exc:
        raise ValueError("حساب انتخاب‌شده متعلق به این دفتر نیست.") from exc
    depth = selected.ancestor_paths.aggregate(value=Max("depth"))["value"]
    if depth != expected_depth:
        raise ValueError("سطح حساب انتخاب‌شده نامعتبر است.")
    if expected_depth == 2:
        return selected, selected.parent, selected
    if expected_depth == 1:
        return selected, selected, None
    return selected, None, None


def list_document_models(params, *, ledger=OFFICE_LEDGER):
    accounts = _depth(0, ledger).filter(is_active=True).order_by("sort_order", "name")
    models = []
    for account in accounts:
        info = account_to_dict(account)
        info["account_code"] = account.code
        info["entry_count"] = account.journal_lines.filter(journal__ledger__code=ledger.id).count()
        models.append(info)
    return {"models": models, "accounts": accounts_grouped(ledger=ledger)}


def list_subsidiary_accounts(params, *, ledger=OFFICE_LEDGER):
    qs = _depth(1, ledger).filter(is_active=True).select_related("parent")
    if str(params.get("account_id") or "").isdigit():
        qs = qs.filter(parent_id=int(params["account_id"]))
    return [subsidiary_to_dict(a) for a in qs.order_by("parent__sort_order", "code")]


def list_detailed_accounts(params, *, ledger=OFFICE_LEDGER):
    qs = _depth(2, ledger).filter(is_active=True).select_related("parent", "parent__parent")
    if str(params.get("subsidiary_id") or "").isdigit():
        qs = qs.filter(parent_id=int(params["subsidiary_id"]))
    elif str(params.get("account_id") or "").isdigit():
        qs = qs.filter(parent__parent_id=int(params["account_id"]))
    return [detailed_to_dict(a) for a in qs.order_by("parent__parent__sort_order", "parent__code", "code")]


def _create_child(parent, code, name):
    code, name = (code or "").strip(), (name or "").strip()
    if not code or not name:
        raise ValueError("کد و عنوان حساب الزامی است.")
    if Account.objects.filter(ledger=parent.ledger, code=code).exists():
        raise ValueError("این کد حساب قبلاً ثبت شده است.")
    return Account.objects.create(
        ledger=parent.ledger,
        parent=parent,
        slug=f"{parent.slug}-{code}",
        code=code,
        name=name,
        account_class=parent.account_class,
        normal_balance=parent.normal_balance,
    )


def create_subsidiary_account(*, account_id, code, name, ledger=OFFICE_LEDGER):
    parent = _depth(0, ledger).get(pk=account_id, is_active=True)
    return _create_child(parent, code, name)


def create_detailed_account(*, subsidiary_id, code, name, ledger=OFFICE_LEDGER):
    parent = _depth(1, ledger).get(pk=subsidiary_id, is_active=True)
    return _create_child(parent, code, name)


def _update(account, code=None, name=None, is_active=None):
    if code is not None:
        account.code = (code or "").strip()
    if name is not None:
        account.name = (name or "").strip()
    if is_active is not None:
        account.is_active = bool(is_active)
    if not account.code or not account.name:
        raise ValueError("کد و عنوان حساب الزامی است.")
    account.save()
    return account


def update_general_account(*, account_id, name=None, is_active=None, ledger=OFFICE_LEDGER):
    return _update(_depth(0, ledger).get(pk=account_id), name=name, is_active=is_active)


def update_subsidiary_account(*, sub_id, code=None, name=None, is_active=None, ledger=OFFICE_LEDGER):
    return _update(_depth(1, ledger).get(pk=sub_id), code, name, is_active)


def update_detailed_account(*, detail_id, code=None, name=None, is_active=None, ledger=OFFICE_LEDGER):
    return _update(_depth(2, ledger).get(pk=detail_id), code, name, is_active)
