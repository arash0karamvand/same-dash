"""دسترسی و queryset صف اداری."""

from django.db.models import Count, Sum

from auth.org_roles import is_executive_user
from auth.permissions import APPROVE_SALE_ACCOUNTING, VIEW_SALES, has_permission
from backend.models import FactoryOrder, OfficeOrder, Sale


def accounting_office_queryset(qs):
    """صف اداری + سفارش‌های ارسال‌شده به کارخانه که هنوز تکمیل نشده‌اند."""
    active_factory_stages = {
        FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
        FactoryOrder.WORKFLOW_STAGE_IN_PRODUCTION,
        FactoryOrder.WORKFLOW_STAGE_PRODUCTION_DONE,
        FactoryOrder.WORKFLOW_STAGE_IN_FREIGHT,
    }
    return qs.filter(
        workflow_stage_id__in={Sale.WORKFLOW_STAGE_BRANCH_APPROVED, *active_factory_stages}
    )


def office_base_queryset():
    return OfficeOrder.all_objects.filter(
        is_deleted=False,
        workflow_stage_id__in={
            Sale.WORKFLOW_STAGE_BRANCH_APPROVED,
            Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
            Sale.WORKFLOW_STAGE_IN_PRODUCTION,
            Sale.WORKFLOW_STAGE_PRODUCTION_DONE,
            Sale.WORKFLOW_STAGE_IN_FREIGHT,
            Sale.WORKFLOW_STAGE_COMPLETED,
        },
    ).select_related(
        "customer",
        "recorded_by",
        "seller",
        "accounting_approved_by",
        "factory_received_by",
        "freight_received_by",
    ).prefetch_related("line_items", "installments")


def office_queryset_for_user(user):
    qs = office_base_queryset()
    if is_executive_user(user):
        return qs
    if has_permission(user, APPROVE_SALE_ACCOUNTING):
        return accounting_office_queryset(qs)
    return qs.none()


def get_office_order(pk):
    try:
        return office_base_queryset().get(pk=pk)
    except OfficeOrder.DoesNotExist:
        return None


def can_view_office_order(user, order):
    if is_executive_user(user):
        return True
    if not has_permission(user, APPROVE_SALE_ACCOUNTING):
        return False
    if order.status == OfficeOrder.STATUS_PENDING:
        return True
    return order.workflow_stage_id != FactoryOrder.WORKFLOW_STAGE_COMPLETED


def aggregate_office_orders(qs):
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


def list_office_orders(user, status=""):
    qs = office_queryset_for_user(user)
    if status == OfficeOrder.STATUS_PENDING:
        qs = qs.filter(workflow_stage_id=Sale.WORKFLOW_STAGE_BRANCH_APPROVED)
    elif status == OfficeOrder.STATUS_RELEASED:
        qs = qs.exclude(workflow_stage_id=Sale.WORKFLOW_STAGE_BRANCH_APPROVED)
    return qs


def office_tracking_queryset(user):
    """همه سفارش‌های اداری — برای پیگیری وضعیت و پیشرفت."""
    if is_executive_user(user):
        return office_base_queryset().order_by("-created_at")
    if has_permission(user, APPROVE_SALE_ACCOUNTING) or has_permission(user, VIEW_SALES):
        return office_base_queryset().order_by("-created_at")
    return OfficeOrder.objects.none()
