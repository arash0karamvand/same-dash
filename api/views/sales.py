"""endpointهای فروش — CRUD، فیلتر، گزارش روزانه/ماهانه."""

from decimal import Decimal, InvalidOperation

from django.db.models import Count, Sum
from django.utils import timezone

from api.filters import apply_sales_filters, parse_date
from api.helpers import api_view, fail, parse_json, success
from api.serializers import sale_to_dict
from auth import roles
from auth.org_roles import is_branch_supervisor, is_executive_user, sales_expert_summary_only
from auth.permissions import (
    APPROVE_SALE_ACCOUNTING,
    APPROVE_SALE_BRANCH,
    CREATE_SALE,
    DELETE_SALE,
    EDIT_SALE,
    MANAGE_FACTORY_ORDERS,
    MANAGE_FREIGHT_ORDERS,
    VIEW_EMPLOYEE_RANKING,
    VIEW_OWN_SALES,
    VIEW_SALES,
    VIEW_SALES_SUMMARY,
    can_edit_sale,
    can_view_sale,
    has_permission,
)
from backend.models import Customer, Product, Sale, SaleLineItem
from logic.audit import log_action
from logic.employee_ranking import build_employee_ranking
from logic.sales import (
    cancel_order,
    confirm_pre_invoice,
    delete_sale,
    normalize_payment_method,
    normalize_payment_status,
    record_payment,
    record_sale,
    update_sale,
)
from logic.jalali import date_to_jalali
from logic.sales_day import (
    filter_sales_for_gregorian_date,
    filter_sales_for_jalali_month,
    filter_sales_for_jalali_year,
    today_jalali,
)
from logic.sale_workflow import (
    STAGE_PENDING_BRANCH,
    approve_sale_branch,
)
from logic.sellers import (
    effective_sale_branch,
    get_seller_for_user,
    get_user_branch,
    resolve_sale_branch_for_create,
)


def _can_list_sales(user):
    if sales_expert_summary_only(user):
        return False
    if is_executive_user(user):
        return True
    return has_permission(user, APPROVE_SALE_BRANCH) or is_branch_supervisor(user)


def _sales_queryset(user, params=None):
    """صف فروشگاه — فقط سفارش‌های معلق تا ارسال به اداری."""
    params = params or {}
    qs = Sale.objects.select_related("customer", "recorded_by", "seller").prefetch_related(
        "installments", "line_items"
    )
    pending_q = qs.filter(
        workflow_stage=STAGE_PENDING_BRANCH,
        transferred_to_office_at__isnull=True,
    )
    if is_executive_user(user):
        queue = (params.get("queue") or "").strip()
        if queue == "branch":
            return pending_q
        return qs
    if has_permission(user, APPROVE_SALE_BRANCH) or is_branch_supervisor(user):
        branch = get_user_branch(user) or effective_sale_branch(user)
        if branch:
            return pending_q.filter(branch=branch)
        return qs.none()
    return qs.none()


def _sales_report_queryset(user, branch_param=None):
    """گزارش فروش شعبه — همه ثبت‌ها در بازه، حتی پس از ارسال به اداری."""
    qs = Sale.objects.select_related("customer", "recorded_by", "seller").prefetch_related(
        "installments", "line_items"
    ).exclude(order_status=Sale.ORDER_STATUS_CANCELLED)

    branch_param = (branch_param or "").strip() or None

    if sales_expert_summary_only(user):
        return qs.filter(recorded_by=user)

    if is_executive_user(user):
        if branch_param:
            return qs.filter(branch=branch_param)
        return qs

    if has_permission(user, APPROVE_SALE_BRANCH) or is_branch_supervisor(user):
        branch = branch_param or get_user_branch(user) or effective_sale_branch(user)
        if branch:
            return qs.filter(branch=branch)
        return qs.none()

    if has_permission(user, VIEW_OWN_SALES) and not has_permission(user, VIEW_SALES):
        branch = get_user_branch(user) or effective_sale_branch(user)
        if branch:
            return qs.filter(branch=branch)
        return qs.filter(recorded_by=user)

    if has_permission(user, VIEW_SALES):
        if branch_param:
            return qs.filter(branch=branch_param)
        return qs

    return qs.none()


