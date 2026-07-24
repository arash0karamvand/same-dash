"""API صف کارخانه و باربری — جدول جدا؛ فقط پس از تایید اداری."""

from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_date

from api.helpers import api_view, fail, success
from api.serializers import factory_order_to_dict
from auth.org_roles import is_executive_user
from auth.permissions import (
    APPROVE_SALE_ACCOUNTING,
    MANAGE_FACTORY_ORDERS,
    MANAGE_FREIGHT_ORDERS,
    VIEW_FACTORY_ORDERS,
    VIEW_FREIGHT_ORDERS,
    has_permission,
)
from backend.models import FactoryOrder
from logic.audit import log_action
from logic.sale_workflow import (
    complete_factory_freight,
    complete_factory_production,
    receive_factory_freight,
    receive_factory_order,
)

SECTION_PRODUCTION = "production"
SECTION_BUILT = "built"
SECTION_FREIGHT = "freight"

QUEUE_NEEDS_BUILD = "needs_build"
QUEUE_IN_PRODUCTION = "in_production"

PRODUCTION_STAGES = {
    FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
    FactoryOrder.WORKFLOW_STAGE_IN_PRODUCTION,
}
BUILT_STAGES = {FactoryOrder.WORKFLOW_STAGE_PRODUCTION_DONE}
FREIGHT_STAGES = {
    FactoryOrder.WORKFLOW_STAGE_PRODUCTION_DONE,
    FactoryOrder.WORKFLOW_STAGE_IN_FREIGHT,
}


def _parse_date_param(value):
    text = (value or "").strip()
    if not text:
        return None
    parsed = parse_date(text)
    if parsed is None:
        raise ValueError("تاریخ نامعتبر است.")
    return parsed


def _is_factory_user(user):
    return has_permission(user, VIEW_FACTORY_ORDERS) or has_permission(user, MANAGE_FACTORY_ORDERS)


def _is_freight_user(user):
    return has_permission(user, VIEW_FREIGHT_ORDERS) or has_permission(user, MANAGE_FREIGHT_ORDERS)


def _has_factory_oversight(user):
    """مدیران و اداری — مشاهده همه مراحل کارخانه."""
    return is_executive_user(user) or (
        has_permission(user, APPROVE_SALE_ACCOUNTING)
        and has_permission(user, VIEW_FACTORY_ORDERS)
    )


def _base_queryset():
    return (
        FactoryOrder.objects.select_related("customer", "source_sale")
        .prefetch_related(
            "line_items",
            "line_items__product__product_materials__material",
        )
        .filter(source_sale__is_deleted=False)
    )


def _default_section(user):
    if _is_freight_user(user) and not _is_factory_user(user):
        return SECTION_FREIGHT
    return SECTION_PRODUCTION


