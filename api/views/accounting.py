"""endpointهای حسابداری — /api/accounting/."""

from decimal import Decimal, InvalidOperation

from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse

from backend.models import Account, AccountingEntry, Customer, DetailedAccount, Sale, SubsidiaryAccount

from api.helpers import api_view, fail, parse_json, success
from api.serializers import accounting_to_dict, sale_to_dict
from auth.permissions import (
    APPROVE_ACCOUNTING,
    CREATE_ACCOUNTING,
    DELETE_ACCOUNTING,
    EDIT_ACCOUNTING,
    VIEW_ACCOUNTING,
    VIEW_REPORTS,
    has_permission,
)
from logic.accounting import (
    SYSTEM_ENTRY_TYPES,
    create_accounting_entry,
    delete_accounting_entry,
    entry_permissions,
    is_office_accounting_user,
    is_payment_account,
    is_system_entry,
)
from logic.accounting_accounts import accounts_grouped, detailed_to_dict, resolve_account_for_entry, subsidiary_to_dict
from logic.accounting_documents import create_accounting_document
from logic.accounting_ledger import ledger_for_accounts, ledger_totals
from logic.accounting_reports import detail_ledger, trial_balance_detailed, trial_balance_general, trial_balance_subsidiary
from logic.audit import log_action

VALID_ENTRY_TYPES = {value for value, _ in AccountingEntry.ENTRY_TYPE_CHOICES}


@api_view("GET", permission=VIEW_ACCOUNTING)
def account_list(request):
    return success({"accounts": accounts_grouped()})


@api_view("GET", permission=VIEW_ACCOUNTING)
def document_models(request):
    """مدل‌های سند (حساب‌های دفتر کل) به همراه تعداد اسناد."""
    from logic.accounting_accounts import account_to_dict, seed_accounts

    seed_accounts()
    accounts = Account.objects.filter(is_active=True).order_by("sort_order", "name")
    account_class = (request.GET.get("account_class") or "").strip()
    if account_class:
        accounts = accounts.filter(account_class=account_class)

    entry_qs = _apply_filters(
        AccountingEntry.objects.filter(account__isnull=False).filter(
            Q(sale__isnull=True) | Q(sale__is_deleted=False)
        ),
        request.GET,
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

    return success({"models": models, "accounts": accounts_grouped()})


@api_view("GET", permission=VIEW_ACCOUNTING)
def ledger(request):
    date_from = (request.GET.get("date_from") or "").strip() or None
    date_to = (request.GET.get("date_to") or "").strip() or None
    account_class = (request.GET.get("account_class") or "").strip() or None
    approved_only = (request.GET.get("approved_only") or "").strip().lower() in ("true", "1")

    rows = ledger_for_accounts(
        date_from=date_from,
        date_to=date_to,
        account_class=account_class,
        approved_only=approved_only,
    )
    totals = ledger_totals(rows)

    try:
        limit = min(max(1, int(request.GET.get("limit") or 20)), 500)
    except (TypeError, ValueError):
        limit = 20

    return success(
        {
            "results": rows[:limit],
            "total": len(rows),
            "limit": limit,
            "totals": totals,
        }
    )


def _parse_entry_date(value):
    """تبدیل رشته تاریخ (YYYY-MM-DD یا ISO) به datetime آگاه از منطقه زمانی."""
    from datetime import datetime, time

    from django.utils import timezone
    from django.utils.dateparse import parse_date, parse_datetime

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


def _parse_money(value, field_label):
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"مقدار {field_label} نامعتبر است.")
    if amount < 0:
        raise ValueError(f"مقدار {field_label} نمی‌تواند منفی باشد.")
    return amount


def _apply_filters(qs, params):
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
        qs = qs.filter(
            Q(description__icontains=search)
            | Q(document_code__icontains=search)
            | Q(sale__invoice_number__icontains=search)
            | Q(sale__customer__full_name__icontains=search)
            | Q(sale__customer__phone__icontains=search)
            | Q(account__name__icontains=search)
            | Q(general_account__icontains=search)
            | Q(subsidiary_account__icontains=search)
            | Q(detailed_account__icontains=search)
        )
    return qs


