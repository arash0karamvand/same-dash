"""فیلتر، ایجاد، ویرایش و تایید اسناد حسابداری."""

from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from backend.models import AccountingEntry, Sale

from logic.accounting import (
    SYSTEM_ENTRY_TYPES,
    assign_document_code,
    create_accounting_entry,
    entry_permissions,
    is_auto_approved_accounting_user,
    is_payment_account,
    resolve_entry_accounts,
)
from logic.accounting_accounts import accounts_grouped, resolve_account_for_entry
from logic.ledger import OFFICE_LEDGER

VALID_ENTRY_TYPES = {value for value, _ in AccountingEntry.ENTRY_TYPE_CHOICES}


def _parse_filter_amount(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def parse_entry_date(value):
    """تبدیل رشته تاریخ (YYYY-MM-DD یا ISO) به datetime آگاه از منطقه زمانی."""
    text = str(value).strip()
    parsed = parse_datetime(text)
    if parsed is None:
        date_only = parse_date(text)
        if date_only is None:
            raise ValueError("تاریخ سند نامعتبر است.")
        parsed = datetime.combine(date_only, time.min)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def parse_money(value, field_label):
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"مقدار {field_label} نامعتبر است.")
    if amount < 0:
        raise ValueError(f"مقدار {field_label} نمی‌تواند منفی باشد.")
    return amount


def apply_entry_filters(qs, params, *, ledger=OFFICE_LEDGER):
    entry_type = (params.get("type") or "").strip()
    if entry_type:
        qs = qs.filter(entry_type=entry_type)

    account_id = (params.get("account_id") or "").strip()
    if account_id.isdigit():
        qs = qs.filter(account_id=int(account_id))

    account_class = (params.get("account_class") or "").strip()
    if account_class:
        qs = qs.filter(account__account_class=account_class)

    approved = (params.get("approved") or "").strip().lower()
    if approved in ("true", "1"):
        qs = qs.filter(is_approved=True)
    elif approved in ("false", "0"):
        qs = qs.filter(is_approved=False)

    date_from = (params.get("date_from") or "").strip()
    if date_from:
        qs = qs.filter(entry_date__date__gte=date_from)
    date_to = (params.get("date_to") or "").strip()
    if date_to:
        qs = qs.filter(entry_date__date__lte=date_to)

    sale_id = (params.get("sale_id") or "").strip()
    if sale_id.isdigit():
        qs = qs.filter(sale_id=int(sale_id))

    search = (params.get("search") or "").strip()
    if search:
        search_q = (
            Q(description__icontains=search)
            | Q(document_code__icontains=search)
            | Q(account__name__icontains=search)
            | Q(general_account__icontains=search)
            | Q(subsidiary_account__icontains=search)
            | Q(detailed_account__icontains=search)
        )
        if ledger.syncs_sales:
            search_q |= (
                Q(sale__invoice_number__icontains=search)
                | Q(sale__customer__full_name__icontains=search)
                | Q(sale__customer__phone__icontains=search)
            )
        else:
            search_q |= Q(factory_order__invoice_number__icontains=search)
        qs = qs.filter(search_q)

    amount_min = _parse_filter_amount(params.get("amount_min"))
    amount_max = _parse_filter_amount(params.get("amount_max"))
    if amount_min is not None:
        qs = qs.filter(amount__gte=amount_min)
    if amount_max is not None:
        qs = qs.filter(amount__lte=amount_max)

    debit_min = _parse_filter_amount(params.get("debit_min"))
    debit_max = _parse_filter_amount(params.get("debit_max"))
    if debit_min is not None:
        qs = qs.filter(debit__gte=debit_min)
    if debit_max is not None:
        qs = qs.filter(debit__lte=debit_max)

    credit_min = _parse_filter_amount(params.get("credit_min"))
    credit_max = _parse_filter_amount(params.get("credit_max"))
    if credit_min is not None:
        qs = qs.filter(credit__gte=credit_min)
    if credit_max is not None:
        qs = qs.filter(credit__lte=credit_max)

    document_code = (params.get("document_code") or "").strip()
    if document_code:
        qs = qs.filter(document_code=document_code)

    document_number = (params.get("document_number") or "").strip()
    if document_number.isdigit():
        qs = qs.filter(document_number=int(document_number))

    subsidiary_id = (params.get("subsidiary_id") or "").strip()
    if subsidiary_id.isdigit():
        qs = qs.filter(subsidiary_id=int(subsidiary_id))

    detailed_id = (params.get("detailed_id") or "").strip()
    if detailed_id.isdigit():
        qs = qs.filter(detailed_id=int(detailed_id))

    return qs


