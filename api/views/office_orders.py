"""API صف اداری — جدول جدا؛ فقط پس از تایید سرپرست شعبه."""

from api.helpers import api_view, fail, parse_json, success
from api.serializers import factory_order_to_dict, office_order_to_dict
from auth.org_roles import is_executive_user
from auth.permissions import APPROVE_SALE_ACCOUNTING, VIEW_SALES, has_permission
from backend.models import FactoryOrder, OfficeOrder, Sale
from logic.audit import log_action
from logic.office_orders import (
    aggregate_office_orders,
    can_view_office_order,
    get_office_order,
    list_office_orders,
    office_tracking_queryset,
)
from logic.pagination import paginate
from logic.record_filter import apply_office_order_search_filters
from logic.sale_workflow import approve_office_order, reject_office_order, rollback_office_workflow_step


@api_view("POST")
def office_factory_work_create(request):
    if not has_permission(request.user, APPROVE_SALE_ACCOUNTING) and not is_executive_user(request.user):
        return fail("Permission denied", status=403)
    from logic.receive_kinds import create_office_factory_work

    try:
        sale = create_office_factory_work(request.user, parse_json(request) or {})
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "create",
        f"ثبت کار کارخانه از اداری — #{sale.id} — {sale.receive_kind}",
        entity_type="Sale",
        entity_id=sale.id,
    )
    factory = FactoryOrder.objects.filter(pk=sale.pk).first() or sale
    return success(
        factory_order_to_dict(factory, include_lines=True, user=request.user),
        status=201,
    )


@api_view("GET")
def office_order_list(request):
    scope = (request.GET.get("scope") or "queue").strip()
    status = (request.GET.get("status") or "").strip()
    if scope != "tracking" and not status:
        status = OfficeOrder.STATUS_PENDING
    if scope == "tracking":
        if not (
            is_executive_user(request.user)
            or has_permission(request.user, APPROVE_SALE_ACCOUNTING)
            or has_permission(request.user, VIEW_SALES)
        ):
            return fail("Permission denied", status=403)
    elif not has_permission(request.user, APPROVE_SALE_ACCOUNTING) and not is_executive_user(request.user):
        return fail("Permission denied", status=403)
    if scope == "tracking":
        qs = office_tracking_queryset(request.user)
        if status == OfficeOrder.STATUS_PENDING:
            qs = qs.filter(workflow_stage_id=Sale.WORKFLOW_STAGE_BRANCH_APPROVED)
        elif status == OfficeOrder.STATUS_RELEASED:
            qs = qs.exclude(workflow_stage_id=Sale.WORKFLOW_STAGE_BRANCH_APPROVED)
    else:
        qs = list_office_orders(request.user, status=status)

    qs = apply_office_order_search_filters(qs, request.GET)
    page, meta = paginate(qs, request.GET)

    return success(
        {
            "results": [
                office_order_to_dict(o, include_lines=True, user=request.user) for o in page
            ],
            "summary": aggregate_office_orders(qs),
            **meta,
        }
    )


@api_view("GET")
def office_order_detail(request, pk):
    order = get_office_order(pk)
    if order is None:
        return fail("سفارش اداری یافت نشد", status=404)
    if not can_view_office_order(request.user, order):
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
    order = get_office_order(pk)
    if order is None:
        return fail("سفارش اداری یافت نشد", status=404)
    if order.status != OfficeOrder.STATUS_PENDING:
        return fail("فقط سفارش‌های در انتظار تایید اداری قابل ارسال هستند.", status=400)
    if not can_view_office_order(request.user, order):
        return fail("Permission denied", status=403)
    body = parse_json(request) if request.body else {}
    try:
        order = approve_office_order(
            order,
            request.user,
            check_registration_account_id=body.get("check_registration_account_id"),
            check_deposit_account_id=body.get("check_deposit_account_id"),
            save_check_accounts_as_default=bool(body.get("save_as_default")),
            fulfillment_route=body.get("fulfillment_route"),
            warehouse_id=body.get("warehouse_id"),
            source_branch=body.get("source_branch") or body.get("fulfillment_source_branch"),
            merchant_user_id=body.get("merchant_user_id"),
        )
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
    order = get_office_order(pk)
    if order is None:
        return fail("سفارش اداری یافت نشد", status=404)
    if order.status != OfficeOrder.STATUS_PENDING:
        return fail("فقط سفارش‌های در انتظار تایید اداری قابل عدم تایید هستند.", status=400)
    if not can_view_office_order(request.user, order):
        return fail("Permission denied", status=403)

    reason = (parse_json(request).get("reason") or "").strip()
    try:
        sale = reject_office_order(order, request.user, reason=reason)
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "update",
        f"عدم تایید اداری — سفارش #{order.id}" + (f" — {reason}" if reason else ""),
        entity_type="Sale",
        entity_id=sale.id,
    )
    return success(
        {
            "source_sale_id": sale.id,
            "workflow_stage": sale.workflow_stage_id,
            "message": "سفارش به صف فروشگاه بازگردانده شد.",
        }
    )


@api_view("POST")
def office_order_rollback(request, pk):
    if not has_permission(request.user, APPROVE_SALE_ACCOUNTING):
        return fail("Permission denied", status=403)
    order = get_office_order(pk)
    if order is None:
        return fail("سفارش اداری یافت نشد", status=404)
    if not can_view_office_order(request.user, order):
        return fail("Permission denied", status=403)

    reason = (parse_json(request).get("reason") or "").strip()
    order_id = order.id
    try:
        result = rollback_office_workflow_step(order, request.user, reason=reason)
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "update",
        f"برگشت گردش کار اداری — سفارش #{order_id}" + (f" — {reason}" if reason else ""),
        entity_type="OfficeOrder",
        entity_id=order_id,
    )

    if isinstance(result, Sale):
        return success(
            {
                "source_sale_id": result.id,
                "workflow_stage": result.workflow_stage_id,
                "message": "سفارش به صف فروشگاه بازگردانده شد.",
                "removed": True,
            }
        )

    refreshed = get_office_order(result.id if hasattr(result, "id") else pk)
    if refreshed is None:
        return success({"message": "سفارش به مرحله قبل برگردانده شد.", "removed": True})

    return success(
        office_order_to_dict(
            refreshed, include_installments=True, include_lines=True, user=request.user
        )
    )