@api_view("GET", "POST")
def entry_list(request):
    if request.method == "GET":
        if not has_permission(request.user, VIEW_ACCOUNTING):
            return fail("Permission denied", status=403)

        qs = _apply_filters(
            AccountingEntry.objects.select_related(
                "sale", "sale__customer", "account"
            ).filter(
                Q(sale__isnull=True) | Q(sale__is_deleted=False)
            ),
            request.GET,
        )

        agg = qs.aggregate(
            total=Count("id"),
            total_debit=Sum("debit"),
            total_credit=Sum("credit"),
        )
        total = agg["total"] or 0

        try:
            offset = max(0, int(request.GET.get("offset") or 0))
            limit = min(max(1, int(request.GET.get("limit") or 50)), 1000)
        except (TypeError, ValueError):
            offset, limit = 0, 50

        results = qs[offset : offset + limit]
        return success(
            {
                "results": [accounting_to_dict(e, user=request.user) for e in results],
                "total": total,
                "offset": offset,
                "limit": limit,
                "filtered_debit": int(agg["total_debit"] or 0),
                "filtered_credit": int(agg["total_credit"] or 0),
                "types": [
                    {"value": value, "label": label}
                    for value, label in AccountingEntry.ENTRY_TYPE_CHOICES
                ],
                "accounts": accounts_grouped(),
            }
        )

    if not has_permission(request.user, CREATE_ACCOUNTING):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    entry_type = (data.get("entry_type") or "").strip() or None

    try:
        account = resolve_account_for_entry(
            account_id=data.get("account_id"),
            account_slug=(data.get("account_slug") or "").strip() or None,
            entry_type=entry_type,
        )
    except Exception:
        return fail("حساب سند نامعتبر است.", status=400)

    if not entry_type:
        entry_type = account.legacy_entry_type or "other"
    if entry_type not in VALID_ENTRY_TYPES:
        return fail("نوع سند نامعتبر است.", status=400)

    try:
        amount = _parse_money(data.get("amount"), "مبلغ")
        debit = _parse_money(data.get("debit"), "بدهکار")
        credit = _parse_money(data.get("credit"), "بستانکار")
        opening_debit = _parse_money(data.get("opening_debit"), "افتتاحیه بدهکار")
        opening_credit = _parse_money(data.get("opening_credit"), "افتتاحیه بستانکار")
        balance_debit = _parse_money(data.get("balance_debit"), "مانده بدهکار")
        balance_credit = _parse_money(data.get("balance_credit"), "مانده بستانکار")
    except ValueError as exc:
        return fail(str(exc), status=400)

    effective_amount = amount or debit or credit
    money_total = effective_amount + opening_debit + opening_credit + balance_debit + balance_credit
    if money_total <= 0:
        return fail("حداقل یکی از مبالغ سند باید بزرگ‌تر از صفر باشد.", status=400)

    description = (data.get("description") or "").strip()
    if not description:
        return fail("شرح سند الزامی است.", status=400)

    document_code = (data.get("document_code") or "").strip()
    if document_code and AccountingEntry.objects.filter(document_code=document_code).exists():
        return fail("این کد سند قبلاً ثبت شده است.", status=400)

    general_account = (data.get("general_account") or "").strip()
    subsidiary_account = (data.get("subsidiary_account") or "").strip()
    detailed_account = (data.get("detailed_account") or "").strip()

    sale = None
    if data.get("sale_id"):
        try:
            sale = Sale.objects.get(pk=data["sale_id"])
        except Sale.DoesNotExist:
            return fail("Sale not found", status=404)

    if sale and (entry_type == "payment" or is_payment_account(account)):
        try:
            from decimal import Decimal

            from logic.accounting_money import TOMAN_TO_RIAL, to_rial_from_toman
            from logic.sales import balance_due, record_payment

            due = balance_due(sale)
            due_rial = to_rial_from_toman(due)
            if effective_amount > due_rial:
                return fail(f"مبلغ پرداخت بیش از مانده فاکتور ({due_rial} ریال) است.", status=400)
            amount_to_apply = Decimal(effective_amount) / TOMAN_TO_RIAL
            record_payment(
                sale,
                amount_to_apply,
                description=description,
                recorded_by=request.user,
                account=account,
            )
            payment_entry = (
                AccountingEntry.objects.filter(sale=sale, entry_type="payment")
                .order_by("-id")
                .first()
            )
            if payment_entry:
                from logic.accounting import assign_document_code

                if document_code:
                    if AccountingEntry.objects.filter(document_code=document_code).exclude(pk=payment_entry.pk).exists():
                        return fail("این کد سند قبلاً ثبت شده است.", status=400)
                    payment_entry.document_code = document_code
                    payment_entry.save(update_fields=["document_code"])
                elif not payment_entry.document_code:
                    assign_document_code(payment_entry)
            log_action(
                request.user,
                "create",
                f"دریافت وجه فاکتور {sale.invoice_number or sale.pk} — {int(amount_to_apply)}",
                entity_type="AccountingEntry",
                entity_id=payment_entry.id if payment_entry else None,
            )
            return success(accounting_to_dict(payment_entry, user=request.user), status=201)
        except ValueError as exc:
            return fail(str(exc), status=400)

    entry_date_parsed = None
    if data.get("entry_date"):
        try:
            entry_date_parsed = _parse_entry_date(data["entry_date"])
        except ValueError as exc:
            return fail(str(exc), status=400)

    entry = create_accounting_entry(
        entry_type=entry_type,
        account=account,
        debit=debit,
        credit=credit,
        amount=effective_amount or money_total,
        description=description,
        sale=sale,
        is_approved=bool(data.get("is_approved", False)) or is_office_accounting_user(request.user),
        document_code=document_code,
        opening_debit=opening_debit,
        opening_credit=opening_credit,
        balance_debit=balance_debit,
        balance_credit=balance_credit,
        entry_date=entry_date_parsed,
        general_account=general_account,
        subsidiary_account=subsidiary_account,
        detailed_account=detailed_account,
    )
    if entry_date_parsed and entry.entry_date != entry_date_parsed:
        entry.entry_date = entry_date_parsed
        entry.save(update_fields=["entry_date"])

    log_action(
        request.user,
        "create",
        f"سند حسابداری {account.name} — {int(entry.amount)}",
        entity_type="AccountingEntry",
        entity_id=entry.id,
    )
    return success(accounting_to_dict(entry, user=request.user), status=201)


