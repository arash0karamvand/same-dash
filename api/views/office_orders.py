"""API صف اداری — جدول جدا؛ فقط پس از تایید سرپرست شعبه."""

from django.db.models import Count, Q, Sum

from api.helpers import api_view, fail, parse_json, success
from api.serializers import office_order_to_dict
from auth.org_roles import is_executive_user
from auth.permissions import APPROVE_SALE_ACCOUNTING, can_edit_sale, has_permission
from backend.models import FactoryOrder, OfficeOrder
from logic.audit import log_action
from logic.sale_workflow import approve_office_order, reject_office_order, rollback_office_workflow_step


def _accounting_office_queryset(qs):
    """صف اداری + سفارش‌های ارسال‌شده به کارخانه که هنوز تکمیل نشده‌اند."""
    active_factory_stages = {
        FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
        FactoryOrder.WORKFLOW_STAGE_IN_PRODUCTION,
        FactoryOrder.WORKFLOW_STAGE_PRODUCTION_DONE,
        FactoryOrder.WORKFLOW_STAGE_IN_FREIGHT,
    }
    return qs.filter(
        Q(status=OfficeOrder.STATUS_PENDING)
        | Q(
            status=OfficeOrder.STATUS_RELEASED,
            source_sale__factory_orders__workflow_stage__in=active_factory_stages,
        )
    ).distinct()


def _office_queryset(user):
    qs = OfficeOrder.objects.select_related(
        "customer",
        "recorded_by",
        "seller",
        "source_sale",
        "factory_order",
        "factory_order__accounting_approved_by",
        "factory_order__factory_received_by",
        "factory_order__freight_received_by",
    ).prefetch_related("line_items", "installments").filter(source_sale__is_deleted=False)
    if is_executive_user(user):
        return qs
    if has_permission(user, APPROVE_SALE_ACCOUNTING):
        return _accounting_office_queryset(qs)
    return qs.none()


def _get_office_order(pk):
    try:
        return (
            OfficeOrder.objects.select_related(
                "customer",
                "recorded_by",
                "seller",
                "source_sale",
                "factory_order",
                "factory_order__accounting_approved_by",
                "factory_order__factory_received_by",
                "factory_order__freight_received_by",
            )
            .prefetch_related("line_items", "installments")
            .get(pk=pk)
        )
    except OfficeOrder.DoesNotExist:
        return None


def _can_view_office_order(user, order):
    if is_executive_user(user):
        return True
    if not has_permission(user, APPROVE_SALE_ACCOUNTING):
        return False
    if order.status == OfficeOrder.STATUS_PENDING:
        return True
    factory = FactoryOrder.objects.filter(source_sale=order.source_sale, is_deleted=False).first()
    if not factory:
        return order.status == OfficeOrder.STATUS_RELEASED
    return factory.workflow_stage != FactoryOrder.WORKFLOW_STAGE_COMPLETED


def _aggregate(qs):
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


@api_view("GET")
def office_order_list(request):
    if not has_permission(request.user, APPROVE_SALE_ACCOUNTING) and not is_executive_user(request.user):
        return fail("Permission denied", status=403)
    qs = _office_queryset(request.user)
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    return success(
        {
            "results": [
                office_order_to_dict(o, include_lines=True, user=request.user) for o in qs
            ],
            "summary": _aggregate(qs),
        }
    )


@api_view("GET")
def office_order_detail(request, pk):
    order = _get_office_order(pk)
    if order is None:
        return fail("سفارش اداری یافت نشد", status=404)
    if not _can_view_office_order(request.user, order):
        return fail("Permission denied", status=403)
    return success(
        office_order_to_dict(
            order, include_installments=True, include_lines=True, user=request.user
        )
    )


@api_view("POST")
def office_order_approve(request, pk):
    if not has_permission(request.user, APPROVE_SALE_ACCOUNTING):
        return fail("Permission denied", status=403)
    order = _get_office_order(pk)
    if order is None:
        return fail("سفارش اداری یافت نشد", status=404)
    if order.status != OfficeOrder.STATUS_PENDING:
        return fail("فقط سفارش‌های در انتظار تایید اداری قابل ارسال به کارخانه هستند.", status=400)
    if not _can_view_office_order(request.user, order):
        return fail("Permission denied", status=403)
    try:
        order = approve_office_order(order, request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "update",
        f"تایید اداری — سفارش #{order.id}",
        entity_type="OfficeOrder",
        entity_id=order.id,
    )
    return success(
        office_order_to_dict(
            order, include_installments=True, include_lines=True, user=request.user
        )
    )


@api_view("POST")
def office_order_reject(request, pk):
    if not has_permission(request.user, APPROVE_SALE_ACCOUNTING):
        return fail("Permission denied", status=403)
    order = _get_office_order(pk)
    if order is None:
        return fail("سفارش اداری یافت نشد", status=404)
    if order.status != OfficeOrder.STATUS_PENDING:
        return fail("فقط سفارش‌های در انتظار تایید اداری قابل عدم تایید هستند.", status=400)
    if not _can_view_office_order(request.user, order):
        return fail("Permission denied", status=403)

    body = parse_json(request)
    reason = (body.get("reason") or "").strip()

    try:
        sale = reject_office_order(order, request.user, reason=reason)
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "update",
        f"عدم تایید اداری — سفارش #{order.id}"
        + (f" — {reason}" if reason else ""),
        entity_type="Sale",
        entity_id=sale.id,
    )
    return success(
        {
            "source_sale_id": sale.id,
            "workflow_stage": sale.workflow_stage,
            "message": "سفارش به صف فروشگاه بازگردانده شد.",
        }
    )


@api_view("POST")
def office_order_rollback(request, pk):
    if not has_permission(request.user, APPROVE_SALE_ACCOUNTING):
        return fail("Permission denied", status=403)
    order = _get_office_order(pk)
    if order is None:
        return fail("سفارش اداری یافت نشد", status=404)
    if not _can_view_office_order(request.user, order):
        return fail("Permission denied", status=403)

    body = parse_json(request)
    reason = (body.get("reason") or "").strip()
    order_id = order.id

    try:
        result = rollback_office_workflow_step(order, request.user, reason=reason)
    except ValueError as exc:
        return fail(str(exc), status=400)

    from backend.models import Sale

    log_action(
        request.user,
        "update",
        f"برگشت گردش کار اداری — سفارش #{order_id}"
        + (f" — {reason}" if reason else ""),
        entity_type="OfficeOrder",
        entity_id=order_id,
    )

    if isinstance(result, Sale):
        return success(
            {
                "source_sale_id": result.id,
                "workflow_stage": result.workflow_stage,
                "message": "سفارش به صف فروشگاه بازگردانده شد.",
                "removed": True,
            }
        )

    refreshed = _get_office_order(result.id if hasattr(result, "id") else pk)
    if refreshed is None:
        return success({"message": "سفارش به مرحله قبل برگردانده شد.", "removed": True})

    return success(
        office_order_to_dict(
            refreshed, include_installments=True, include_lines=True, user=request.user
        )
    )
