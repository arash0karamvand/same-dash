"""Lock-safe per-line fulfillment orchestration."""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from backend.models import (
    FulfillmentPlan,
    FulfillmentPlanLine,
    InventoryReservation,
    MerchantSupplyDemand,
    ProductMaterial,
    ProductionOrder,
    SaleLineItem,
    StockTransfer,
)
from logic.inventory_costing import availability, consume_stock, release_reservation, reserve_stock
from logic.feature_flags import FULFILLMENT, require_feature
from logic.stock_locations import default_warehouse, location_transaction_kwargs, parse_location


def _qty(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.001"))
    except Exception as exc:
        raise ValueError("Quantity is invalid.") from exc


def _actor(user):
    return user if getattr(user, "is_authenticated", False) else None


def _location_from_plan_line(line):
    return {
        "kind": line.source_location_kind,
        "warehouse": line.source_warehouse,
        "warehouse_id": line.source_warehouse_id,
        "branch": line.source_branch,
        "branch_id": line.source_branch_id,
    }


def _destination_for_sale(sale):
    if sale.branch_id:
        return parse_location({"kind": "branch", "branch": sale.branch_id}, required=True)
    warehouse = default_warehouse()
    return parse_location({"kind": "warehouse", "warehouse_id": warehouse.pk}, required=True)


def _bom_snapshot(sale_line, quantity):
    from logic.materials import resolve_material_requirements

    rows = resolve_material_requirements(
        product=sale_line.product if sale_line.product_id else None,
        workset_config=sale_line.workset_config or None,
        quantity=quantity,
    )
    return [
        {
            "material_id": row["material_id"],
            "name": row["material"]["name"],
            "unit": row["unit"],
            "bom_quantity": str(
                _qty(Decimal(str(row["required_quantity"])) / Decimal(str(quantity)))
            ),
            "required_quantity": str(_qty(row["required_quantity"])),
            "source": row["source"],
        }
        for row in rows
    ]


def _create_factory_supply(plan_line, user):
    sale_line = plan_line.plan.sale_line
    sale = sale_line.sale
    actor = _actor(user) or sale.recorded_by
    if actor is None:
        raise ValueError("Factory planning requires an accountable user.")
    order = ProductionOrder.objects.create(
        sale=sale,
        invoice_number=sale.invoice_number or "",
        customer_name=sale.customer.full_name if sale.customer_id else "",
        branch_name=sale.branch.label if sale.branch_id else "",
        delivery_date=sale.delivery_date or date.today(),
        product_name=sale_line.product_name,
        product_model=sale_line.product_model,
        general_notes=f"Fulfillment plan line {plan_line.uuid}",
        created_by=actor,
    )
    from backend.models import BOMVersion
    from logic.production import bom_snapshot, create_run, publish_bom_version, release_run

    bom = None
    if sale_line.product_id:
        bom = (
            BOMVersion.objects.filter(
                product=sale_line.product, status=BOMVersion.STATUS_PUBLISHED
            ).order_by("-version").first()
            or publish_bom_version(sale_line.product, user=actor)
        )
    # Freeze the exact order choices; a published catalog BOM may contain different
    # per-piece paint/fabric defaults from this sale.
    snapshot = _bom_snapshot(sale_line, _qty(plan_line.quantity))
    plan_line.production_order = order
    plan_line.bom_version = bom
    plan_line.bom_snapshot = snapshot
    plan_line.save(update_fields=[
        "production_order", "bom_version", "bom_snapshot", "updated_at",
    ])
    if sale_line.product_id and sale_line.variant_id:
        run = release_run(create_run(plan_line, user=actor), user=actor)
        from backend.models import PurchaseRequestLine

        shortage_line = PurchaseRequestLine.objects.filter(
            source_type="production_run", source_key=str(run.uuid)
        ).select_related("request").first()
        plan_line.shortage_request = shortage_line.request if shortage_line else None
        shortages = [
            {
                "material_id": req.material_id,
                "required_quantity": str(req.required_quantity),
                "shortage": str(req.shortage_quantity),
            }
            for req in run.requirements.filter(shortage_quantity__gt=0)
        ]
        plan_line.status = (
            FulfillmentPlanLine.STATUS_BLOCKED
            if run.status == run.STATUS_BLOCKED
            else FulfillmentPlanLine.STATUS_PLANNED
        )
    else:
        # Legacy catalog rows without a ProductVariant keep the phase-4 path;
        # their BOM is still versioned/frozen, but no finished-goods lot can exist.
        # Existing rows may hold unlocated global material stock. The legacy
        # completion service performs its own locked shortage check.
        plan_line.shortage_request = None
        shortages = []
        plan_line.status = FulfillmentPlanLine.STATUS_PLANNED
    plan_line.shortage_snapshot = shortages
    plan_line.save(
        update_fields=[
            "shortage_request", "shortage_snapshot", "status", "updated_at",
        ]
    )


def _create_route_line(plan, spec, user):
    route = (spec.get("route_kind") or spec.get("route") or "").strip()
    if route not in dict(FulfillmentPlanLine.ROUTE_CHOICES):
        raise ValueError("Fulfillment route is invalid.")
    quantity = _qty(spec.get("quantity"))
    if quantity <= 0:
        raise ValueError("Fulfillment quantity must be greater than zero.")
    fields = {"plan": plan, "route_kind": route, "quantity": quantity, "note": spec.get("note") or ""}
    location = None
    if route == FulfillmentPlanLine.ROUTE_BRANCH:
        location = parse_location(
            {"kind": "branch", "branch": spec.get("branch") or spec.get("source_branch")},
            required=True,
        )
    elif route == FulfillmentPlanLine.ROUTE_WAREHOUSE:
        location = parse_location(
            {"kind": "warehouse", "warehouse_id": spec.get("warehouse_id")}, required=True
        )
    if location:
        fields.update(
            source_location_kind=location["kind"],
            source_warehouse=location.get("warehouse"),
            source_branch=location.get("branch"),
        )
    row = FulfillmentPlanLine.objects.create(**fields)
    sale_line = plan.sale_line
    if route in {FulfillmentPlanLine.ROUTE_BRANCH, FulfillmentPlanLine.ROUTE_WAREHOUSE}:
        if sale_line.variant_id is None:
            raise ValueError("Stock fulfillment requires a product variant.")
        row.reservation = reserve_stock(
            sale_line.variant,
            quantity,
            location=location,
            user=_actor(user),
            sale=sale_line.sale,
            order_line=sale_line,
            reference=f"fulfillment:{row.uuid}",
            reason="fulfillment_plan",
        )
        row.status = FulfillmentPlanLine.STATUS_RESERVED
        row.save(update_fields=["reservation", "status", "updated_at"])
    elif route == FulfillmentPlanLine.ROUTE_FACTORY:
        _create_factory_supply(row, user)
    else:
        destination = _destination_for_sale(sale_line.sale)
        MerchantSupplyDemand.objects.create(
            plan_line=row,
            product=sale_line.product,
            variant=sale_line.variant,
            quantity=quantity,
            destination_kind=destination["kind"],
            warehouse=destination.get("warehouse"),
            branch=destination.get("branch"),
            requested_by=_actor(user),
        )
    return row


@transaction.atomic
def save_fulfillment_plan(sale_line, lines, *, user=None):
    """Create/replace one line's split plan while holding the sale-line lock."""
    require_feature(FULFILLMENT)
    locked = SaleLineItem.objects.select_for_update().select_related(
        "sale__customer", "sale__branch", "product", "variant"
    ).get(pk=sale_line.pk)
    if not isinstance(lines, list) or not lines:
        raise ValueError("At least one fulfillment route is required.")
    total = sum((_qty(row.get("quantity")) for row in lines), Decimal("0"))
    if total > _qty(locked.quantity):
        raise ValueError("Planned quantity cannot exceed the sale line quantity.")
    plan, _ = FulfillmentPlan.objects.select_for_update().get_or_create(
        sale_line=locked, defaults={"created_by": _actor(user), "updated_by": _actor(user)}
    )
    if plan.status == FulfillmentPlan.STATUS_EXECUTED:
        raise ValueError("An executed fulfillment plan cannot be changed.")
    _release_plan_lines(plan, user=user, cancel=True)
    plan.status = FulfillmentPlan.STATUS_PLANNED
    plan.updated_by = _actor(user)
    plan.save(update_fields=["status", "updated_by", "updated_at"])
    for spec in lines:
        _create_route_line(plan, spec, user)
    return plan


def _release_plan_lines(plan, *, user=None, cancel=False):
    for line in plan.lines.select_related("reservation").all():
        if line.reservation_id and line.reservation.status == InventoryReservation.STATUS_ACTIVE:
            release_reservation(line.reservation, user=_actor(user), reason="fulfillment_released")
        if hasattr(line, "merchant_demand") and line.merchant_demand.status in {
            MerchantSupplyDemand.STATUS_OPEN, MerchantSupplyDemand.STATUS_ORDERED
        }:
            line.merchant_demand.status = MerchantSupplyDemand.STATUS_CANCELLED
            line.merchant_demand.save(update_fields=["status", "updated_at"])
        if line.production_order_id and line.production_order.status == ProductionOrder.STATUS_PENDING:
            line.production_order.status = ProductionOrder.STATUS_CANCELLED
            line.production_order.save(update_fields=["status", "updated_at"])
        if line.shortage_request_id and line.shortage_request.status == line.shortage_request.STATUS_DRAFT:
            line.shortage_request.status = line.shortage_request.STATUS_CANCELLED
            line.shortage_request.save(update_fields=["status", "updated_at"])
        line.status = (
            FulfillmentPlanLine.STATUS_CANCELLED if cancel else FulfillmentPlanLine.STATUS_RELEASED
        )
        line.save(update_fields=["status", "updated_at"])


@transaction.atomic
def release_fulfillment_plan(plan, *, user=None, cancel=False):
    require_feature(FULFILLMENT)
    locked = FulfillmentPlan.objects.select_for_update().get(pk=plan.pk)
    if locked.status in {FulfillmentPlan.STATUS_RELEASED, FulfillmentPlan.STATUS_CANCELLED}:
        return locked
    if locked.status == FulfillmentPlan.STATUS_EXECUTED:
        raise ValueError("An executed plan cannot be released.")
    _release_plan_lines(locked, user=user)
    locked.status = FulfillmentPlan.STATUS_CANCELLED if cancel else FulfillmentPlan.STATUS_RELEASED
    locked.updated_by = _actor(user)
    locked.save(update_fields=["status", "updated_by", "updated_at"])
    return locked


@transaction.atomic
def release_sale_fulfillment(sale, *, user=None, cancel=True):
    plans = FulfillmentPlan.objects.select_for_update().filter(sale_line__sale=sale)
    if not plans.exists():
        return []
    require_feature(FULFILLMENT)
    return [release_fulfillment_plan(plan, user=user, cancel=cancel) for plan in plans]


@transaction.atomic
def receive_merchant_supply(demand, *, unit_cost, user=None):
    require_feature(FULFILLMENT)
    locked = MerchantSupplyDemand.objects.select_for_update().select_related("variant").get(pk=demand.pk)
    if locked.status == MerchantSupplyDemand.STATUS_RECEIVED:
        return locked
    if locked.status == MerchantSupplyDemand.STATUS_CANCELLED:
        raise ValueError("A cancelled merchant demand cannot be received.")
    if locked.variant_id is None:
        raise ValueError("Merchant receipt requires a product variant.")
    try:
        cost = Decimal(str(unit_cost))
    except Exception as exc:
        raise ValueError("Merchant unit cost is invalid.") from exc
    if cost < 0:
        raise ValueError("Merchant unit cost cannot be negative.")
    from logic.inventory_costing import adjust_stock

    location = {
        "kind": locked.destination_kind,
        "warehouse": locked.warehouse,
        "branch": locked.branch,
    }
    movement = adjust_stock(
        locked.variant,
        locked.quantity,
        unit_cost=cost,
        location=location,
        user=_actor(user),
        reason="merchant_goods_receipt",
        reference=f"merchant:{locked.uuid}",
    )
    locked.receipt_movement = movement
    locked.status = MerchantSupplyDemand.STATUS_RECEIVED
    locked.save(update_fields=["receipt_movement", "status", "updated_at"])
    return locked


@transaction.atomic
def execute_fulfillment_plan(plan, *, user=None):
    require_feature(FULFILLMENT)
    locked = FulfillmentPlan.objects.select_for_update().select_related("sale_line__sale").get(pk=plan.pk)
    if locked.status == FulfillmentPlan.STATUS_EXECUTED:
        return locked
    # A plan is never issued independently: delivery is all-or-nothing across
    # the sale because reservations are exact-quantity reservations.
    from logic.delivery import deliver_sale

    deliver_sale(locked.sale_line.sale, user=user)
    return FulfillmentPlan.objects.get(pk=locked.pk)


def plan_to_dict(plan):
    return {
        "uuid": str(plan.uuid),
        "sale_line_id": plan.sale_line_id,
        "status": plan.status,
        "planned_quantity": float(
            plan.lines.exclude(status=FulfillmentPlanLine.STATUS_CANCELLED).aggregate(
                total=Sum("quantity")
            )["total"] or Decimal("0")
        ),
        "lines": [
            {
                "uuid": str(row.uuid),
                "route_kind": row.route_kind,
                "quantity": float(row.quantity),
                "status": row.status,
                "source_location_kind": row.source_location_kind,
                "warehouse_id": row.source_warehouse_id,
                "branch": row.source_branch_id,
                "reservation_uuid": str(row.reservation.uuid) if row.reservation_id else None,
                "production_order_id": row.production_order_id,
                "purchase_request_uuid": (
                    str(row.shortage_request.uuid) if row.shortage_request_id else None
                ),
                "merchant_demand_uuid": (
                    str(row.merchant_demand.uuid) if hasattr(row, "merchant_demand") else None
                ),
                "bom_snapshot": row.bom_snapshot,
                "shortages": row.shortage_snapshot,
            }
            for row in plan.lines.exclude(
                status=FulfillmentPlanLine.STATUS_CANCELLED
            ).select_related(
                "reservation", "shortage_request", "merchant_demand"
            ).all()
        ],
    }


@transaction.atomic
def assert_factory_fulfillment_ready(sale):
    """Refresh BOM shortages and prevent production start while any remain."""
    from backend.models import Material

    location = parse_location(
        {"kind": "warehouse", "warehouse_id": default_warehouse().pk}, required=True
    )
    blocked = []
    rows = FulfillmentPlanLine.objects.select_for_update().filter(
        plan__sale_line__sale=sale,
        route_kind=FulfillmentPlanLine.ROUTE_FACTORY,
        status=FulfillmentPlanLine.STATUS_BLOCKED,
    )
    for line in rows:
        if hasattr(line, "production_run"):
            from logic.production import release_run

            run = release_run(line.production_run)
            shortages = [
                {
                    "material_id": req.material_id,
                    "required_quantity": str(req.required_quantity),
                    "available_quantity": str(req.required_quantity - req.shortage_quantity),
                    "shortage": str(req.shortage_quantity),
                }
                for req in run.requirements.filter(shortage_quantity__gt=0)
            ]
            line.shortage_snapshot = shortages
            if shortages:
                blocked.append(line)
            else:
                line.status = FulfillmentPlanLine.STATUS_PLANNED
            line.save(update_fields=["shortage_snapshot", "status", "updated_at"])
            continue
        shortages = []
        for requirement in line.bom_snapshot:
            material = Material.objects.filter(pk=requirement.get("material_id")).first()
            required = _qty(requirement.get("required_quantity"))
            available_qty = (
                _qty(availability(material, location=location)["available"]) if material else Decimal("0")
            )
            if available_qty < required:
                shortages.append({
                    "material_id": requirement.get("material_id"),
                    "required_quantity": str(required),
                    "available_quantity": str(available_qty),
                    "shortage": str(required - available_qty),
                })
        line.shortage_snapshot = shortages
        if shortages:
            blocked.append(line)
        else:
            line.status = FulfillmentPlanLine.STATUS_PLANNED
        line.save(update_fields=["shortage_snapshot", "status", "updated_at"])
    if blocked:
        raise ValueError("Material shortages must be resolved before production can start.")
    return True


@transaction.atomic
def start_stock_transfer(
    variant, source, destination, quantity, *, idempotency_key, user=None, plan_line=None
):
    require_feature(FULFILLMENT)
    key = (idempotency_key or "").strip()
    if not key:
        raise ValueError("Transfer idempotency key is required.")
    existing = StockTransfer.objects.filter(idempotency_key=key).first()
    if existing:
        return existing
    if source["kind"] == destination["kind"] and (
        source.get("warehouse_id"), source.get("branch_id")
    ) == (destination.get("warehouse_id"), destination.get("branch_id")):
        raise ValueError("Transfer source and destination must differ.")
    consumed = consume_stock(
        variant,
        quantity,
        location=source,
        user=_actor(user),
        reason="stock_transfer_issue",
        reference=f"transfer:{key}",
    )
    transfer = StockTransfer.objects.create(
        idempotency_key=key,
        plan_line=plan_line,
        variant=variant,
        quantity=_qty(quantity),
        source_kind=source["kind"],
        source_warehouse=source.get("warehouse"),
        source_branch=source.get("branch"),
        destination_kind=destination["kind"],
        destination_warehouse=destination.get("warehouse"),
        destination_branch=destination.get("branch"),
        issue_movement=consumed["movement"],
        created_by=_actor(user),
    )
    # Same-value internal transfers are memo events: traceable and idempotent, with no GL journal.
    from logic.accounting_events import register_event

    event, _ = register_event(
        source_module="inventory",
        source_type="StockTransfer",
        source=transfer,
        event_type="location_transfer",
        payload={
            "transfer_uuid": str(transfer.uuid),
            "quantity": str(transfer.quantity),
            "variant_id": variant.pk,
            "same_value_no_gl": True,
        },
    )
    transfer.accounting_event = event
    transfer.save(update_fields=["accounting_event"])
    return transfer


@transaction.atomic
def complete_stock_transfer(transfer, *, user=None):
    require_feature(FULFILLMENT)
    locked = StockTransfer.objects.select_for_update().select_related("variant", "issue_movement").get(
        pk=transfer.pk
    )
    if locked.status == StockTransfer.STATUS_COMPLETED:
        return locked
    if locked.status != StockTransfer.STATUS_IN_TRANSIT:
        raise ValueError("Only an in-transit transfer can be completed.")
    destination = {
        "kind": locked.destination_kind,
        "warehouse": locked.destination_warehouse,
        "branch": locked.destination_branch,
    }
    from logic.inventory_costing import adjust_stock

    receipt = adjust_stock(
        locked.variant,
        locked.quantity,
        unit_cost=locked.issue_movement.unit_cost,
        location=destination,
        reason="stock_transfer_receipt",
        reference=f"transfer:{locked.idempotency_key}",
        user=_actor(user),
    )
    locked.receipt_movement = receipt
    locked.status = StockTransfer.STATUS_COMPLETED
    locked.received_by = _actor(user)
    locked.received_at = timezone.now()
    locked.save(
        update_fields=["receipt_movement", "status", "received_by", "received_at"]
    )
    return locked