def entry_base_queryset(*, ledger=OFFICE_LEDGER):
    EntryModel = ledger.AccountingEntry
    qs = EntryModel.objects.select_related("account")
    if ledger.syncs_sales:
        qs = qs.select_related("sale", "sale__customer").filter(
            Q(sale__isnull=True) | Q(sale__is_deleted=False)
        )
    else:
        qs = qs.select_related("factory_order")
    return qs


def list_entries(params, *, ledger=OFFICE_LEDGER):
    """فهرست اسناد با فیلتر، صفحه‌بندی و جمع مبالغ."""
    EntryModel = ledger.AccountingEntry
    qs = apply_entry_filters(entry_base_queryset(ledger=ledger), params, ledger=ledger)
    agg = qs.aggregate(
        total=Count("id"),
        total_debit=Sum("debit"),
        total_credit=Sum("credit"),
    )
    total = agg["total"] or 0

    try:
        offset = max(0, int(params.get("offset") or 0))
        limit = min(max(1, int(params.get("limit") or 50)), 1000)
    except (TypeError, ValueError):
        offset, limit = 0, 50

    results = list(qs[offset : offset + limit])
    return {
        "results": results,
        "total": total,
        "offset": offset,
        "limit": limit,
        "filtered_debit": int(agg["total_debit"] or 0),
        "filtered_credit": int(agg["total_credit"] or 0),
        "types": [
            {"value": value, "label": label}
            for value, label in EntryModel.ENTRY_TYPE_CHOICES
        ],
        "accounts": accounts_grouped(ledger=ledger),
    }


def get_entry(pk, *, ledger=OFFICE_LEDGER):
    EntryModel = ledger.AccountingEntry
    try:
        if ledger.syncs_sales:
            return EntryModel.objects.select_related("sale", "sale__customer", "account").get(pk=pk)
        return EntryModel.objects.select_related("factory_order", "account").get(pk=pk)
    except EntryModel.DoesNotExist as exc:
        raise LookupError("Entry not found") from exc


def _resolve_sale(sale_id):
    if not sale_id:
        return None
    try:
        return Sale.objects.get(pk=sale_id)
    except Sale.DoesNotExist as exc:
        raise LookupError("Sale not found") from exc


def _create_payment_entry(*, sale, account, effective_amount, description, document_code, user):
    from logic.accounting_money import to_rial
    from logic.sales import balance_due, record_payment

    due = balance_due(sale)
    due_rial = to_rial(due)
    if effective_amount > due_rial:
        raise ValueError(f"مبلغ پرداخت بیش از مانده فاکتور ({due_rial} ریال) است.")
    amount_to_apply = Decimal(effective_amount)
    record_payment(
        sale,
        amount_to_apply,
        description=description,
        recorded_by=user,
        account=account,
    )
    payment_entry = (
        AccountingEntry.objects.filter(sale=sale, entry_type="payment")
        .order_by("-id")
        .first()
    )
    if payment_entry:
        if document_code:
            if (
                AccountingEntry.objects.filter(document_code=document_code)
                .exclude(pk=payment_entry.pk)
                .exists()
            ):
                raise ValueError("این کد سند قبلاً ثبت شده است.")
            payment_entry.document_code = document_code
            payment_entry.save(update_fields=["document_code"])
        elif not payment_entry.document_code:
            assign_document_code(payment_entry)
    return payment_entry, amount_to_apply


