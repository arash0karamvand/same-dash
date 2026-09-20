"""Compatibility adapters for the single-table order workflow."""

from django.db import transaction

from backend.models import FactoryOrder, OfficeOrder, OrderTransition, Sale, WorkflowStage


@transaction.atomic
def transition_order(order, to_stage, actor=None, note="", **updates):
    """Lock one concrete Sale, change its stage, and append immutable history."""
    sale = Sale.objects.select_for_update().get(pk=order.pk)
    from_stage_id = sale.workflow_stage_id
    if from_stage_id == to_stage:
        raise ValueError("سفارش از قبل در این مرحله است.")
    to_stage_obj = WorkflowStage.objects.filter(code=to_stage, is_active=True).first()
    if not to_stage_obj:
        raise ValueError("مرحله گردش کار نامعتبر است.")
    from_stage = WorkflowStage.objects.filter(code=from_stage_id).first()

    sale.workflow_stage_id = to_stage
    update_fields = ["workflow_stage"]
    for field, value in updates.items():
        setattr(sale, field, value)
        update_fields.append(field if field.endswith("_id") else field)
    sale.save(update_fields=update_fields)
    OrderTransition.objects.create(
        order=sale,
        from_stage=from_stage,
        to_stage=to_stage_obj,
        actor=actor,
        note=(note or "")[:500],
    )
    return sale


def as_office_order(sale):
    return OfficeOrder.objects.get(pk=sale.pk)


def as_factory_order(sale):
    found = FactoryOrder.objects.filter(pk=sale.pk).first()
    return found or sale


@transaction.atomic
def create_office_order_from_sale(sale, user):
    """Legacy name: transition the Sale into the office queue; never copy it."""
    from django.utils import timezone
    from logic.sales import ensure_draft_sale_accounting

    sale = transition_order(
        sale,
        Sale.WORKFLOW_STAGE_BRANCH_APPROVED,
        user,
        branch_approved_at=timezone.now(),
        branch_approved_by_id=user.pk if user else None,
        office_released_at=timezone.now(),
    )
    ensure_draft_sale_accounting(sale)
    return as_office_order(sale)


@transaction.atomic
def create_factory_order_from_office(office, user):
    """Legacy name: transition the same Sale into the factory queue."""
    from django.utils import timezone

    now = timezone.now()
    sale = transition_order(
        office,
        Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
        user,
        accounting_approved_at=now,
        accounting_approved_by_id=user.pk if user else None,
        factory_released_at=now,
        order_status=Sale.ORDER_STATUS_CONFIRMED,
        fulfillment_route=Sale.FULFILLMENT_ROUTE_FACTORY,
    )
    return as_factory_order(sale)


@transaction.atomic
def route_office_order(office, user, fields, note=""):
    """Send an office-approved sale to warehouse, pickup, or merchant."""
    from django.utils import timezone
    from backend.models import Sale

    now = timezone.now()
    warehouse = fields.get("fulfillment_warehouse")
    source = fields.get("fulfillment_source_branch")
    merchant = fields.get("merchant_user")
    sale = transition_order(
        office,
        fields["workflow_stage_id"],
        user,
        note=note,
        accounting_approved_at=now,
        accounting_approved_by_id=user.pk if user else None,
        factory_released_at=now,
        order_status=Sale.ORDER_STATUS_CONFIRMED,
        fulfillment_route=fields["fulfillment_route"],
        fulfillment_warehouse_id=warehouse.pk if warehouse else None,
        fulfillment_source_branch_id=source.code if source else None,
        merchant_user_id=merchant.pk if merchant else None,
    )
    return sale


def soft_delete_workflow_orders_for_sale(sale):
    """No-op: deleting the concrete Sale removes it from every proxy queue."""
    return sale


def migrate_sale_to_office_if_needed(sale):
    return as_office_order(sale) if sale.workflow_stage_id == Sale.WORKFLOW_STAGE_BRANCH_APPROVED else None


def migrate_office_to_factory_if_needed(office):
    factory_stages = {
        Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
        Sale.WORKFLOW_STAGE_MERCHANT_ASSIGNED,
        Sale.WORKFLOW_STAGE_IN_PRODUCTION,
        Sale.WORKFLOW_STAGE_PRODUCTION_DONE,
        Sale.WORKFLOW_STAGE_IN_FREIGHT,
        Sale.WORKFLOW_STAGE_COMPLETED,
    }
    return as_factory_order(office) if office.workflow_stage_id in factory_stages else None