def _can_view_sales_reports(user):
    return (
        is_executive_user(user)
        or is_branch_supervisor(user)
        or has_permission(user, VIEW_SALES)
        or has_permission(user, VIEW_OWN_SALES)
        or has_permission(user, VIEW_SALES_SUMMARY)
        or has_permission(user, APPROVE_SALE_BRANCH)
    )


def _serialize_sales(user, sales):
    return [sale_to_dict(s, user=user, include_lines=True) for s in sales]


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


def _aggregate_sales(qs):
    qs = qs.exclude(order_status=Sale.ORDER_STATUS_CANCELLED)
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
        if not _can_list_sales(request.user):
            if has_permission(request.user, VIEW_SALES_SUMMARY):
                return fail("فقط گزارش ماهانه فروش در دسترس است.", status=403)
            return fail("Permission denied", status=403)
        qs = apply_sales_filters(_sales_queryset(request.user, request.GET), request.GET)
        workflow = (request.GET.get("workflow_stage") or "").strip()
        if workflow:
            qs = qs.filter(workflow_stage=workflow)
        return success({"results": _serialize_sales(request.user, qs), "summary": _aggregate_sales(qs)})

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
        birthday = parse_date(new_customer.get("birthday")) if new_customer.get("birthday") else None
        customer, created = Customer.objects.get_or_create(
            phone=phone,
            defaults={
                "full_name": name,
                "email": (new_customer.get("email") or "").strip(),
                "address": (new_customer.get("address") or "").strip(),
                "birthday": birthday,
            },
        )
        if created:
            from logic.membership import ensure_membership_code
            from logic.sms_club import maybe_send_welcome

            ensure_membership_code(customer)
            maybe_send_welcome(customer, user=request.user)
        else:
            updates = []
            if customer.full_name != name:
                customer.full_name = name
                updates.append("full_name")
            addr = (new_customer.get("address") or "").strip()
            if addr and customer.address != addr:
                customer.address = addr
                updates.append("address")
            if birthday and customer.birthday != birthday:
                customer.birthday = birthday
                updates.append("birthday")
            if updates:
                customer.save(update_fields=updates)
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
    order_kind = (data.get("order_kind") or Sale.ORDER_KIND_NORMAL).strip()
    delivery_date = parse_date(data.get("delivery_date"))
    seller = get_seller_for_user(request.user)
    try:
        branch = resolve_sale_branch_for_create(request.user, data.get("branch"))
    except ValueError as exc:
        return fail(str(exc), status=400)
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
            order_kind=order_kind,
            delivery_date=delivery_date,
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
        return success(sale_to_dict(sale, include_installments=True, include_lines=True, user=request.user))

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

    if not can_edit_sale(request.user, sale):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    try:
        kwargs = {}
        for field in ("description", "invoice_number", "payment_method", "payment_status", "order_kind"):
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
        if "delivery_date" in data:
            kwargs["delivery_date"] = data.get("delivery_date") or None
        if "line_items" in data:
            kwargs["line_items"] = data.get("line_items") or []
        if "installments" in data:
            kwargs["installments"] = data.get("installments") or []
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
    return success(sale_to_dict(sale, include_installments=True, include_lines=True, user=request.user))


@api_view("POST")
def sale_record_payment(request, pk):
    sale = _get_sale(pk)
    if sale is None:
        return fail("Sale not found", status=404)
    if not can_edit_sale(request.user, sale):
        return fail("Permission denied", status=403)

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


@api_view("POST")
def sale_confirm(request, pk):
    sale = _get_sale(pk)
    if sale is None:
        return fail("Sale not found", status=404)
    if not can_edit_sale(request.user, sale):
        return fail("Permission denied", status=403)

    try:
        sale = confirm_pre_invoice(sale, recorded_by=request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "update",
        f"تایید پیش‌فاکتور #{sale.id} — {sale.customer.full_name}",
        entity_type="Sale",
        entity_id=sale.id,
    )
    return success(sale_to_dict(sale, include_installments=True, include_lines=True))


@api_view("POST")
def sale_cancel(request, pk):
    sale = _get_sale(pk)
    if sale is None:
        return fail("Sale not found", status=404)
    if not can_edit_sale(request.user, sale):
        return fail("Permission denied", status=403)

    try:
        sale = cancel_order(sale, recorded_by=request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "update",
        f"لغو سفارش #{sale.id} — {sale.customer.full_name}",
        entity_type="Sale",
        entity_id=sale.id,
    )
    return success(sale_to_dict(sale, include_installments=True, include_lines=True))