def create_entry_from_data(data, *, user, ledger=OFFICE_LEDGER):
    """ایجاد سند دستی یا ثبت پرداخت روی فاکتور.

    Returns:
        (entry, meta) where meta may include payment_amount_rial for audit logs.
    """
    entry_type = (data.get("entry_type") or "").strip() or None

    try:
        account = resolve_account_for_entry(
            account_id=data.get("account_id"),
            account_slug=(data.get("account_slug") or "").strip() or None,
            entry_type=entry_type,
            ledger=ledger,
        )
    except Exception as exc:
        raise ValueError("حساب سند نامعتبر است.") from exc

    if not entry_type:
        entry_type = account.legacy_entry_type or "other"
    if entry_type not in VALID_ENTRY_TYPES:
        raise ValueError("نوع سند نامعتبر است.")

    amount = parse_money(data.get("amount"), "مبلغ")
    debit = parse_money(data.get("debit"), "بدهکار")
    credit = parse_money(data.get("credit"), "بستانکار")
    opening_debit = parse_money(data.get("opening_debit"), "افتتاحیه بدهکار")
    opening_credit = parse_money(data.get("opening_credit"), "افتتاحیه بستانکار")
    balance_debit = parse_money(data.get("balance_debit"), "مانده بدهکار")
    balance_credit = parse_money(data.get("balance_credit"), "مانده بستانکار")

    effective_amount = amount or debit or credit
    money_total = effective_amount + opening_debit + opening_credit + balance_debit + balance_credit
    if money_total <= 0:
        raise ValueError("حداقل یکی از مبالغ سند باید بزرگ‌تر از صفر باشد.")

    description = (data.get("description") or "").strip()
    if not description:
        raise ValueError("شرح سند الزامی است.")

    EntryModel = ledger.AccountingEntry
    document_code = (data.get("document_code") or "").strip()
    if document_code and EntryModel.objects.filter(document_code=document_code).exists():
        raise ValueError("این کد سند قبلاً ثبت شده است.")

    general_account = (data.get("general_account") or "").strip()
    subsidiary_account = (data.get("subsidiary_account") or "").strip()
    detailed_account = (data.get("detailed_account") or "").strip()

    sale = _resolve_sale(data.get("sale_id")) if ledger.syncs_sales else None

    if ledger.syncs_sales and sale and (entry_type == "payment" or is_payment_account(account)):
        payment_entry, amount_to_apply = _create_payment_entry(
            sale=sale,
            account=account,
            effective_amount=effective_amount,
            description=description,
            document_code=document_code,
            user=user,
        )
        return payment_entry, {
            "kind": "payment",
            "amount_rial": int(amount_to_apply),
            "sale": sale,
        }

    entry_date_parsed = None
    if data.get("entry_date"):
        entry_date_parsed = parse_entry_date(data["entry_date"])

    entry = create_accounting_entry(
        entry_type=entry_type,
        account=account,
        debit=debit,
        credit=credit,
        amount=effective_amount or money_total,
        description=description,
        sale=sale,
        is_approved=bool(data.get("is_approved", False)) or is_auto_approved_accounting_user(user, ledger=ledger),
        document_code=document_code,
        opening_debit=opening_debit,
        opening_credit=opening_credit,
        balance_debit=balance_debit,
        balance_credit=balance_credit,
        entry_date=entry_date_parsed,
        general_account=general_account,
        subsidiary_account=subsidiary_account,
        detailed_account=detailed_account,
        ledger=ledger,
    )
    if entry_date_parsed and entry.entry_date != entry_date_parsed:
        entry.entry_date = entry_date_parsed
        entry.save(update_fields=["entry_date"])

    return entry, {"kind": "manual", "account": account}


