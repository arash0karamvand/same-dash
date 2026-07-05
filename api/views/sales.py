"""endpointهای فروش — CRUD، فیلتر، گزارش روزانه/ماهانه."""

from decimal import Decimal, InvalidOperation

from django.db.models import Count, Sum
from django.utils import timezone

from api.filters import apply_sales_filters, parse_date
from api.helpers import api_view, fail, parse_json, success
from api.serializers import sale_to_dict
from auth.permissions import (
    CREATE_SALE,
    DELETE_SALE,
    EDIT_SALE,
    VIEW_EMPLOYEE_RANKING,
    VIEW_OWN_SALES,
    VIEW_SALES,
    can_view_sale,
    has_permission,
)
from backend.models import Customer, Product, Sale, SaleLineItem
from logic.audit import log_action
from logic.employee_ranking import build_employee_ranking
from logic.sales import delete_sale, normalize_payment_status, record_payment, record_sale, update_sale
from logic.jalali import date_to_jalali
from logic.sales_day import (
    filter_sales_for_gregorian_date,
    filter_sales_for_jalali_month,
    filter_sales_for_jalali_year,
    today_jalali,
)
from logic.sellers import effective_sale_branch, get_seller_for_user


def _parse_period_params(params):
    period = (params.get("period") or "month").strip().lower()
    if period not in {"day", "month", "year"}:
        raise ValueError("بازه باید day، month یا year باشد.")
    jy, jm, jd = today_jalali()
    year = int(params.get("year") or jy)
    month = int(params.get("month") or jm)
    day = int(params.get("day") or jd)
    return period, year, month, day


def _get_sale(pk, include_deleted=False):
    manager = Sale.all_objects if include_deleted else Sale.objects
    try:
        return manager.select_related("customer", "recorded_by", "seller").prefetch_related(
        "installments", "line_items"
    ).get(pk=pk)
    except Sale.DoesNotExist:
        return None


def _sales_queryset(user):
    qs = Sale.objects.select_related("customer", "recorded_by", "seller").prefetch_related(
        "installments", "line_items"
    )
    if has_permission(user, VIEW_SALES):
        return qs
    if has_permission(user, VIEW_OWN_SALES):
        branch = effective_sale_branch(user)
        qs = qs.filter(recorded_by=user)
        if branch:
            qs = qs.filter(branch__in=[branch, ""])
        return qs
    return qs.none()


def _aggregate_sales(qs):
    agg = qs.aggregate(
        count=Count("id"),
        total_final=Sum("final_amount"),
        total_paid=Sum("paid_amount"),
    )
    return {
        "count": agg["count"] or 0,
        "total_final": int(agg["total_final"] or 0),
        "total_paid": int(agg["total_paid"] or 0),
    }


@api_view("GET", "POST")
def sale_list(request):
    if request.method == "GET":
        if not (has_permission(request.user, VIEW_SALES) or has_permission(request.user, VIEW_OWN_SALES)):
            return fail("Permission denied", status=403)
        qs = apply_sales_filters(_sales_queryset(request.user), request.GET)
        return success({"results": [sale_to_dict(s) for s in qs], "summary": _aggregate_sales(qs)})

    if not has_permission(request.user, CREATE_SALE):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    customer_id = data.get("customer_id")
    new_customer = data.get("new_customer")
    if not customer_id and new_customer:
        phone = (new_customer.get("phone") or "").strip()
        name = (new_customer.get("full_name") or "").strip()
        if not name or not phone:
            return fail("Customer name and phone required", status=400)
        customer, created = Customer.objects.get_or_create(
            phone=phone,
            defaults={
                "full_name": name,
                "email": (new_customer.get("email") or "").strip(),
            },
        )
        if created:
            from logic.membership import ensure_membership_code
            from logic.sms_club import maybe_send_welcome

            ensure_membership_code(customer)
            maybe_send_welcome(customer, user=request.user)
        if customer.full_name != name:
            customer.full_name = name
            customer.save(update_fields=["full_name"])
    else:
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            return fail("Invalid customer", status=404)

    line_items = data.get("line_items") or []
    try:
        amount = Decimal(str(data.get("amount") or 0))
        discount_type = (data.get("discount_type") or "amount").strip()
        discount_value = data.get("discount_value")
        if discount_value is None:
            discount_value = data.get("discount")
        discount_value = Decimal(str(discount_value or 0))
        paid_amount = data.get("paid_amount")
        if paid_amount is not None:
            paid_amount = Decimal(str(paid_amount))
    except (InvalidOperation, TypeError):
        return fail("Invalid amount or discount", status=400)

    payment_status = normalize_payment_status(data.get("payment_status") or "paid")
    seller = get_seller_for_user(request.user)
    branch = effective_sale_branch(request.user) or (seller.branch if seller else "")
    try:
        sale = record_sale(
            customer,
            amount,
            discount_type=discount_type,
            discount_value=discount_value,
            payment_method=data.get("payment_method") or "cash",
            payment_status=payment_status,
            paid_amount=paid_amount,
            installments=data.get("installments"),
            line_items=line_items,
            invoice_number=(data.get("invoice_number") or "").strip(),
            description=(data.get("description") or "").strip(),
            recorded_by=request.user,
            branch=branch,
            seller=seller,
        )
    except ValueError as exc:
        return fail(str(exc), status=400)

    from logic.sms_club import maybe_send_order_placed

    maybe_send_order_placed(sale, user=request.user)

    seller_name = seller.full_name if seller else request.user.get_full_name()
    log_action(
        request.user,
        "sale",
        f"فروش {int(sale.final_amount)} تومان — {customer.full_name} — فروشنده: {seller_name}",
        entity_type="Sale",
        entity_id=sale.id,
        details={"branch": branch, "line_items": line_items},
    )

    return success(sale_to_dict(sale, include_installments=True, include_lines=True), status=201)


