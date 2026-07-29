"""endpointهای فروش — CRUD، فیلتر، گزارش روزانه/ماهانه."""

from decimal import Decimal, InvalidOperation

from api.filters import apply_sales_filters, parse_date
from api.helpers import api_view, fail, parse_json, success
from api.serializers import sale_to_dict
from auth.org_roles import is_branch_supervisor, is_executive_user
from auth.permissions import (
    APPROVE_SALE_ACCOUNTING,
    APPROVE_SALE_BRANCH,
    CREATE_SALE,
    DELETE_SALE,
    MANAGE_FACTORY_ORDERS,
    MANAGE_FREIGHT_ORDERS,
    VIEW_EMPLOYEE_RANKING,
    VIEW_SALES_SUMMARY,
    can_edit_sale,
    can_view_sale,
    has_permission,
)
from backend.models import Customer, Sale
from logic.audit import log_action
from logic.sales import (
    cancel_order,
    confirm_pre_invoice,
    delete_sale,
    normalize_payment_status,
    record_payment,
    record_sale,
    update_sale,
)
from logic.sale_workflow import approve_sale_branch
from logic.sales_reports import (
    aggregate_sales,
    build_daily_breakdown,
    build_daily_sales_report,
    build_employee_ranking_report,
    build_monthly_sales_payload,
    build_yearly_sales_report,
    can_list_sales,
    can_view_sales_reports,
    get_sale,
    prepare_monthly_sales_queryset,
    sales_queryset,
)
from logic.sellers import get_seller_for_user, resolve_sale_branch_for_create


def _serialize_sales(user, sales):
    return [sale_to_dict(s, user=user, include_lines=True) for s in sales]


def _report_success(user, payload):
    """تبدیل کلید sales به results سریال‌شده."""
    sales = payload.pop("sales", None)
    if sales is not None:
        if sales == []:
            payload["results"] = []
        else:
            payload["results"] = _serialize_sales(user, sales)
    return success(payload)


@api_view("GET", "POST")
def sale_list(request):
    if request.method == "GET":
        if not can_list_sales(request.user):
            if has_permission(request.user, VIEW_SALES_SUMMARY):
                return fail("فقط گزارش ماهانه فروش در دسترس است.", status=403)
            return fail("Permission denied", status=403)
        qs = apply_sales_filters(sales_queryset(request.user, request.GET), request.GET)
        workflow = (request.GET.get("workflow_stage") or "").strip()
        if workflow:
            qs = qs.filter(workflow_stage=workflow)
        return success({"results": _serialize_sales(request.user, qs), "summary": aggregate_sales(qs)})

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
        f"فروش {int(sale.final_amount)} ریال — {customer.full_name} — فروشنده: {seller_name}",
        entity_type="Sale",
        entity_id=sale.id,
        details={"branch": branch, "line_items": line_items},
    )

    return success(sale_to_dict(sale, include_installments=True, include_lines=True), status=201)


@api_view("GET", "PUT", "DELETE")
def sale_detail(request, pk):
    sale = get_sale(pk)
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
    sale = get_sale(pk)
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
        f"دریافت {int(amount)} ریال — فروش #{sale.id}",
        entity_type="Sale",
        entity_id=sale.id,
    )
    return success(sale_to_dict(sale, include_installments=True))


@api_view("POST")
def sale_confirm(request, pk):
    sale = get_sale(pk)
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
    sale = get_sale(pk)
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
    if not can_view_sales_reports(request.user):
        return fail("Permission denied", status=403)
    if is_branch_supervisor(request.user) and not is_executive_user(request.user):
        return fail("سرپرست شعبه گزارش روزانه ندارد.", status=403)
    return _report_success(request.user, build_daily_sales_report(request.user, request.GET))


@api_view("GET")
def sales_monthly_report(request):
    if not can_view_sales_reports(request.user):
        return fail("Permission denied", status=403)
    qs, year, month = prepare_monthly_sales_queryset(request.user, request.GET)
    qs = apply_sales_filters(qs, {k: v for k, v in request.GET.items() if k not in ("year", "month")})
    return _report_success(request.user, build_monthly_sales_payload(request.user, qs, year, month))


def _workflow_action(request, pk, permission, action, log_label):
    if not has_permission(request.user, permission):
        return fail("Permission denied", status=403)
    sale = get_sale(pk)
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
    sale = get_sale(pk)
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
    if not can_view_sales_reports(request.user):
        return fail("Permission denied", status=403)
    return _report_success(request.user, build_yearly_sales_report(request.user, request.GET))


@api_view("GET")
def sales_daily_breakdown(request):
    """خلاصه فروش روزانه — فقط تاریخ و مبلغ، بدون جزئیات سفارش."""
    if not can_view_sales_reports(request.user):
        return fail("Permission denied", status=403)
    return success(build_daily_breakdown(request.user, request.GET))


@api_view("GET")
def employee_ranking(request):
    if not has_permission(request.user, VIEW_EMPLOYEE_RANKING):
        return fail("Permission denied", status=403)
    try:
        return success(build_employee_ranking_report(request.GET))
    except (ValueError, TypeError) as exc:
        return fail(str(exc), status=400)
