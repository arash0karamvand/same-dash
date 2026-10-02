"""Versioned BOM publication and lock-safe production execution."""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone

from auth.permissions import MANAGE_FACTORY_ORDERS, has_permission
from backend.models import (
    BOMLine,
    BOMVersion,
    InventoryCostLayer,
    InventoryTransaction,
    Material,
    MaterialRequirement,
    ProductLot,
    ProductMaterial,
    ProductionEvent,
    ProductionRun,
)
from logic.accounting_accounts import get_account
from logic.accounting_events import issue_event_draft, issue_through_gateway, register_event
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.inventory_costing import (
    availability,
    consume_stock,
    receive_stock,
    reserve_stock,
)
from logic.feature_flags import ACTUAL_COST_PRODUCTION, require_feature
from logic.ledger import LEGAL_LEDGER
from logic.stock_locations import default_warehouse


def _qty(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.001"))


def _money(value):
    return Decimal(value or 0).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _actor(user):
    return user if getattr(user, "is_authenticated", False) else None


def _warehouse_location(warehouse):
    return {
        "kind": InventoryTransaction.LOCATION_WAREHOUSE,
        "warehouse": warehouse,
        "warehouse_id": warehouse.pk,
    }


def _approved(material):
    return (
        material
        and not material.is_deleted
        and material.is_active
        and material.approval_status == Material.APPROVAL_APPROVED
    )


def _collect_product_bom(product):
    """Merge product, piece recipes and per-piece frames through the shared resolver."""
    from logic.materials import resolve_material_requirements

    rows = defaultdict(lambda: {"quantity": Decimal("0"), "spoilage": Decimal("0"), "sources": []})
    resolved = resolve_material_requirements(
        product=product, quantity=1, include_unapproved=True
    )
    material_map = {
        material.pk: material
        for material in Material.objects.filter(
            pk__in=[
                item["material_id"]
                for item in resolved
            ]
        )
    }
    for item in resolved:
        material = material_map.get(item["material_id"])
        if not _approved(material):
            label = getattr(material, "name", str(item["material_id"]))
            raise ValueError(f"Material {label} must be active and approved before BOM publication.")
        sources = item.get("source_labels") or [item.get("source") or "product"]
        source_kind = (
            BOMLine.SOURCE_FRAME
            if "frame" in sources
            else BOMLine.SOURCE_RECIPE
            if any(source in sources for source in ("paint", "fabric", "foam", "cushion", "webbing"))
            else BOMLine.SOURCE_PRODUCT
        )
        rows[material.pk] = {
            "material": material,
            "quantity": _qty(item["required_quantity"]),
            "spoilage": Decimal(str(item.get("normal_spoilage_rate") or 0)),
            "sources": [
                {"kind": source_kind, "reference": "+".join(sources)}
            ],
        }
    return rows


@transaction.atomic
def publish_bom_version(product, *, user=None):
    require_feature(ACTUAL_COST_PRODUCTION)
    locked_product = type(product).objects.select_for_update().get(pk=product.pk)
    rows = _collect_product_bom(locked_product)
    if not rows:
        raise ValueError("The product has no publishable material requirements.")
    version = (
        BOMVersion.objects.filter(product=locked_product).aggregate(value=Max("version"))["value"] or 0
    ) + 1
    bom = BOMVersion.objects.create(
        product=locked_product,
        version=version,
        source_snapshot={
            "product_material_ids": list(
                ProductMaterial.objects.filter(product=locked_product).values_list("material_id", flat=True)
            ),
            "published_from_catalog_at": timezone.now().isoformat(),
        },
    )
    for order, (material_id, row) in enumerate(sorted(rows.items())):
        sources = row["sources"]
        BOMLine.objects.create(
            bom_version=bom,
            material=row["material"],
            quantity=row["quantity"],
            normal_spoilage_rate=row["spoilage"],
            source_kind=sources[0]["kind"],
            source_reference=";".join(source["reference"] for source in sources)[:100],
            sort_order=order,
        )
    bom.status = BOMVersion.STATUS_PUBLISHED
    bom.published_at = timezone.now()
    bom.published_by = _actor(user)
    bom.save(update_fields=["status", "published_at", "published_by"])
    BOMVersion.objects.filter(
        product=locked_product, status=BOMVersion.STATUS_PUBLISHED
    ).exclude(pk=bom.pk).update(status=BOMVersion.STATUS_RETIRED)
    return bom


def bom_snapshot(bom, quantity=1):
    multiplier = _qty(quantity)
    return [
        {
            "bom_version_uuid": str(bom.uuid),
            "bom_line_id": line.pk,
            "material_id": line.material_id,
            "name": line.material.name,
            "unit": line.material.unit,
            "bom_quantity": str(line.quantity),
            "required_quantity": str(_qty(line.quantity * multiplier)),
            "normal_spoilage_rate": str(line.normal_spoilage_rate),
            "source": line.source_kind,
        }
        for line in bom.lines.select_related("material").all()
    ]


@transaction.atomic
def create_run(plan_line, *, user=None, warehouse=None):
    require_feature(ACTUAL_COST_PRODUCTION)
    if hasattr(plan_line, "production_run"):
        return plan_line.production_run
    sale_line = plan_line.plan.sale_line
    if not sale_line.product_id or not sale_line.variant_id or not plan_line.production_order_id:
        raise ValueError("Production requires a product variant and production order.")
    bom = plan_line.bom_version
    if bom is None:
        bom = (
            BOMVersion.objects.filter(
                product=sale_line.product, status=BOMVersion.STATUS_PUBLISHED
            ).order_by("-version").first()
            or publish_bom_version(sale_line.product, user=user)
        )
        plan_line.bom_version = bom
        plan_line.bom_snapshot = bom_snapshot(bom, plan_line.quantity)
        plan_line.save(update_fields=["bom_version", "bom_snapshot", "updated_at"])
    run = ProductionRun.objects.create(
        production_order=plan_line.production_order,
        fulfillment_plan_line=plan_line,
        sale=sale_line.sale,
        product=sale_line.product,
        variant=sale_line.variant,
        bom_version=bom,
        quantity=plan_line.quantity,
        warehouse=warehouse or default_warehouse(),
        created_by=_actor(user),
    )
    for line in bom.lines.select_related("material").all():
        MaterialRequirement.objects.create(
            run=run,
            bom_line=line,
            material=line.material,
            required_quantity=_qty(line.quantity * run.quantity),
        )
    return run


@transaction.atomic
def release_run(run, *, user=None):
    require_feature(ACTUAL_COST_PRODUCTION)
    locked = ProductionRun.objects.select_for_update().get(pk=run.pk)
    if locked.status in {
        ProductionRun.STATUS_RELEASED, ProductionRun.STATUS_IN_PROGRESS,
        ProductionRun.STATUS_COMPLETED,
    }:
        return locked
    location = _warehouse_location(locked.warehouse)
    shortages = []
    for req in locked.requirements.select_for_update().select_related("material", "reservation"):
        if req.reservation_id:
            continue
        available_qty = max(Decimal("0"), availability(req.material, location=location)["available"])
        reserve_qty = min(available_qty, req.required_quantity)
        if reserve_qty == req.required_quantity:
            req.reservation = reserve_stock(
                req.material,
                req.required_quantity,
                location=location,
                user=_actor(user),
                sale=locked.sale,
                production_order=locked.production_order,
                reference=f"production:{locked.uuid}",
                reason="production_requirement",
            )
            req.shortage_quantity = 0
        else:
            req.shortage_quantity = req.required_quantity - reserve_qty
            shortages.append(req)
        req.save(update_fields=["reservation", "shortage_quantity"])
    if shortages:
        from logic.procurement import generate_shortage_requests

        generate_shortage_requests(
            [
                {
                    "material_id": req.material_id,
                    # Procurement owns netting against available stock/incoming
                    # orders. Passing the already-netted shortage would subtract
                    # availability twice and can suppress a real request.
                    "quantity": req.required_quantity,
                    "source_type": "production_run",
                    "source_key": str(locked.uuid),
                    "sale_id": locked.sale_id,
                    "production_order_id": locked.production_order_id,
                }
                for req in shortages
            ],
            location=location,
            user=_actor(user),
            note=f"Production shortage {locked.uuid}",
        )
        locked.status = ProductionRun.STATUS_BLOCKED
    else:
        locked.status = ProductionRun.STATUS_RELEASED
        locked.released_at = timezone.now()
    locked.save(update_fields=["status", "released_at"])
    return locked


def _material_journal(event, rule_name, *, user, description):
    financial, journal, _ = issue_through_gateway(
        source_module="production",
        source_type="ProductionEvent",
        source=event,
        event_type=event.event_type,
        rule_name=rule_name,
        amounts={"cost": event.total_cost},
        entry_type="adjustment",
        description=description,
        payload={
            "run_uuid": str(event.run.uuid),
            "event_uuid": str(event.uuid),
            "material_id": event.material_id,
            "quantity": str(event.quantity),
            "cost": str(event.total_cost),
        },
        ledger=LEGAL_LEDGER,
        user=user,
        production_order=event.run.production_order,
        inventory_transaction=event.inventory_transaction,
    )
    financial.refresh_from_db()
    event.financial_event = financial
    event.save(update_fields=["financial_event"])
    return journal


@transaction.atomic
def consume_requirement(requirement, *, user=None, idempotency_key=None):
    require_feature(ACTUAL_COST_PRODUCTION)
    key = (idempotency_key or f"production:{requirement.run.uuid}:requirement:{requirement.pk}").strip()
    existing = ProductionEvent.objects.filter(idempotency_key=key).first()
    if existing:
        return existing
    req = MaterialRequirement.objects.select_for_update().select_related(
        "run__warehouse", "run__production_order", "reservation", "material"
    ).get(pk=requirement.pk)
    if req.run.status not in {ProductionRun.STATUS_RELEASED, ProductionRun.STATUS_IN_PROGRESS}:
        raise ValueError("The production run must be released before consumption.")
    if not req.reservation_id:
        raise ValueError("The material requirement has no complete reservation.")
    result = consume_stock(
        req.material,
        req.required_quantity,
        reservation=req.reservation,
        user=_actor(user),
        reason="production_actual_consumption",
        reference=f"production:{req.run.uuid}",
        sale=req.run.sale,
        production_order=req.run.production_order,
    )
    event = ProductionEvent.objects.create(
        idempotency_key=key,
        run=req.run,
        event_type=ProductionEvent.TYPE_CONSUMPTION,
        material=req.material,
        quantity=req.required_quantity,
        total_cost=result["total_cost"],
        consumption=result["consumption"],
        inventory_transaction=result["movement"],
        recorded_by=_actor(user),
    )
    _material_journal(event, "material_consumption", user=user, description=f"Production consumption {req.run.uuid}")
    if req.run.status == ProductionRun.STATUS_RELEASED:
        req.run.status = ProductionRun.STATUS_IN_PROGRESS
        req.run.started_at = timezone.now()
        req.run.save(update_fields=["status", "started_at"])
    return event


@transaction.atomic
def consume_extra(run, material, quantity, *, reason, user, idempotency_key):
    require_feature(ACTUAL_COST_PRODUCTION)
    if not (reason or "").strip():
        raise ValueError("Extra material usage requires an explicit reason.")
    if not (
        getattr(user, "is_superuser", False)
        or (getattr(user, "is_authenticated", False) and has_permission(user, MANAGE_FACTORY_ORDERS))
    ):
        raise PermissionDenied("Extra material usage requires factory-management authorization.")
    key = (idempotency_key or "").strip()
    if not key:
        raise ValueError("An idempotency key is required.")
    existing = ProductionEvent.objects.filter(idempotency_key=key).first()
    if existing:
        return existing
    locked = ProductionRun.objects.select_for_update().get(pk=run.pk)
    if locked.status not in {ProductionRun.STATUS_RELEASED, ProductionRun.STATUS_IN_PROGRESS}:
        raise ValueError("The production run is not open for consumption.")
    result = consume_stock(
        material,
        quantity,
        location=_warehouse_location(locked.warehouse),
        user=user,
        reason="production_extra_consumption",
        reference=f"production:{locked.uuid}",
        sale=locked.sale,
        production_order=locked.production_order,
    )
    event = ProductionEvent.objects.create(
        idempotency_key=key,
        run=locked,
        event_type=ProductionEvent.TYPE_EXTRA_CONSUMPTION,
        material=material,
        quantity=_qty(quantity),
        total_cost=result["total_cost"],
        reason=reason.strip(),
        consumption=result["consumption"],
        inventory_transaction=result["movement"],
        authorized_by=user,
        recorded_by=user,
    )
    _material_journal(event, "material_consumption", user=user, description=f"Extra production usage {locked.uuid}")
    if locked.status == ProductionRun.STATUS_RELEASED:
        locked.status = ProductionRun.STATUS_IN_PROGRESS
        locked.started_at = timezone.now()
        locked.save(update_fields=["status", "started_at"])
    return event


@transaction.atomic
def return_material(original_event, quantity, *, reason, user=None, idempotency_key=None):
    require_feature(ACTUAL_COST_PRODUCTION)
    qty = _qty(quantity)
    if original_event.event_type not in {
        ProductionEvent.TYPE_CONSUMPTION, ProductionEvent.TYPE_EXTRA_CONSUMPTION
    }:
        raise ValueError("Returns must reference a material-consumption event.")
    returned = original_event.reversals.filter(event_type=ProductionEvent.TYPE_RETURN).aggregate(
        value=Sum("quantity")
    )["value"] or Decimal("0")
    if qty <= 0 or returned + qty > original_event.quantity:
        raise ValueError("Return quantity exceeds the unreversed consumption.")
    key = (idempotency_key or f"production:return:{original_event.uuid}:{returned + qty}").strip()
    existing = ProductionEvent.objects.filter(idempotency_key=key).first()
    if existing:
        return existing
    unit_cost = original_event.total_cost / original_event.quantity
    movement = receive_stock(
        original_event.material,
        qty,
        unit_cost,
        reason="production_material_return",
        reference=f"production:{original_event.run.uuid}",
        recorded_by=_actor(user),
        location=_warehouse_location(original_event.run.warehouse),
        metadata={"original_production_event": str(original_event.uuid)},
    )
    event = ProductionEvent.objects.create(
        idempotency_key=key,
        run=original_event.run,
        event_type=ProductionEvent.TYPE_RETURN,
        material=original_event.material,
        quantity=qty,
        total_cost=_money(unit_cost * qty),
        reason=(reason or "").strip(),
        inventory_transaction=movement,
        original_event=original_event,
        recorded_by=_actor(user),
    )
    _material_journal(
        event, "material_consumption_reverse", user=user,
        description=f"Production material return {event.run.uuid}",
    )
    return event


@transaction.atomic
def record_scrap(run, material, quantity, *, reason, user=None, idempotency_key=None):
    require_feature(ACTUAL_COST_PRODUCTION)
    if not (reason or "").strip():
        raise ValueError("Scrap requires a reason.")
    key = (idempotency_key or "").strip()
    if not key:
        raise ValueError("An idempotency key is required.")
    existing = ProductionEvent.objects.filter(idempotency_key=key).first()
    if existing:
        return existing
    # Scrap is a classification of material already issued to WIP. It does not
    # mutate the original consumption or issue inventory a second time.
    consumed_cost = run.events.filter(
        material=material,
        event_type__in=[ProductionEvent.TYPE_CONSUMPTION, ProductionEvent.TYPE_EXTRA_CONSUMPTION],
    ).aggregate(value=Sum("total_cost"))["value"] or Decimal("0")
    consumed_qty = run.events.filter(
        material=material,
        event_type__in=[ProductionEvent.TYPE_CONSUMPTION, ProductionEvent.TYPE_EXTRA_CONSUMPTION],
    ).aggregate(value=Sum("quantity"))["value"] or Decimal("0")
    if consumed_qty <= 0:
        raise ValueError("Scrap cannot exceed issued WIP material.")
    qty = _qty(quantity)
    returned_qty = run.events.filter(
        material=material, event_type=ProductionEvent.TYPE_RETURN
    ).aggregate(value=Sum("quantity"))["value"] or Decimal("0")
    prior_scrap = run.events.filter(
        material=material, event_type=ProductionEvent.TYPE_SCRAP
    ).aggregate(value=Sum("quantity"))["value"] or Decimal("0")
    if qty <= 0 or prior_scrap + qty > consumed_qty - returned_qty:
        raise ValueError("Scrap quantity exceeds material remaining in WIP.")
    cost = _money((consumed_cost / consumed_qty) * qty)
    event = ProductionEvent.objects.create(
        idempotency_key=key,
        run=run,
        event_type=ProductionEvent.TYPE_SCRAP,
        material=material,
        quantity=qty,
        total_cost=cost,
        reason=reason.strip(),
        recorded_by=_actor(user),
    )
    financial, _ = register_event(
        source_module="production",
        source_type="ProductionEvent",
        source=event,
        event_type="scrap",
        payload={"run_uuid": str(run.uuid), "quantity": str(qty), "cost": str(cost), "reason": reason},
    )
    expense = get_account(ACCOUNT_SLUGS.ADMIN_OVERHEAD, ledger=LEGAL_LEDGER)
    wip = get_account(ACCOUNT_SLUGS.WIP_INVENTORY, ledger=LEGAL_LEDGER)
    issue_event_draft(
        financial,
        lines=[
            {"account": expense, "debit": cost, "credit": 0, "description": reason},
            {"account": wip, "debit": 0, "credit": cost, "description": reason},
        ],
        entry_type="adjustment",
        description=f"Production scrap {run.uuid}",
        user=user,
        production_order=run.production_order,
    )
    financial.refresh_from_db()
    event.financial_event = financial
    event.save(update_fields=["financial_event"])
    return event


@transaction.atomic
def complete_run(run, *, overhead_cost=0, user=None, idempotency_key=None):
    require_feature(ACTUAL_COST_PRODUCTION)
    key = (idempotency_key or f"production:complete:{run.uuid}").strip()
    existing = ProductionEvent.objects.filter(idempotency_key=key).first()
    if existing:
        return existing
    locked = ProductionRun.objects.select_for_update().select_related(
        "variant", "warehouse", "production_order"
    ).get(pk=run.pk)
    if locked.status == ProductionRun.STATUS_COMPLETED:
        return locked.events.get(event_type=ProductionEvent.TYPE_COMPLETION)
    if locked.status != ProductionRun.STATUS_IN_PROGRESS:
        raise ValueError("All production material must be issued before completion.")
    if locked.requirements.exclude(
        reservation__status="consumed"
    ).exists():
        raise ValueError("All production requirements must be consumed before completion.")
    # Partial completion is deliberately prohibited: a run creates one immutable lot.
    returned_cost = locked.events.filter(event_type=ProductionEvent.TYPE_RETURN).aggregate(
        value=Sum("total_cost")
    )["value"] or Decimal("0")
    issued_cost = locked.events.filter(
        event_type__in=[ProductionEvent.TYPE_CONSUMPTION, ProductionEvent.TYPE_EXTRA_CONSUMPTION]
    ).aggregate(value=Sum("total_cost"))["value"] or Decimal("0")
    scrap_cost = locked.events.filter(event_type=ProductionEvent.TYPE_SCRAP).aggregate(
        value=Sum("total_cost")
    )["value"] or Decimal("0")
    material_cost = _money(issued_cost - returned_cost - scrap_cost)
    overhead = _money(overhead_cost)
    if overhead < 0:
        raise ValueError("Allocated overhead cannot be negative.")
    total = _money(material_cost + overhead)
    unit_cost = _money(total / locked.quantity)
    movement = InventoryTransaction.objects.create(
        variant=locked.variant,
        location_kind=InventoryTransaction.LOCATION_WAREHOUSE,
        warehouse=locked.warehouse,
        quantity=locked.quantity,
        unit_cost=unit_cost,
        reason="production_completion",
        reference=f"production:{locked.uuid}",
        recorded_by=_actor(user),
    )
    layer = InventoryCostLayer.objects.create(
        variant=locked.variant,
        source_transaction=movement,
        location_kind=InventoryTransaction.LOCATION_WAREHOUSE,
        warehouse=locked.warehouse,
        unit_cost=unit_cost,
        original_qty=locked.quantity,
        qty_remaining=locked.quantity,
        metadata={"production_run_uuid": str(locked.uuid), "actual_cost": True},
    )
    now = timezone.now()
    lot = ProductLot.objects.create(
        lot_number=f"PR-{locked.pk}-{now:%Y%m%d%H%M%S}",
        run=locked,
        variant=locked.variant,
        warehouse=locked.warehouse,
        quantity=locked.quantity,
        unit_cost=unit_cost,
        total_cost=total,
        inventory_transaction=movement,
        cost_layer=layer,
        completed_at=now,
    )
    event = ProductionEvent.objects.create(
        idempotency_key=key,
        run=locked,
        event_type=ProductionEvent.TYPE_COMPLETION,
        quantity=locked.quantity,
        total_cost=total,
        inventory_transaction=movement,
        recorded_by=_actor(user),
    )
    financial, _ = register_event(
        source_module="production",
        source_type="ProductionEvent",
        source=event,
        event_type="completion",
        payload={
            "run_uuid": str(locked.uuid), "lot_uuid": str(lot.uuid),
            "material_cost": str(material_cost), "overhead_cost": str(overhead),
            "total_cost": str(total),
        },
    )
    finished = get_account(ACCOUNT_SLUGS.FINISHED_GOODS_INVENTORY, ledger=LEGAL_LEDGER)
    wip = get_account(ACCOUNT_SLUGS.WIP_INVENTORY, ledger=LEGAL_LEDGER)
    issue_event_draft(
        financial,
        lines=[
            {"account": finished, "debit": total, "credit": 0, "description": str(locked.uuid)},
            {"account": wip, "debit": 0, "credit": total, "description": str(locked.uuid)},
        ],
        entry_type="adjustment",
        description=f"Production completion {locked.uuid}",
        user=user,
        production_order=locked.production_order,
        inventory_transaction=movement,
    )
    financial.refresh_from_db()
    event.financial_event = financial
    event.save(update_fields=["financial_event"])
    locked.overhead_cost = overhead
    locked.actual_material_cost = material_cost
    locked.total_cost = total
    locked.status = ProductionRun.STATUS_COMPLETED
    locked.completed_at = now
    locked.completed_by = _actor(user)
    locked.save(update_fields=[
        "overhead_cost", "actual_material_cost", "total_cost", "status",
        "completed_at", "completed_by",
    ])
    locked.production_order.status = locked.production_order.STATUS_COMPLETED
    locked.production_order.save(update_fields=["status", "updated_at"])
    return event


def run_to_dict(run):
    events = run.events.select_related(
        "material", "consumption", "inventory_transaction", "financial_event"
    ).prefetch_related("consumption__allocations__cost_layer")
    return {
        "uuid": str(run.uuid),
        "production_order_id": run.production_order_id,
        "fulfillment_plan_line_uuid": (
            str(run.fulfillment_plan_line.uuid) if run.fulfillment_plan_line_id else None
        ),
        "product_id": run.product_id,
        "variant_id": run.variant_id,
        "bom_version_uuid": str(run.bom_version.uuid),
        "quantity": float(run.quantity),
        "warehouse_id": run.warehouse_id,
        "status": run.status,
        "cost_breakdown": {
            "actual_material": int(run.actual_material_cost),
            "overhead": int(run.overhead_cost),
            "total": int(run.total_cost),
        },
        "requirements": [
            {
                "id": req.pk,
                "material_id": req.material_id,
                "material": req.material.name,
                "required_quantity": float(req.required_quantity),
                "shortage_quantity": float(req.shortage_quantity),
                "reservation_uuid": str(req.reservation.uuid) if req.reservation_id else None,
                "reservation_status": req.reservation.status if req.reservation_id else None,
            }
            for req in run.requirements.select_related("material", "reservation")
        ],
        "events": [
            {
                "uuid": str(event.uuid),
                "event_type": event.event_type,
                "material_id": event.material_id,
                "quantity": float(event.quantity),
                "total_cost": int(event.total_cost),
                "reason": event.reason,
                "original_event_uuid": (
                    str(event.original_event.uuid) if event.original_event_id else None
                ),
                "allocations": [
                    {
                        "layer_uuid": str(allocation.cost_layer.uuid),
                        "quantity": float(allocation.quantity),
                        "unit_cost": int(allocation.unit_cost),
                    }
                    for allocation in (
                        event.consumption.allocations.all() if event.consumption_id else []
                    )
                ],
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
        "product_lot": (
            {
                "uuid": str(run.product_lot.uuid),
                "lot_number": run.product_lot.lot_number,
                "quantity": float(run.product_lot.quantity),
                "unit_cost": int(run.product_lot.unit_cost),
                "total_cost": int(run.product_lot.total_cost),
            }
            if hasattr(run, "product_lot") else None
        ),
    }
