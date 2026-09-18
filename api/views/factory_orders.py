"""API صف کارخانه و باربری — جدول جدا؛ فقط پس از تایید اداری."""

from api.helpers import api_view, fail, parse_json, success
from api.serializers import factory_order_to_dict
from auth.permissions import (
    APPROVE_SALE_ACCOUNTING,
    MANAGE_FACTORY_ORDERS,
    MANAGE_FREIGHT_ORDERS,
    has_permission,
)
from logic.audit import log_action
from logic.early_ship import (
    confirm_factory_delivery_ready,
    send_factory_order_to_freight,
    set_early_ship_allowed_date,
)
from logic.factory_orders import (
    can_list_factory_orders,
    can_run_factory_action,
    can_view_factory_order,
    factory_list_summary,
    factory_queryset_for_user,
    get_factory_order,
)
from logic.sale_workflow import (
    complete_factory_freight,
    complete_factory_production,
    receive_factory_freight,
    receive_factory_order,
)


@api_view("GET")
def factory_order_list(request):
    if not can_list_factory_orders(request.user):
        return fail("Permission denied", status=403)
    try:
        qs = factory_queryset_for_user(request.user, request.GET)
    except ValueError as exc:
        return fail(str(exc), status=400)
    from logic.pagination import paginate

    page, meta = paginate(qs, request.GET)
    return success(
        {
            "results": [
                factory_order_to_dict(o, include_lines=True, user=request.user) for o in page
            ],
            "summary": factory_list_summary(qs),
            **meta,
        }
    )


@api_view("GET")
def factory_order_detail(request, pk):
    order = get_factory_order(pk)
    if order is None:
        return fail("سفارش کارخانه یافت نشد", status=404)
    if not can_view_factory_order(request.user, order):
        return fail("Permission denied", status=403)
    return success(factory_order_to_dict(order, include_lines=True, user=request.user))


def _factory_action(request, pk, permission, action, log_label):
    if not has_permission(request.user, permission):
        return fail("Permission denied", status=403)
    order = get_factory_order(pk)
    if order is None:
        return fail("سفارش کارخانه یافت نشد", status=404)
    if not can_run_factory_action(request.user, order, permission):
        return fail("Permission denied", status=403)
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
def factory_order_receive(request, pk):
    return _factory_action(
        request, pk, MANAGE_FACTORY_ORDERS, receive_factory_order, "دریافت کارخانه — سفارش"
    )


@api_view("POST")
def factory_order_complete(request, pk):
    return _factory_action(
        request,
        pk,
        MANAGE_FACTORY_ORDERS,
        complete_factory_production,
        "پایان ساخت — سفارش",
    )


@api_view("POST")
def factory_order_confirm_ready(request, pk):
    return _factory_action(
        request,
        pk,
        MANAGE_FACTORY_ORDERS,
        confirm_factory_delivery_ready,
        "تایید نهایی ساخته‌شده — سفارش",
    )


@api_view("POST")
def factory_order_send_to_freight(request, pk):
    return _factory_action(
        request,
        pk,
        MANAGE_FACTORY_ORDERS,
        send_factory_order_to_freight,
        "ارسال به باربری — سفارش",
    )


@api_view("POST")
def factory_order_early_ship_date(request, pk):
    if not has_permission(request.user, APPROVE_SALE_ACCOUNTING):
        return fail("Permission denied", status=403)
    order = get_factory_order(pk)
    if order is None:
        return fail("سفارش کارخانه یافت نشد", status=404)
    data = parse_json(request)
    try:
        order = set_early_ship_allowed_date(order, request.user, data.get("allowed_date"))
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "update",
        f"تعیین تاریخ ارسال زودتر از موعد #{order.id}",
        entity_type="FactoryOrder",
        entity_id=order.id,
    )
    return success(factory_order_to_dict(order, include_lines=True, user=request.user))


@api_view("POST")
def factory_order_freight_receive(request, pk):
    return _factory_action(
        request, pk, MANAGE_FREIGHT_ORDERS, receive_factory_freight, "دریافت باربری — سفارش"
    )


@api_view("POST")
def factory_order_freight_complete(request, pk):
    return _factory_action(
        request,
        pk,
        MANAGE_FREIGHT_ORDERS,
        complete_factory_freight,
        "تکمیل باربری — سفارش",
    )