@api_view("GET", "PUT", "DELETE")
def entry_detail(request, pk):
    try:
        entry = AccountingEntry.objects.select_related("sale", "sale__customer", "account").get(pk=pk)
    except AccountingEntry.DoesNotExist:
        return fail("Entry not found", status=404)

    if request.method == "GET":
        if not has_permission(request.user, VIEW_ACCOUNTING):
            return fail("Permission denied", status=403)
        return success(accounting_to_dict(entry, user=request.user))

    if request.method == "DELETE":
        if not (
            has_permission(request.user, DELETE_ACCOUNTING)
            or has_permission(request.user, APPROVE_ACCOUNTING)
        ):
            return fail("Permission denied", status=403)
        summary_text = f"{entry.get_entry_type_display()} — {int(entry.amount)}"
        sale_id = entry.sale_id
        try:
            result = delete_accounting_entry(entry, user=request.user)
        except ValueError as exc:
            return fail(str(exc), status=400)
        log_action(
            request.user,
            "delete",
            f"حذف سند حسابداری {summary_text}"
            + (f" (فاکتور #{sale_id})" if sale_id else "")
            + (" — فاکتور از همه بخش‌ها حذف شد" if result.get("sale_deleted") else ""),
            entity_type="AccountingEntry",
            entity_id=result.get("entry_id"),
        )
        return success(result)

    # PUT — ویرایش سند
    if not (
        has_permission(request.user, EDIT_ACCOUNTING)
        or has_permission(request.user, CREATE_ACCOUNTING)
    ):
        return fail("Permission denied", status=403)
    if entry.is_approved and not is_office_accounting_user(request.user):
        return fail("سند تاییدشده قابل ویرایش نیست؛ ابتدا تایید را لغو کنید.", status=400)

    data = parse_json(request)
    perms = entry_permissions(entry, user=request.user)
    if not perms["can_edit"]:
        return fail("این سند قابل ویرایش نیست.", status=400)
    partial = perms["edit_mode"] == "partial"

    if partial:
        # اسناد فاکتور: فقط شرح و تاریخ
        if "description" in data:
            description = (data.get("description") or "").strip()
            if not description:
                return fail("شرح سند الزامی است.", status=400)
            entry.description = description
        if data.get("entry_date"):
            try:
                entry.entry_date = _parse_entry_date(data["entry_date"])
            except ValueError as exc:
                return fail(str(exc), status=400)
        entry.save()
        if entry.sale_id and entry.entry_type == "sale" and "description" in data:
            sale = entry.sale
            sale.description = entry.description
            sale.save(update_fields=["description"])
            from logic.order_queues import sync_workflow_orders_from_sale

            sync_workflow_orders_from_sale(sale)
        log_action(
            request.user,
            "update",
            f"ویرایش شرح/تاریخ سند #{entry.id}",
            entity_type="AccountingEntry",
            entity_id=entry.id,
        )
        return success(accounting_to_dict(entry, user=request.user))

    if "entry_type" in data:
        entry_type = (data.get("entry_type") or "").strip()
        if entry_type not in VALID_ENTRY_TYPES:
            return fail("نوع سند نامعتبر است.", status=400)
        if entry.sale_id and entry_type in SYSTEM_ENTRY_TYPES:
            return fail("سند متصل به فروش را نمی‌توان به نوع سیستمی تغییر داد.", status=400)
        entry.entry_type = entry_type

    if "account_id" in data and not partial:
        try:
            entry.account = resolve_account_for_entry(account_id=data.get("account_id"))
        except Exception:
            return fail("حساب سند نامعتبر است.", status=400)

    try:
        if "debit" in data:
            entry.debit = _parse_money(data.get("debit"), "بدهکار")
        if "credit" in data:
            entry.credit = _parse_money(data.get("credit"), "بستانکار")
        if "amount" in data:
            entry.amount = _parse_money(data.get("amount"), "مبلغ")
        if "opening_debit" in data:
            entry.opening_debit = _parse_money(data.get("opening_debit"), "افتتاحیه بدهکار")
        if "opening_credit" in data:
            entry.opening_credit = _parse_money(data.get("opening_credit"), "افتتاحیه بستانکار")
        if "balance_debit" in data:
            entry.balance_debit = _parse_money(data.get("balance_debit"), "مانده بدهکار")
        if "balance_credit" in data:
            entry.balance_credit = _parse_money(data.get("balance_credit"), "مانده بستانکار")
    except ValueError as exc:
        return fail(str(exc), status=400)

    if "document_code" in data and not partial:
        document_code = (data.get("document_code") or "").strip()
        if document_code and AccountingEntry.objects.filter(document_code=document_code).exclude(pk=entry.pk).exists():
            return fail("این کد سند قبلاً ثبت شده است.", status=400)
        entry.document_code = document_code

    if not partial:
        if "general_account" in data:
            entry.general_account = (data.get("general_account") or "").strip()
        if "subsidiary_account" in data:
            entry.subsidiary_account = (data.get("subsidiary_account") or "").strip()
        if "detailed_account" in data:
            entry.detailed_account = (data.get("detailed_account") or "").strip()
        from logic.accounting import resolve_entry_accounts

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
        return fail("حداقل یکی از مبالغ سند باید بزرگ‌تر از صفر باشد.", status=400)

    if "description" in data:
        description = (data.get("description") or "").strip()
        if not description:
            return fail("شرح سند الزامی است.", status=400)
        entry.description = description

    if data.get("entry_date"):
        try:
            entry.entry_date = _parse_entry_date(data["entry_date"])
        except ValueError as exc:
            return fail(str(exc), status=400)

    entry.save()
    if not entry.document_code:
        from logic.accounting import assign_document_code

        assign_document_code(entry)
    log_action(
        request.user,
        "update",
        f"ویرایش سند حسابداری #{entry.id} — {int(entry.amount)}",
        entity_type="AccountingEntry",
        entity_id=entry.id,
    )
    return success(accounting_to_dict(entry, user=request.user))