@api_view("GET")
def sales_daily_report(request):
    if not _can_view_sales_reports(request.user):
        return fail("Permission denied", status=403)
    if is_branch_supervisor(request.user) and not is_executive_user(request.user):
        return fail("سرپرست شعبه گزارش روزانه ندارد.", status=403)
    day = parse_date(request.GET.get("date")) or timezone.localdate()
    jy, jm, jd = date_to_jalali(day)
    branch = (request.GET.get("branch") or "").strip() or None
    qs = filter_sales_for_gregorian_date(_sales_report_queryset(request.user, branch), day)
    return success(
        {
            "date": day.isoformat(),
            "jalali_year": jy,
            "jalali_month": jm,
            "jalali_day": jd,
            **_aggregate_sales(qs),
            "results": _serialize_sales(request.user, qs),
        }
    )


@api_view("GET")
def sales_monthly_report(request):
    if not _can_view_sales_reports(request.user):
        return fail("Permission denied", status=403)
    jy, jm, _ = today_jalali()
    year = int(request.GET.get("year") or jy)
    month = int(request.GET.get("month") or jm)
    branch = (request.GET.get("branch") or "").strip() or None
    if sales_expert_summary_only(request.user):
        qs = Sale.objects.filter(recorded_by=request.user).exclude(
            order_status=Sale.ORDER_STATUS_CANCELLED
        )
    else:
        qs = _sales_report_queryset(request.user, branch)
    qs = filter_sales_for_jalali_month(qs, year, month)
    qs = apply_sales_filters(qs, {k: v for k, v in request.GET.items() if k not in ("year", "month")})
    return success(
        {
            "jalali_year": year,
            "jalali_month": month,
            "year": year,
            "month": month,
            **_aggregate_sales(qs),
            "results": [] if sales_expert_summary_only(request.user) else _serialize_sales(request.user, qs),
        }
    )


def _workflow_action(request, pk, permission, action, log_label):
    if not has_permission(request.user, permission):
        return fail("Permission denied", status=403)
    sale = _get_sale(pk)
    if sale is None:
        return fail("Sale not found", status=404)
    if not can_view_sale(request.user, sale):
        return fail("Permission denied", status=403)
    try:
        sale = action(sale, request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "update",
        f"{log_label} #{sale.id}",
        entity_type="Sale",
        entity_id=sale.id,
    )
    return success(sale_to_dict(sale, include_installments=True, include_lines=True, user=request.user))


@api_view("POST")
def sale_approve_branch(request, pk):
    if not (has_permission(request.user, APPROVE_SALE_BRANCH) or is_executive_user(request.user)):
        return fail("Permission denied", status=403)
    sale = _get_sale(pk)
    if sale is None:
        return fail("Sale not found", status=404)
    if not can_view_sale(request.user, sale):
        return fail("Permission denied", status=403)
    try:
        sale = approve_sale_branch(sale, request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "update",
        f"تایید سرپرست شعبه — سفارش #{sale.id}",
        entity_type="Sale",
        entity_id=sale.id,
    )
    return success(sale_to_dict(sale, include_installments=True, include_lines=True, user=request.user))