def _apply_section_filters(qs, user, params):
    section = (params.get("section") or _default_section(user)).strip().lower()
    queue = (params.get("queue") or "").strip().lower()
    stage = (params.get("workflow_stage") or "").strip()

    if stage:
        qs = qs.filter(workflow_stage=stage)

    if _has_factory_oversight(user):
        if section == SECTION_BUILT:
            qs = qs.filter(workflow_stage__in=BUILT_STAGES)
            built_date = _parse_date_param(params.get("built_date"))
            if built_date:
                qs = qs.filter(production_done_at__date=built_date)
        elif section == SECTION_FREIGHT:
            qs = qs.filter(workflow_stage__in=FREIGHT_STAGES)
            delivery_date = _parse_date_param(params.get("delivery_date"))
            if delivery_date:
                qs = qs.filter(delivery_date=delivery_date)
        else:
            qs = qs.filter(workflow_stage__in=PRODUCTION_STAGES)
            if queue == QUEUE_NEEDS_BUILD:
                qs = qs.filter(workflow_stage=FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED)
            elif queue == QUEUE_IN_PRODUCTION:
                qs = qs.filter(workflow_stage=FactoryOrder.WORKFLOW_STAGE_IN_PRODUCTION)
        return qs.order_by("-created_at")

    if _is_factory_user(user) and not _is_freight_user(user):
        if section == SECTION_BUILT:
            qs = qs.filter(workflow_stage__in=BUILT_STAGES)
            built_date = _parse_date_param(params.get("built_date"))
            if built_date:
                qs = qs.filter(production_done_at__date=built_date)
        elif section == SECTION_FREIGHT:
            return qs.none()
        else:
            qs = qs.filter(workflow_stage__in=PRODUCTION_STAGES)
            if queue == QUEUE_NEEDS_BUILD:
                qs = qs.filter(workflow_stage=FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED)
            elif queue == QUEUE_IN_PRODUCTION:
                qs = qs.filter(workflow_stage=FactoryOrder.WORKFLOW_STAGE_IN_PRODUCTION)
        return qs.order_by("-created_at")

    if _is_freight_user(user) and not _is_factory_user(user):
        if section not in {SECTION_FREIGHT, ""}:
            return qs.none()
        qs = qs.filter(workflow_stage__in=FREIGHT_STAGES)
        delivery_date = _parse_date_param(params.get("delivery_date")) or timezone.localdate()
        qs = qs.filter(delivery_date=delivery_date)
        return qs.order_by("delivery_date", "-created_at")

    if _is_factory_user(user) and _is_freight_user(user):
        if section == SECTION_BUILT:
            qs = qs.filter(workflow_stage__in=BUILT_STAGES)
            built_date = _parse_date_param(params.get("built_date"))
            if built_date:
                qs = qs.filter(production_done_at__date=built_date)
        elif section == SECTION_FREIGHT:
            qs = qs.filter(workflow_stage__in=FREIGHT_STAGES)
            delivery_date = _parse_date_param(params.get("delivery_date")) or timezone.localdate()
            qs = qs.filter(delivery_date=delivery_date)
        else:
            qs = qs.filter(workflow_stage__in=PRODUCTION_STAGES)
            if queue == QUEUE_NEEDS_BUILD:
                qs = qs.filter(workflow_stage=FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED)
            elif queue == QUEUE_IN_PRODUCTION:
                qs = qs.filter(workflow_stage=FactoryOrder.WORKFLOW_STAGE_IN_PRODUCTION)
        return qs.order_by("-created_at")

    return qs.none()


def _factory_queryset(user, params=None):
    params = params or {}
    try:
        return _apply_section_filters(_base_queryset(), user, params)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def _get_factory_order(pk):
    try:
        return (
            FactoryOrder.objects.select_related("customer", "source_sale")
            .prefetch_related("line_items")
            .get(pk=pk)
        )
    except FactoryOrder.DoesNotExist:
        return None


def _can_view_factory_order(user, order):
    if is_executive_user(user) or (
        has_permission(user, APPROVE_SALE_ACCOUNTING) and has_permission(user, VIEW_FACTORY_ORDERS)
    ):
        return True
    if _is_factory_user(user):
        return order.workflow_stage in PRODUCTION_STAGES | BUILT_STAGES
    if _is_freight_user(user):
        return order.workflow_stage in FREIGHT_STAGES
    return False


def _can_run_factory_action(user, order, permission):
    if not has_permission(user, permission):
        return False
    return _can_view_factory_order(user, order)


@api_view("GET")
def factory_order_list(request):
    can_list = (
        is_executive_user(request.user)
        or _is_factory_user(request.user)
        or _is_freight_user(request.user)
        or _has_factory_oversight(request.user)
    )
    if not can_list:
        return fail("Permission denied", status=403)
    try:
        qs = _factory_queryset(request.user, request.GET)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(
        {
            "results": [
                factory_order_to_dict(o, include_lines=True, user=request.user) for o in qs
            ],
            "summary": {"count": qs.aggregate(c=Count("id"))["c"] or 0},
        }
    )


@api_view("GET")
def factory_order_detail(request, pk):
    order = _get_factory_order(pk)
    if order is None:
        return fail("سفارش کارخانه یافت نشد", status=404)
    if not _can_view_factory_order(request.user, order):
        return fail("Permission denied", status=403)
    return success(factory_order_to_dict(order, include_lines=True, user=request.user))


def _factory_action(request, pk, permission, action, log_label):
    if not has_permission(request.user, permission):
        return fail("Permission denied", status=403)
    order = _get_factory_order(pk)
    if order is None:
        return fail("سفارش کارخانه یافت نشد", status=404)
    if not _can_run_factory_action(request.user, order, permission):
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