@api_view("PUT", permission=APPROVE_ACCOUNTING)
def entry_approve(request, pk):
    try:
        entry = AccountingEntry.objects.get(pk=pk)
    except AccountingEntry.DoesNotExist:
        return fail("Entry not found", status=404)
    data = parse_json(request)
    entry.is_approved = bool(data.get("is_approved"))
    entry.save(update_fields=["is_approved"])
    log_action(
        request.user,
        "approve" if entry.is_approved else "update",
        f"{'تایید' if entry.is_approved else 'لغو تایید'} سند حسابداری #{entry.id}",
        entity_type="AccountingEntry",
        entity_id=entry.id,
    )
    return success(accounting_to_dict(entry, user=request.user))


@api_view("POST", permission=APPROVE_ACCOUNTING)
def bulk_approve(request):
    """تایید گروهی اسناد — با شناسه‌ها یا همه اسناد در انتظار."""
    data = parse_json(request)
    ids = data.get("ids")

    qs = AccountingEntry.objects.filter(is_approved=False)
    if ids:
        if not isinstance(ids, list):
            return fail("فهرست شناسه‌ها نامعتبر است.", status=400)
        qs = qs.filter(pk__in=ids)

    updated = qs.update(is_approved=True)
    if updated:
        log_action(
            request.user,
            "approve",
            f"تایید گروهی {updated} سند حسابداری",
            entity_type="AccountingEntry",
        )
    return success({"approved_count": updated})