@api_view("POST")
def sale_approve_accounting(request, pk):
    from api.serializers import office_order_to_dict
    from backend.models import OfficeOrder
    from logic.sale_workflow import approve_office_order

    if not has_permission(request.user, APPROVE_SALE_ACCOUNTING):
        return fail("Permission denied", status=403)
    try:
        order = OfficeOrder.objects.select_related("customer", "source_sale").get(
            source_sale_id=pk, status=OfficeOrder.STATUS_PENDING
        )
    except OfficeOrder.DoesNotExist:
        return fail("سفارش اداری یافت نشد — ابتدا سرپرست شعبه باید تایید کند.", status=404)
    try:
        order = approve_office_order(order, request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(
        office_order_to_dict(order, include_installments=True, include_lines=True, user=request.user)
    )


def _factory_action_by_sale(request, pk, permission, action, log_label):
    from api.serializers import factory_order_to_dict
    from backend.models import FactoryOrder

    if not has_permission(request.user, permission):
        return fail("Permission denied", status=403)
    try:
        order = FactoryOrder.objects.select_related("source_sale").get(source_sale_id=pk)
    except FactoryOrder.DoesNotExist:
        return fail("سفارش کارخانه یافت نشد — ابتدا اداری باید تایید کند.", status=404)
    try:
        order = action(order, request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "update",
        f"{log_label} #{order.id}",
        entity_type="FactoryOrder",
        entity_id=order.id,
    )
    return success(factory_order_to_dict(order, include_lines=True, user=request.user))


@api_view("POST")
def sale_factory_receive(request, pk):
    from logic.sale_workflow import receive_factory_order

    return _factory_action_by_sale(
        request, pk, MANAGE_FACTORY_ORDERS, receive_factory_order, "دریافت کارخانه — سفارش"
    )


@api_view("POST")
def sale_factory_complete(request, pk):
    from logic.sale_workflow import complete_factory_production

    return _factory_action_by_sale(
        request,
        pk,
        MANAGE_FACTORY_ORDERS,
        complete_factory_production,
        "پایان ساخت — سفارش",
    )


@api_view("POST")
def sale_freight_receive(request, pk):
    from logic.sale_workflow import receive_factory_freight

    return _factory_action_by_sale(
        request, pk, MANAGE_FREIGHT_ORDERS, receive_factory_freight, "دریافت باربری — سفارش"
    )


@api_view("POST")
def sale_freight_complete(request, pk):
    from logic.sale_workflow import complete_factory_freight

    return _factory_action_by_sale(
        request,
        pk,
        MANAGE_FREIGHT_ORDERS,
        complete_factory_freight,
        "تکمیل باربری — سفارش",
    )


@api_view("GET")
def sales_yearly_report(request):
    if not _can_view_sales_reports(request.user):
        return fail("Permission denied", status=403)
    jy, _, _ = today_jalali()
    year = int(request.GET.get("year") or jy)
    branch = (request.GET.get("branch") or "").strip() or None
    if sales_expert_summary_only(request.user):
        qs = Sale.objects.filter(recorded_by=request.user).exclude(
            order_status=Sale.ORDER_STATUS_CANCELLED
        )
    else:
        qs = _sales_report_queryset(request.user, branch)
    qs = filter_sales_for_jalali_year(qs, year)
    return success(
        {
            "jalali_year": year,
            "year": year,
            **_aggregate_sales(qs),
            "results": [] if sales_expert_summary_only(request.user) else _serialize_sales(request.user, qs),
        }
    )


@api_view("GET")
def sales_daily_breakdown(request):
    """خلاصه فروش روزانه — فقط تاریخ و مبلغ، بدون جزئیات سفارش."""
    if not _can_view_sales_reports(request.user):
        return fail("Permission denied", status=403)
    jy, jm, _ = today_jalali()
    year = int(request.GET.get("year") or jy)
    month = int(request.GET.get("month") or jm)
    branch = (request.GET.get("branch") or "").strip() or None

    if sales_expert_summary_only(request.user):
        qs = Sale.objects.filter(recorded_by=request.user).exclude(
            order_status=Sale.ORDER_STATUS_CANCELLED
        )
    else:
        qs = _sales_report_queryset(request.user, branch)

    qs = filter_sales_for_jalali_month(qs, year, month)
    from logic.sales_day import sold_at_jalali

    buckets = {}
    for sold_at, final_amount in qs.values_list("sold_at", "final_amount"):
        dj_y, dj_m, dj_d = sold_at_jalali(sold_at)
        key = (dj_y, dj_m, dj_d)
        if key not in buckets:
            buckets[key] = {"count": 0, "total_final": 0}
        buckets[key]["count"] += 1
        buckets[key]["total_final"] += int(final_amount or 0)

    days = []
    for (dj_y, dj_m, dj_d) in sorted(buckets.keys(), reverse=True):
        agg = buckets[(dj_y, dj_m, dj_d)]
        days.append(
            {
                "jalali_year": dj_y,
                "jalali_month": dj_m,
                "jalali_day": dj_d,
                "count": agg["count"],
                "total_final": agg["total_final"],
            }
        )

    return success(
        {
            "jalali_year": year,
            "jalali_month": month,
            "year": year,
            "month": month,
            **_aggregate_sales(qs),
            "days": days,
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