def update_entry_from_data(entry, data, *, user, ledger=OFFICE_LEDGER):
    """ویرایش سند — حالت کامل یا جزئی بر اساس مجوز."""
    if getattr(entry, "transferred_to_office_at", None):
        raise ValueError("سند منتقل‌شده به اداری قابل ویرایش نیست.")
    if entry.is_approved and not is_auto_approved_accounting_user(user, ledger=ledger):
        raise ValueError("سند تاییدشده قابل ویرایش نیست؛ ابتدا تایید را لغو کنید.")

    perms = entry_permissions(entry, user=user, ledger=ledger)
    if not perms["can_edit"]:
        raise ValueError("این سند قابل ویرایش نیست.")
    partial = perms["edit_mode"] == "partial"

    if partial:
        if "description" in data:
            description = (data.get("description") or "").strip()
            if not description:
                raise ValueError("شرح سند الزامی است.")
            entry.description = description
        if data.get("entry_date"):
            entry.entry_date = parse_entry_date(data["entry_date"])
        entry.save()
        if entry.sale_id and entry.entry_type == "sale" and "description" in data:
            sale = entry.sale
            sale.description = entry.description
            sale.save(update_fields=["description"])
            from logic.order_queues import sync_workflow_orders_from_sale

            sync_workflow_orders_from_sale(sale)
        return entry, {"kind": "partial"}

    if "entry_type" in data:
        entry_type = (data.get("entry_type") or "").strip()
        if entry_type not in VALID_ENTRY_TYPES:
            raise ValueError("نوع سند نامعتبر است.")
        if entry.sale_id and entry_type in SYSTEM_ENTRY_TYPES:
            raise ValueError("سند متصل به فروش را نمی‌توان به نوع سیستمی تغییر داد.")
        entry.entry_type = entry_type

    if "account_id" in data and not partial:
        try:
            entry.account = resolve_account_for_entry(account_id=data.get("account_id"), ledger=ledger)
        except Exception as exc:
            raise ValueError("حساب سند نامعتبر است.") from exc

    if "debit" in data:
        entry.debit = parse_money(data.get("debit"), "بدهکار")
    if "credit" in data:
        entry.credit = parse_money(data.get("credit"), "بستانکار")
    if "amount" in data:
        entry.amount = parse_money(data.get("amount"), "مبلغ")
    if "opening_debit" in data:
        entry.opening_debit = parse_money(data.get("opening_debit"), "افتتاحیه بدهکار")
    if "opening_credit" in data:
        entry.opening_credit = parse_money(data.get("opening_credit"), "افتتاحیه بستانکار")
    if "balance_debit" in data:
        entry.balance_debit = parse_money(data.get("balance_debit"), "مانده بدهکار")
    if "balance_credit" in data:
        entry.balance_credit = parse_money(data.get("balance_credit"), "مانده بستانکار")

    if "document_code" in data and not partial:
        document_code = (data.get("document_code") or "").strip()
        if (
            document_code
            and ledger.AccountingEntry.objects.filter(document_code=document_code)
            .exclude(pk=entry.pk)
            .exists()
        ):
            raise ValueError("این کد سند قبلاً ثبت شده است.")
        entry.document_code = document_code

    if not partial:
        if "general_account" in data:
            entry.general_account = (data.get("general_account") or "").strip()
        if "subsidiary_account" in data:
            entry.subsidiary_account = (data.get("subsidiary_account") or "").strip()
        if "detailed_account" in data:
            entry.detailed_account = (data.get("detailed_account") or "").strip()
        general, subsidiary, detailed = resolve_entry_accounts(
            entry.account,
            general=entry.general_account,
            subsidiary=entry.subsidiary_account,
            detailed=entry.detailed_account,
        )
        entry.general_account = general
        entry.subsidiary_account = subsidiary
        entry.detailed_account = detailed

    entry.amount = entry.amount or entry.debit or entry.credit
    money_total = (
        int(entry.amount or 0)
        + int(entry.opening_debit or 0)
        + int(entry.opening_credit or 0)
        + int(entry.balance_debit or 0)
        + int(entry.balance_credit or 0)
    )
    if money_total <= 0:
        raise ValueError("حداقل یکی از مبالغ سند باید بزرگ‌تر از صفر باشد.")

    if "description" in data:
        description = (data.get("description") or "").strip()
        if not description:
            raise ValueError("شرح سند الزامی است.")
        entry.description = description

    if data.get("entry_date"):
        entry.entry_date = parse_entry_date(data["entry_date"])

    entry.save()
    if not entry.document_code:
        assign_document_code(entry, ledger=ledger)
    return entry, {"kind": "full"}


def set_entry_approval(entry, is_approved):
    entry.is_approved = bool(is_approved)
    entry.save(update_fields=["is_approved"])
    return entry


def bulk_approve_entries(ids=None, *, ledger=OFFICE_LEDGER):
    """تایید گروهی — با شناسه‌ها یا همه اسناد در انتظار."""
    qs = ledger.AccountingEntry.objects.filter(is_approved=False)
    if ids:
        if not isinstance(ids, list):
            raise ValueError("فهرست شناسه‌ها نامعتبر است.")
        qs = qs.filter(pk__in=ids)
    return qs.update(is_approved=True)