@api_view("GET", permission=VIEW_ACCOUNTING)
def summary(request):
    entries = _apply_filters(AccountingEntry.objects.all(), request.GET)
    agg = entries.aggregate(
        total_debit=Sum("debit"),
        total_credit=Sum("credit"),
        total_amount=Sum("amount"),
        count=Count("id"),
        approved_count=Count("id", filter=Q(is_approved=True)),
        pending_count=Count("id", filter=Q(is_approved=False)),
        total_receivables=Sum("debit", filter=Q(account__slug="receivables") | Q(entry_type="receivable")),
        total_payments=Sum("credit", filter=Q(account__slug__in=["bank", "cash_documents", "petty_cash", "collection_at_bank"]) | Q(entry_type="payment")),
        total_refunds=Sum("amount", filter=Q(entry_type="refund")),
    )

    due_agg = Sale.objects.filter(final_amount__gt=F("paid_amount")).aggregate(
        total=Sum(F("final_amount") - F("paid_amount")),
        open_invoices=Count("id"),
    )

    return success(
        {
            "total_debit": int(agg["total_debit"] or 0),
            "total_credit": int(agg["total_credit"] or 0),
            "total_amount": int(agg["total_amount"] or 0),
            "total_receivables": int(agg["total_receivables"] or 0),
            "total_payments": int(agg["total_payments"] or 0),
            "total_refunds": int(agg["total_refunds"] or 0),
            "total_balance_due": int(due_agg["total"] or 0),
            "open_invoices_count": due_agg["open_invoices"] or 0,
            "entry_count": agg["count"] or 0,
            "approved_count": agg["approved_count"] or 0,
            "pending_count": agg["pending_count"] or 0,
        }
    )


@api_view("GET", permission=VIEW_REPORTS)
def sales_report(request):
    qs = Sale.objects.select_related("customer").all()
    payment_status = request.GET.get("payment_status")
    if payment_status:
        qs = qs.filter(payment_status=payment_status)

    agg = qs.aggregate(
        count=Count("id"),
        total_amount=Sum("amount"),
        total_discount=Sum("discount"),
        total_final=Sum("final_amount"),
    )
    return success(
        {
            "count": agg["count"] or 0,
            "total_amount": int(agg["total_amount"] or 0),
            "total_discount": int(agg["total_discount"] or 0),
            "total_final": int(agg["total_final"] or 0),
            "results": [sale_to_dict(s) for s in qs[:100]],
        }
    )


@api_view("GET", permission=VIEW_REPORTS)
def customer_accounting(request, customer_id):
    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist:
        return fail("Customer not found", status=404)

    sales = Sale.objects.filter(customer=customer)
    sale_ids = sales.values_list("id", flat=True)
    entries = AccountingEntry.objects.filter(sale_id__in=sale_ids)

    sales_agg = sales.aggregate(
        total=Sum("final_amount"),
        count=Count("id"),
        paid=Sum("paid_amount"),
        balance=Sum(F("final_amount") - F("paid_amount"), filter=Q(final_amount__gt=F("paid_amount"))),
    )
    entries_agg = entries.aggregate(total=Sum("amount"), count=Count("id"))

    return success(
        {
            "customer_id": customer.id,
            "customer_name": customer.full_name,
            "sales_count": sales_agg["count"] or 0,
            "sales_total": int(sales_agg["total"] or 0),
            "paid_total": int(sales_agg["paid"] or 0),
            "balance_due": int(sales_agg["balance"] or 0),
            "accounting_entries_count": entries_agg["count"] or 0,
            "accounting_total": int(entries_agg["total"] or 0),
            "sales": [sale_to_dict(s) for s in sales],
            "entries": [accounting_to_dict(e, user=request.user) for e in entries],
        }
    )


