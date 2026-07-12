"""endpointهای حسابداری — /api/accounting/."""

from decimal import Decimal, InvalidOperation

from django.db.models import Count, F, Q, Sum

from backend.models import AccountingEntry, Customer, Sale

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
from logic.accounting import SYSTEM_ENTRY_TYPES, delete_accounting_entry, entry_permissions, is_office_accounting_user, is_system_entry
from logic.audit import log_action

VALID_ENTRY_TYPES = {value for value, _ in AccountingEntry.ENTRY_TYPE_CHOICES}


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
            | Q(sale__invoice_number__icontains=search)
            | Q(sale__customer__full_name__icontains=search)
            | Q(sale__customer__phone__icontains=search)
        )
    return qs


@api_view("GET", "POST")
def entry_list(request):
    if request.method == "GET":
        if not has_permission(request.user, VIEW_ACCOUNTING):
            return fail("Permission denied", status=403)

        qs = _apply_filters(
            AccountingEntry.objects.select_related("sale", "sale__customer").filter(
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
            }
        )

    if not has_permission(request.user, CREATE_ACCOUNTING):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    entry_type = (data.get("entry_type") or "other").strip()
    if entry_type not in VALID_ENTRY_TYPES:
        return fail("نوع سند نامعتبر است.", status=400)

    try:
        amount = _parse_money(data.get("amount"), "مبلغ")
        debit = _parse_money(data.get("debit"), "بدهکار")
        credit = _parse_money(data.get("credit"), "بستانکار")
    except ValueError as exc:
        return fail(str(exc), status=400)

    effective_amount = amount or debit or credit
    if effective_amount <= 0:
        return fail("مبلغ سند باید بزرگ‌تر از صفر باشد.", status=400)

    description = (data.get("description") or "").strip()
    if not description:
        return fail("شرح سند الزامی است.", status=400)

    sale = None
    if data.get("sale_id"):
        try:
            sale = Sale.objects.get(pk=data["sale_id"])
        except Sale.DoesNotExist:
            return fail("Sale not found", status=404)

    if entry_type == "payment" and sale:
        try:
            from logic.sales import balance_due, record_payment

            amount_to_apply = effective_amount
            due = balance_due(sale)
            if amount_to_apply > due:
                return fail(f"مبلغ پرداخت بیش از مانده فاکتور ({int(due)} تومان) است.", status=400)
            record_payment(
                sale,
                amount_to_apply,
                description=description,
                recorded_by=request.user,
            )
            payment_entry = (
                AccountingEntry.objects.filter(sale=sale, entry_type="payment")
                .order_by("-id")
                .first()
            )
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

    entry_kwargs = {
        "entry_type": entry_type,
        "debit": debit,
        "credit": credit,
        "amount": effective_amount,
        "description": description,
        "sale": sale,
        "is_approved": bool(data.get("is_approved", False)) or is_office_accounting_user(request.user),
    }
    if data.get("entry_date"):
        try:
            entry_kwargs["entry_date"] = _parse_entry_date(data["entry_date"])
        except ValueError as exc:
            return fail(str(exc), status=400)

    entry = AccountingEntry.objects.create(**entry_kwargs)
    log_action(
        request.user,
        "create",
        f"سند حسابداری {entry.get_entry_type_display()} — {int(entry.amount)}",
        entity_type="AccountingEntry",
        entity_id=entry.id,
    )
    return success(accounting_to_dict(entry, user=request.user), status=201)


@api_view("GET", "PUT", "DELETE")
def entry_detail(request, pk):
    try:
        entry = AccountingEntry.objects.select_related("sale", "sale__customer").get(pk=pk)
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

    try:
        if "debit" in data:
            entry.debit = _parse_money(data.get("debit"), "بدهکار")
        if "credit" in data:
            entry.credit = _parse_money(data.get("credit"), "بستانکار")
        if "amount" in data:
            entry.amount = _parse_money(data.get("amount"), "مبلغ")
    except ValueError as exc:
        return fail(str(exc), status=400)

    entry.amount = entry.amount or entry.debit or entry.credit
    if entry.amount <= 0:
        return fail("مبلغ سند باید بزرگ‌تر از صفر باشد.", status=400)

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


@api_view("GET", permission=VIEW_REPORTS)
def summary(request):
    entries = _apply_filters(AccountingEntry.objects.all(), request.GET)
    agg = entries.aggregate(
        total_debit=Sum("debit"),
        total_credit=Sum("credit"),
        total_amount=Sum("amount"),
        count=Count("id"),
        approved_count=Count("id", filter=Q(is_approved=True)),
        pending_count=Count("id", filter=Q(is_approved=False)),
        total_receivables=Sum("debit", filter=Q(entry_type="receivable")),
        total_payments=Sum("credit", filter=Q(entry_type="payment")),
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