@api_view("GET", "PUT", "DELETE")
def sale_detail(request, pk):
    sale = _get_sale(pk)
    if sale is None:
        return fail("Sale not found", status=404)

    if request.method == "GET":
        if not can_view_sale(request.user, sale):
            return fail("Permission denied", status=403)
        return success(sale_to_dict(sale, include_installments=True, include_lines=True))

    if request.method == "DELETE":
        if not has_permission(request.user, DELETE_SALE):
            return fail("Permission denied", status=403)
        deleted_entries = delete_sale(sale, user=request.user)
        log_action(
            request.user,
            "delete",
            f"حذف فروش #{sale.id} — {sale.customer.full_name}"
            + (f" — {deleted_entries} سند حسابداری" if deleted_entries else ""),
            entity_type="Sale",
            entity_id=sale.id,
        )
        return success({"deleted": True, "accounting_entries_deleted": deleted_entries})

    if not has_permission(request.user, EDIT_SALE):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    try:
        kwargs = {}
        for field in ("description", "invoice_number", "payment_method"):
            if field in data:
                kwargs[field] = data.get(field)
        if "amount" in data:
            kwargs["amount"] = data["amount"]
        if "discount_type" in data:
            kwargs["discount_type"] = data["discount_type"]
        if "discount_value" in data:
            kwargs["discount_value"] = data["discount_value"]
        elif "discount" in data:
            kwargs["discount"] = data["discount"]
        if "paid_amount" in data:
            kwargs["paid_amount"] = data["paid_amount"]
        sale = update_sale(sale, **kwargs)
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "update",
        f"ویرایش فروش #{sale.id} — {sale.customer.full_name}",
        entity_type="Sale",
        entity_id=sale.id,
    )
    return success(sale_to_dict(sale, include_installments=True))


@api_view("POST")
def sale_record_payment(request, pk):
    if not has_permission(request.user, EDIT_SALE):
        return fail("Permission denied", status=403)

    sale = _get_sale(pk)
    if sale is None:
        return fail("Sale not found", status=404)

    data = parse_json(request)
    try:
        amount = Decimal(str(data.get("amount")))
    except (InvalidOperation, TypeError):
        return fail("Invalid payment amount", status=400)

    try:
        sale = record_payment(
            sale,
            amount,
            description=(data.get("description") or "").strip(),
            recorded_by=request.user,
        )
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "payment",
        f"دریافت {int(amount)} تومان — فروش #{sale.id}",
        entity_type="Sale",
        entity_id=sale.id,
    )
    return success(sale_to_dict(sale, include_installments=True))


@api_view("GET")
def sales_daily_report(request):
    if not (has_permission(request.user, VIEW_SALES) or has_permission(request.user, VIEW_OWN_SALES)):
        return fail("Permission denied", status=403)
    day = parse_date(request.GET.get("date")) or timezone.localdate()
    jy, jm, jd = date_to_jalali(day)
    qs = filter_sales_for_gregorian_date(_sales_queryset(request.user), day)
    return success(
        {
            "date": day.isoformat(),
            "jalali_year": jy,
            "jalali_month": jm,
            "jalali_day": jd,
            **_aggregate_sales(qs),
            "results": [sale_to_dict(s) for s in qs],
        }
    )


@api_view("GET")
def sales_monthly_report(request):
    if not (has_permission(request.user, VIEW_SALES) or has_permission(request.user, VIEW_OWN_SALES)):
        return fail("Permission denied", status=403)
    jy, jm, _ = today_jalali()
    year = int(request.GET.get("year") or jy)
    month = int(request.GET.get("month") or jm)
    qs = filter_sales_for_jalali_month(_sales_queryset(request.user), year, month)
    qs = apply_sales_filters(qs, {k: v for k, v in request.GET.items() if k not in ("year", "month")})
    return success(
        {
            "jalali_year": year,
            "jalali_month": month,
            "year": year,
            "month": month,
            **_aggregate_sales(qs),
            "results": [sale_to_dict(s) for s in qs],
        }
    )


@api_view("GET")
def sales_yearly_report(request):
    if not (has_permission(request.user, VIEW_SALES) or has_permission(request.user, VIEW_OWN_SALES)):
        return fail("Permission denied", status=403)
    jy, _, _ = today_jalali()
    year = int(request.GET.get("year") or jy)
    qs = filter_sales_for_jalali_year(_sales_queryset(request.user), year)
    return success(
        {
            "jalali_year": year,
            "year": year,
            **_aggregate_sales(qs),
            "results": [sale_to_dict(s) for s in qs],
        }
    )


@api_view("GET")
def employee_ranking(request):
    if not has_permission(request.user, VIEW_EMPLOYEE_RANKING):
        return fail("Permission denied", status=403)
    try:
        period, year, month, day = _parse_period_params(request.GET)
    except (ValueError, TypeError) as exc:
        return fail(str(exc), status=400)

    branch = (request.GET.get("branch") or "").strip() or None
    qs = Sale.objects.select_related("recorded_by")
    try:
        results = build_employee_ranking(
            qs,
            period,
            year,
            jm=month if period in ("day", "month") else None,
            jd=day if period == "day" else None,
            branch=branch,
        )
    except ValueError as exc:
        return fail(str(exc), status=400)

    total = sum(item["total_final"] for item in results)
    return success(
        {
            "period": period,
            "jalali_year": year,
            "jalali_month": month if period in ("day", "month") else None,
            "jalali_day": day if period == "day" else None,
            "branch": branch,
            "total_final": total,
            "results": results,
        }
    )