def _report_params(request):
    account_id = (request.GET.get("account_id") or "").strip()
    subsidiary_id = (request.GET.get("subsidiary_id") or "").strip()
    return {
        "date_from": (request.GET.get("date_from") or "").strip() or None,
        "date_to": (request.GET.get("date_to") or "").strip() or None,
        "account_class": (request.GET.get("account_class") or "").strip() or None,
        "approved_only": (request.GET.get("approved_only") or "").strip().lower() in ("true", "1"),
        "account_id": int(account_id) if account_id.isdigit() else None,
        "subsidiary_id": int(subsidiary_id) if subsidiary_id.isdigit() else None,
    }


@api_view("GET", permission=VIEW_ACCOUNTING)
def trial_balance(request):
    level = (request.GET.get("level") or "general").strip().lower()
    params = _report_params(request)
    common = {
        "date_from": params["date_from"],
        "date_to": params["date_to"],
        "account_class": params["account_class"],
        "approved_only": params["approved_only"],
    }
    if level == "subsidiary":
        rows, totals = trial_balance_subsidiary(**common, account_id=params["account_id"])
    elif level == "detailed":
        rows, totals = trial_balance_detailed(
            **common,
            account_id=params["account_id"],
            subsidiary_id=params["subsidiary_id"],
        )
    else:
        rows, totals = trial_balance_general(**common)
    return success({"level": level, "results": rows, "totals": totals, "total": len(rows)})


@api_view("GET", permission=VIEW_ACCOUNTING)
def detail_ledger_view(request):
    params = _report_params(request)
    detailed_id = (request.GET.get("detailed_id") or "").strip()
    subsidiary_id = (request.GET.get("subsidiary_id") or "").strip()
    account_id = (request.GET.get("account_id") or "").strip()
    doc_from = (request.GET.get("doc_from") or "").strip()
    doc_to = (request.GET.get("doc_to") or "").strip()

    kwargs = {
        "date_from": params["date_from"],
        "date_to": params["date_to"],
        "approved_only": params["approved_only"],
    }
    if doc_from.isdigit():
        kwargs["doc_from"] = int(doc_from)
    if doc_to.isdigit():
        kwargs["doc_to"] = int(doc_to)
    if detailed_id.isdigit():
        kwargs["detailed_id"] = int(detailed_id)
    elif subsidiary_id.isdigit():
        kwargs["subsidiary_id"] = int(subsidiary_id)
    elif account_id.isdigit():
        kwargs["account_id"] = int(account_id)
    else:
        return fail("حساب تفصیلی، معین یا کل را انتخاب کنید.", status=400)

    try:
        data = detail_ledger(**kwargs)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(data)


@api_view("GET", "POST", permission=VIEW_ACCOUNTING)
def subsidiary_accounts(request):
    if request.method == "GET":
        account_id = (request.GET.get("account_id") or "").strip()
        qs = SubsidiaryAccount.objects.filter(is_active=True).select_related("account").order_by(
            "account__sort_order", "code"
        )
        if account_id.isdigit():
            qs = qs.filter(account_id=int(account_id))
        return success({"results": [subsidiary_to_dict(s) for s in qs]})

    if not has_permission(request.user, CREATE_ACCOUNTING):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    account_id = data.get("account_id")
    code = (data.get("code") or "").strip()
    name = (data.get("name") or "").strip()
    if not account_id or not code or not name:
        return fail("حساب کل، کد و عنوان معین الزامی است.", status=400)
    try:
        account = Account.objects.get(pk=account_id, is_active=True)
    except Account.DoesNotExist:
        return fail("حساب کل یافت نشد.", status=404)
    if SubsidiaryAccount.objects.filter(account=account, code=code).exists():
        return fail("این کد معین قبلاً ثبت شده است.", status=400)
    sub = SubsidiaryAccount.objects.create(account=account, code=code, name=name)
    return success(subsidiary_to_dict(sub), status=201)


