"""دسترسی و فیلتر صف کارخانه / باربری."""

from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_date

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


def parse_date_param(value):
    text = (value or "").strip()
    if not text:
        return None
    parsed = parse_date(text)
    if parsed is None:
        raise ValueError("تاریخ نامعتبر است.")
    return parsed


def is_factory_user(user):
    return has_permission(user, VIEW_FACTORY_ORDERS) or has_permission(user, MANAGE_FACTORY_ORDERS)


def is_freight_user(user):
    return has_permission(user, VIEW_FREIGHT_ORDERS) or has_permission(user, MANAGE_FREIGHT_ORDERS)


def has_factory_oversight(user):
    return is_executive_user(user) or (
        has_permission(user, APPROVE_SALE_ACCOUNTING)
        and has_permission(user, VIEW_FACTORY_ORDERS)
    )


def base_factory_queryset():
    return (
        FactoryOrder.objects.select_related("customer", "source_sale")
        .prefetch_related(
            "line_items",
            "line_items__product__product_materials__material",
        )
        .filter(source_sale__is_deleted=False)
    )


def default_section(user):
    if is_freight_user(user) and not is_factory_user(user):
        return SECTION_FREIGHT
    return SECTION_PRODUCTION


def apply_section_filters(qs, user, params):
    section = (params.get("section") or default_section(user)).strip().lower()
    queue = (params.get("queue") or "").strip().lower()
    stage = (params.get("workflow_stage") or "").strip()

    if stage:
        qs = qs.filter(workflow_stage=stage)

    if has_factory_oversight(user):
        if section == SECTION_BUILT:
            qs = qs.filter(workflow_stage__in=BUILT_STAGES)
            built_date = parse_date_param(params.get("built_date"))
            if built_date:
                qs = qs.filter(production_done_at__date=built_date)
        elif section == SECTION_FREIGHT:
            qs = qs.filter(workflow_stage__in=FREIGHT_STAGES)
            delivery_date = parse_date_param(params.get("delivery_date"))
            if delivery_date:
                qs = qs.filter(delivery_date=delivery_date)
        else:
            qs = qs.filter(workflow_stage__in=PRODUCTION_STAGES)
            if queue == QUEUE_NEEDS_BUILD:
                qs = qs.filter(workflow_stage=FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED)
            elif queue == QUEUE_IN_PRODUCTION:
                qs = qs.filter(workflow_stage=FactoryOrder.WORKFLOW_STAGE_IN_PRODUCTION)
        return qs.order_by("-created_at")

    if is_factory_user(user) and not is_freight_user(user):
        if section == SECTION_BUILT:
            qs = qs.filter(workflow_stage__in=BUILT_STAGES)
            built_date = parse_date_param(params.get("built_date"))
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

    if is_freight_user(user) and not is_factory_user(user):
        if section not in {SECTION_FREIGHT, ""}:
            return qs.none()
        qs = qs.filter(workflow_stage__in=FREIGHT_STAGES)
        delivery_date = parse_date_param(params.get("delivery_date")) or timezone.localdate()
        qs = qs.filter(delivery_date=delivery_date)
        return qs.order_by("delivery_date", "-created_at")

    if is_factory_user(user) and is_freight_user(user):
        if section == SECTION_BUILT:
            qs = qs.filter(workflow_stage__in=BUILT_STAGES)
            built_date = parse_date_param(params.get("built_date"))
            if built_date:
                qs = qs.filter(production_done_at__date=built_date)
        elif section == SECTION_FREIGHT:
            qs = qs.filter(workflow_stage__in=FREIGHT_STAGES)
            delivery_date = parse_date_param(params.get("delivery_date")) or timezone.localdate()
            qs = qs.filter(delivery_date=delivery_date)
        else:
            qs = qs.filter(workflow_stage__in=PRODUCTION_STAGES)
            if queue == QUEUE_NEEDS_BUILD:
                qs = qs.filter(workflow_stage=FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED)
            elif queue == QUEUE_IN_PRODUCTION:
                qs = qs.filter(workflow_stage=FactoryOrder.WORKFLOW_STAGE_IN_PRODUCTION)
        return qs.order_by("-created_at")

    return qs.none()


def factory_queryset_for_user(user, params=None):
    params = params or {}
    return apply_section_filters(base_factory_queryset(), user, params)


def get_factory_order(pk):
    try:
        return (
            FactoryOrder.objects.select_related("customer", "source_sale")
            .prefetch_related("line_items")
            .get(pk=pk)
        )
    except FactoryOrder.DoesNotExist:
        return None


def can_view_factory_order(user, order):
    if is_executive_user(user) or (
        has_permission(user, APPROVE_SALE_ACCOUNTING) and has_permission(user, VIEW_FACTORY_ORDERS)
    ):
        return True
    if is_factory_user(user):
        return order.workflow_stage in PRODUCTION_STAGES | BUILT_STAGES
    if is_freight_user(user):
        return order.workflow_stage in FREIGHT_STAGES
    return False


def can_run_factory_action(user, order, permission):
    if not has_permission(user, permission):
        return False
    return can_view_factory_order(user, order)


def can_list_factory_orders(user):
    return (
        is_executive_user(user)
        or is_factory_user(user)
        or is_freight_user(user)
        or has_factory_oversight(user)
    )


def factory_list_summary(qs):
    return {"count": qs.aggregate(c=Count("id"))["c"] or 0}