@api_view("GET", "POST", permission=VIEW_ACCOUNTING)
def detailed_accounts(request):
    if request.method == "GET":
        subsidiary_id = (request.GET.get("subsidiary_id") or "").strip()
        account_id = (request.GET.get("account_id") or "").strip()
        qs = DetailedAccount.objects.filter(is_active=True).select_related(
            "subsidiary", "subsidiary__account"
        ).order_by("subsidiary__account__sort_order", "subsidiary__code", "code")
        if subsidiary_id.isdigit():
            qs = qs.filter(subsidiary_id=int(subsidiary_id))
        elif account_id.isdigit():
            qs = qs.filter(subsidiary__account_id=int(account_id))
        return success({"results": [detailed_to_dict(d) for d in qs]})

    if not has_permission(request.user, CREATE_ACCOUNTING):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    subsidiary_id = data.get("subsidiary_id")
    code = (data.get("code") or "").strip()
    name = (data.get("name") or "").strip()
    if not subsidiary_id or not code or not name:
        return fail("حساب معین، کد و عنوان تفصیلی الزامی است.", status=400)
    try:
        subsidiary = SubsidiaryAccount.objects.select_related("account").get(pk=subsidiary_id, is_active=True)
    except SubsidiaryAccount.DoesNotExist:
        return fail("حساب معین یافت نشد.", status=404)
    if DetailedAccount.objects.filter(subsidiary=subsidiary, code=code).exists():
        return fail("این کد تفصیلی قبلاً ثبت شده است.", status=400)
    detail = DetailedAccount.objects.create(subsidiary=subsidiary, code=code, name=name)
    return success(detailed_to_dict(detail), status=201)


@api_view("POST")
def document_create(request):
    if not has_permission(request.user, CREATE_ACCOUNTING):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    lines = data.get("lines") or []
    if not isinstance(lines, list) or not lines:
        return fail("حداقل یک ردیف سند لازم است.", status=400)

    entry_date_parsed = None
    if data.get("entry_date"):
        try:
            entry_date_parsed = _parse_entry_date(data["entry_date"])
        except ValueError as exc:
            return fail(str(exc), status=400)

    document_number = data.get("document_number")
    if document_number is not None:
        try:
            document_number = int(document_number)
        except (TypeError, ValueError):
            return fail("شماره سند نامعتبر است.", status=400)

    try:
        result = create_accounting_document(
            lines=lines,
            entry_date=entry_date_parsed,
            document_code=(data.get("document_code") or "").strip(),
            document_number=document_number,
            description=(data.get("description") or "").strip(),
            is_approved=bool(data.get("is_approved", False)) or is_office_accounting_user(request.user),
            entry_type=(data.get("entry_type") or "manual").strip() or "manual",
        )
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "create",
        f"ثبت سند {result['document_number']} — {result['total_debit']} ریال",
        entity_type="AccountingEntry",
    )
    return success(
        {
            "document_code": result["document_code"],
            "document_number": result["document_number"],
            "total_debit": result["total_debit"],
            "total_credit": result["total_credit"],
            "entries": [accounting_to_dict(e, user=request.user) for e in result["entries"]],
        },
        status=201,
    )


@api_view("POST", permission=CREATE_ACCOUNTING)
def excel_import(request):
    """آپلود فایل اکسل حسابداری — تراز کل/معین/تفصیلی + ریز نمونه."""
    upload = request.FILES.get("file")
    if not upload:
        return fail("فایل اکسل انتخاب نشده است.", status=400)

    name = (upload.name or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        return fail("فقط فایل‌های Excel (.xlsx) پذیرفته می‌شوند.", status=400)

    dry_run = (request.POST.get("dry_run") or "").strip().lower() in ("1", "true", "yes")
    approve = (request.POST.get("approve") or "").strip().lower() in ("1", "true", "yes")
    force = (request.POST.get("force") or "").strip().lower() in ("1", "true", "yes")

    from logic.accounting_excel_import import import_excel_file

    try:
        report = import_excel_file(
            upload,
            dry_run=dry_run,
            approve=approve,
            force=force,
        )
    except ImportError:
        return fail("کتابخانه openpyxl نصب نیست. دستور: pip install openpyxl", status=500)
    except ValueError as exc:
        return fail(str(exc), status=400)
    except Exception as exc:
        return fail(f"خطا در پردازش فایل: {exc}", status=400)

    if report.get("errors"):
        return JsonResponse(
            {"ok": False, "error": report["errors"][0], "data": report},
            status=400,
        )

    if report.get("committed"):
        log_action(
            request.user,
            "create",
            (
                f"آپلود اکسل حسابداری — "
                f"{report['stats'].get('entries_created', 0)} سند، "
                f"{report['stats'].get('details_created', 0)} تفصیلی جدید"
            ),
            entity_type="AccountingEntry",
        )

    return success(report, status=200 if dry_run else 201)
