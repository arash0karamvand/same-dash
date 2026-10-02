"""Atomic sale delivery, actual-cost posting, trace, and sales returns."""

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from backend.models import (
    DeliveryDocument,
    DeliveryLine,
    FinancialEvent,
    FulfillmentPlan,
    FulfillmentPlanLine,
    InventoryCostLayer,
    InventoryReservation,
    InventoryTransaction,
    JournalEntry,
    MerchantSupplyDemand,
    Sale,
    SalesReturn,
    SalesReturnLine,
)
from logic.accounting_accounts import get_account, payment_account_for_sale
from logic.accounting_events import issue_event_draft, register_event
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.document_issuance import DocumentIssuanceService
from logic.inventory_costing import consume_stock
from logic.feature_flags import UNIFIED_DELIVERY, require_feature
from logic.ledger import LEGAL_LEDGER
from logic.stock_locations import location_transaction_kwargs


def _qty(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.001"))


def _money(value):
    return Decimal(value or 0).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _actor(user):
    return user if getattr(user, "is_authenticated", False) else None


def _route_location(line):
    if line.route_kind in {FulfillmentPlanLine.ROUTE_BRANCH, FulfillmentPlanLine.ROUTE_WAREHOUSE}:
        return {
            "kind": line.source_location_kind,
            "warehouse": line.source_warehouse,
            "warehouse_id": line.source_warehouse_id,
            "branch": line.source_branch,
            "branch_id": line.source_branch_id,
        }
    if line.route_kind == FulfillmentPlanLine.ROUTE_FACTORY:
        lot = line.production_run.product_lot
        return {"kind": "warehouse", "warehouse": lot.warehouse, "warehouse_id": lot.warehouse_id}
    demand = line.merchant_demand
    return {
        "kind": demand.destination_kind,
        "warehouse": demand.warehouse,
        "warehouse_id": demand.warehouse_id,
        "branch": demand.branch,
        "branch_id": demand.branch_id,
    }


def _validate_ready(sale):
    sale_lines = list(sale.line_items.select_related("variant").all())
    if not sale_lines:
        raise ValueError("Delivery requires catalog sale lines.")
    routes = []
    for sale_line in sale_lines:
        if not sale_line.variant_id:
            raise ValueError("Every delivered sale line must have a product variant.")
        try:
            plan = sale_line.fulfillment_plan
        except FulfillmentPlan.DoesNotExist as exc:
            raise ValueError("Every sale line requires a fulfillment plan before delivery.") from exc
        planned = plan.lines.exclude(status=FulfillmentPlanLine.STATUS_CANCELLED).aggregate(
            total=Sum("quantity")
        )["total"] or Decimal("0")
        if _qty(planned) != _qty(sale_line.quantity):
            raise ValueError("Partial delivery is not supported; every sale line must be fully planned.")
        for line in plan.lines.exclude(status=FulfillmentPlanLine.STATUS_CANCELLED).select_related(
            "reservation", "production_run__product_lot__cost_layer", "merchant_demand"
        ):
            if line.route_kind in {FulfillmentPlanLine.ROUTE_BRANCH, FulfillmentPlanLine.ROUTE_WAREHOUSE}:
                if not line.reservation_id or line.reservation.status != InventoryReservation.STATUS_ACTIVE:
                    raise ValueError("Every stock route requires an active reservation.")
            elif line.route_kind == FulfillmentPlanLine.ROUTE_FACTORY:
                if not hasattr(line, "production_run") or not hasattr(line.production_run, "product_lot"):
                    raise ValueError("Factory delivery requires a completed ProductLot.")
                if line.production_run.product_lot.cost_layer.qty_remaining < line.quantity:
                    raise ValueError("The factory ProductLot no longer has enough quantity.")
            elif line.route_kind == FulfillmentPlanLine.ROUTE_MERCHANT:
                if not hasattr(line, "merchant_demand") or line.merchant_demand.status != MerchantSupplyDemand.STATUS_RECEIVED:
                    raise ValueError("Merchant goods must be received before delivery.")
            routes.append((sale_line, plan, line))
    return routes


def is_unified_delivery_candidate(sale):
    """Whether a sale has enough phase-4 data to use unified delivery.

    Legacy sales without catalog variants/plans must remain on their historical
    completion and accounting workflow during staged rollout.
    """
    lines = list(sale.line_items.all())
    if not lines or any(not line.variant_id for line in lines):
        return False
    return all(
        FulfillmentPlan.objects.filter(sale_line=line).exists()
        for line in lines
    )


def _retire_legacy_sale_drafts(sale, user):
    legacy = JournalEntry.objects.filter(
        order_links__order=sale,
        entry_type_ref_id="sale",
    ).exclude(status_ref_id=JournalEntry.STATUS_VOID)
    for journal in legacy:
        if not FinancialEvent.objects.filter(journal=journal).exists():
            if journal.status == JournalEntry.STATUS_POSTED:
                DocumentIssuanceService().issue_correction(
                    journal, user=user, reason="Replaced by actual delivery recognition"
                )
            else:
                DocumentIssuanceService().retire_draft(
                    journal, user=user, reason="Replaced by posted delivery revenue event"
                )


def _issue_delivery_events(delivery, user):
    sale = delivery.sale
    invoice = sale.invoice_number or sale.pk
    description = f"تحویل و فروش فاکتور {invoice}"
    _retire_legacy_sale_drafts(sale, user)
    final_amount = _money(sale.final_amount)
    vat = _money(sale.vat_amount)
    revenue = final_amount - vat
    paid = min(_money(sale.paid_amount), final_amount)
    outstanding = final_amount - paid
    sale_lines = []
    if outstanding:
        sale_lines.append({
            "account": get_account(ACCOUNT_SLUGS.RECEIVABLES, ledger=LEGAL_LEDGER),
            "debit": outstanding, "credit": 0, "description": description,
        })
    if paid:
        sale_lines.append({
            "account": payment_account_for_sale(sale, ledger=LEGAL_LEDGER),
            "debit": paid, "credit": 0, "description": description,
        })
    sale_lines.append({
        "account": get_account(ACCOUNT_SLUGS.PRODUCT_SALES, ledger=LEGAL_LEDGER),
        "debit": 0, "credit": revenue, "description": description,
    })
    if vat:
        sale_lines.append({
            "account": get_account(ACCOUNT_SLUGS.VAT_PAYABLE, ledger=LEGAL_LEDGER),
            "debit": 0, "credit": vat, "description": description,
        })
    sale_event, _ = register_event(
        source_module="sales", source_type="DeliveryDocument", source=delivery,
        event_type="sale_recognized",
        payload={"sale_uuid": str(sale.uuid), "amount": str(final_amount), "vat": str(vat)},
        occurred_at=delivery.posted_at,
    )
    issue_event_draft(
        sale_event, lines=sale_lines, entry_type="sale", description=description,
        entry_date=delivery.posted_at, user=user, sale=sale, branch=sale.branch,
        ledger=LEGAL_LEDGER,
    )
    cogs = _money(delivery.total_actual_cogs)
    cogs_event, _ = register_event(
        source_module="sales", source_type="DeliveryDocument", source=delivery,
        event_type="actual_cogs_recognized",
        payload={"sale_uuid": str(sale.uuid), "actual_cogs": str(cogs)},
        occurred_at=delivery.posted_at,
    )
    issue_event_draft(
        cogs_event,
        lines=[
            {"account": get_account(ACCOUNT_SLUGS.COGS, ledger=LEGAL_LEDGER),
             "debit": cogs, "credit": 0, "description": description},
            {"account": get_account(ACCOUNT_SLUGS.FINISHED_GOODS_INVENTORY, ledger=LEGAL_LEDGER),
             "debit": 0, "credit": cogs, "description": description},
        ],
        entry_type="sale", description=f"بهای تمام‌شده واقعی فاکتور {invoice}",
        entry_date=delivery.posted_at, user=user, sale=sale, branch=sale.branch,
        ledger=LEGAL_LEDGER,
    )
    return sale_event, cogs_event


@transaction.atomic
def deliver_sale(sale, *, user=None, idempotency_key=None):
    """Deliver a complete sale once. Partial delivery is deliberately prohibited."""
    require_feature(UNIFIED_DELIVERY)
    locked = Sale.objects.select_for_update().select_related("branch", "customer").get(pk=sale.pk)
    existing = DeliveryDocument.objects.filter(sale=locked).first()
    if existing:
        return existing
    key = (idempotency_key or f"delivery:{locked.uuid}").strip()
    by_key = DeliveryDocument.objects.filter(idempotency_key=key).first()
    if by_key:
        if by_key.sale_id != locked.pk:
            raise ValueError("Delivery idempotency key belongs to another sale.")
        return by_key
    if locked.order_status == Sale.ORDER_STATUS_CANCELLED:
        raise ValueError("A cancelled sale cannot be delivered.")
    routes = _validate_ready(locked)
    delivery = DeliveryDocument.objects.create(
        idempotency_key=key, sale=locked, posted_by=_actor(user)
    )
    total_cogs = Decimal("0")
    for sale_line, plan, line in routes:
        location = _route_location(line)
        kwargs = {}
        product_lot = None
        if line.route_kind in {FulfillmentPlanLine.ROUTE_BRANCH, FulfillmentPlanLine.ROUTE_WAREHOUSE}:
            kwargs["reservation"] = line.reservation
        elif line.route_kind == FulfillmentPlanLine.ROUTE_FACTORY:
            product_lot = line.production_run.product_lot
            kwargs.update(
                override_layers=[{"layer_id": product_lot.cost_layer_id, "quantity": line.quantity}],
                override_reason="Required factory ProductLot for its fulfillment route",
                system_override=True,
            )
        result = consume_stock(
            sale_line.variant, line.quantity, location=location, user=_actor(user),
            reason="sale_delivery", reference=f"delivery:{delivery.uuid}",
            sale=locked, order_line=sale_line, **kwargs,
        )
        DeliveryLine.objects.create(
            delivery=delivery, sale_line=sale_line, fulfillment_plan_line=line,
            quantity=line.quantity, total_actual_cost=result["total_cost"],
            consumption=result["consumption"], product_lot=product_lot,
        )
        total_cogs += result["total_cost"]
        line.status = FulfillmentPlanLine.STATUS_EXECUTED
        line.executed_at = timezone.now()
        line.save(update_fields=["status", "executed_at", "updated_at"])
        plan.status = FulfillmentPlan.STATUS_EXECUTED
        plan.updated_by = _actor(user)
        plan.save(update_fields=["status", "updated_by", "updated_at"])
    delivery.total_actual_cogs = _money(total_cogs)
    delivery.posted_at = timezone.now()
    sale_event, cogs_event = _issue_delivery_events(delivery, user)
    delivery.sale_event = sale_event
    delivery.cogs_event = cogs_event
    delivery.status = DeliveryDocument.STATUS_POSTED
    delivery.save(update_fields=[
        "total_actual_cogs", "posted_at", "sale_event", "cogs_event", "status"
    ])
    return delivery


def _return_cost(delivery_line, prior_returned, quantity):
    skip = _qty(prior_returned)
    remaining = _qty(quantity)
    picks = []
    cost = Decimal("0")
    for allocation in delivery_line.consumption.allocations.select_related("cost_layer").order_by("id"):
        available = _qty(allocation.quantity)
        if skip >= available:
            skip -= available
            continue
        available -= skip
        skip = Decimal("0")
        take = min(available, remaining)
        if take:
            line_cost = _money(take * Decimal(allocation.unit_cost))
            picks.append({
                "original_layer_uuid": str(allocation.cost_layer.uuid),
                "quantity": str(take),
                "unit_cost": str(allocation.unit_cost),
                "cost": str(line_cost),
            })
            cost += line_cost
            remaining -= take
        if remaining <= 0:
            break
    if remaining > 0:
        raise ValueError("Original delivery allocation is incomplete.")
    return _money(cost), picks


@transaction.atomic
def return_sale(delivery, lines, *, reason, user=None, idempotency_key=None):
    require_feature(UNIFIED_DELIVERY)
    if not (reason or "").strip():
        raise ValueError("A sales return requires a reason.")
    key = (idempotency_key or "").strip()
    if not key:
        raise ValueError("A return idempotency key is required.")
    existing = SalesReturn.objects.filter(idempotency_key=key).first()
    if existing:
        return existing
    locked = DeliveryDocument.objects.select_for_update().select_related("sale__branch").get(pk=delivery.pk)
    if locked.status != DeliveryDocument.STATUS_POSTED:
        raise ValueError("Only a posted delivery can be returned.")
    if not isinstance(lines, list) or not lines:
        raise ValueError("At least one return line is required.")
    document = SalesReturn.objects.create(
        idempotency_key=key, delivery=locked, reason=reason.strip(), posted_by=_actor(user)
    )
    revenue_total = vat_total = cogs_total = Decimal("0")
    sale = locked.sale
    sale_base = Decimal(sale.amount or 0)
    net_total = _money(Decimal(sale.final_amount or 0) - Decimal(sale.vat_amount or 0))
    for spec in lines:
        try:
            delivery_line = DeliveryLine.objects.select_for_update().select_related(
                "sale_line", "consumption__movement"
            ).get(pk=spec.get("delivery_line_id"), delivery=locked)
        except (DeliveryLine.DoesNotExist, TypeError, ValueError) as exc:
            raise ValueError("Return line does not belong to the original delivery.") from exc
        qty = _qty(spec.get("quantity"))
        returned = delivery_line.return_lines.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        if qty <= 0 or _qty(returned) + qty > _qty(delivery_line.quantity):
            raise ValueError("Return quantity exceeds delivered, unreturned quantity.")
        cost, allocation_snapshot = _return_cost(delivery_line, returned, qty)
        fraction = (
            (Decimal(delivery_line.sale_line.line_total or 0) / sale_base)
            * (qty / Decimal(delivery_line.sale_line.quantity))
            if sale_base > 0 else Decimal("0")
        )
        revenue = _money(net_total * fraction)
        vat = _money(Decimal(sale.vat_amount or 0) * fraction)
        movement = InventoryTransaction.objects.create(
            variant_id=delivery_line.sale_line.variant_id, quantity=qty,
            unit_cost=_money(cost / qty), reason="sales_return",
            reference=f"return:{document.uuid}", recorded_by=_actor(user),
            order_line=delivery_line.sale_line,
            **location_transaction_kwargs({
                "kind": delivery_line.consumption.movement.location_kind,
                "warehouse": delivery_line.consumption.movement.warehouse,
                "branch": delivery_line.consumption.movement.branch,
            }),
        )
        layer = InventoryCostLayer.objects.create(
            variant_id=delivery_line.sale_line.variant_id, source_transaction=movement,
            unit_cost=_money(cost / qty), original_qty=qty, qty_remaining=qty,
            metadata={
                "sales_return_uuid": str(document.uuid),
                "original_delivery_uuid": str(locked.uuid),
                "original_allocations": allocation_snapshot,
            },
            **location_transaction_kwargs({
                "kind": movement.location_kind,
                "warehouse": movement.warehouse,
                "branch": movement.branch,
            }),
        )
        SalesReturnLine.objects.create(
            sales_return=document, delivery_line=delivery_line, quantity=qty,
            revenue_amount=revenue, vat_amount=vat, actual_cost=cost,
            allocation_snapshot=allocation_snapshot,
            inventory_transaction=movement, return_cost_layer=layer,
        )
        revenue_total += revenue
        vat_total += vat
        cogs_total += cost
    document.revenue_amount = _money(revenue_total)
    document.vat_amount = _money(vat_total)
    document.total_actual_cogs = _money(cogs_total)
    document.posted_at = timezone.now()
    desc = f"برگشت فروش تحویل {locked.uuid}"
    revenue_event, _ = register_event(
        source_module="sales", source_type="SalesReturn", source=document,
        event_type="revenue_reversed",
        payload={
            "delivery_uuid": str(locked.uuid), "revenue": str(document.revenue_amount),
            "vat": str(document.vat_amount),
        },
    )
    revenue_journal = issue_event_draft(
        revenue_event,
        lines=[
            {"account": get_account(ACCOUNT_SLUGS.PRODUCT_SALES, ledger=LEGAL_LEDGER),
             "debit": document.revenue_amount, "credit": 0, "description": desc},
            *([{"account": get_account(ACCOUNT_SLUGS.VAT_PAYABLE, ledger=LEGAL_LEDGER),
                "debit": document.vat_amount, "credit": 0, "description": desc}]
              if document.vat_amount else []),
            {"account": get_account(ACCOUNT_SLUGS.RECEIVABLES, ledger=LEGAL_LEDGER),
             "debit": 0, "credit": document.revenue_amount + document.vat_amount,
             "description": desc},
        ],
        entry_type="refund", description=desc, user=user, sale=sale,
        branch=sale.branch, ledger=LEGAL_LEDGER,
    )
    cogs_event, _ = register_event(
        source_module="sales", source_type="SalesReturn", source=document,
        event_type="actual_cogs_reversed",
        payload={"delivery_uuid": str(locked.uuid), "actual_cogs": str(document.total_actual_cogs)},
    )
    cogs_journal = issue_event_draft(
        cogs_event,
        lines=[
            {"account": get_account(ACCOUNT_SLUGS.FINISHED_GOODS_INVENTORY, ledger=LEGAL_LEDGER),
             "debit": document.total_actual_cogs, "credit": 0, "description": desc},
            {"account": get_account(ACCOUNT_SLUGS.COGS, ledger=LEGAL_LEDGER),
             "debit": 0, "credit": document.total_actual_cogs, "description": desc},
        ],
        entry_type="refund", description=f"برگشت بهای تمام‌شده {locked.uuid}",
        user=user, sale=sale, branch=sale.branch, ledger=LEGAL_LEDGER,
    )
    JournalEntry.objects.filter(pk=revenue_journal.pk).update(corrects_id=locked.sale_event.journal_id)
    JournalEntry.objects.filter(pk=cogs_journal.pk).update(corrects_id=locked.cogs_event.journal_id)
    document.revenue_event = revenue_event
    document.cogs_event = cogs_event
    document.status = SalesReturn.STATUS_POSTED
    document.save(update_fields=[
        "revenue_amount", "vat_amount", "total_actual_cogs", "posted_at",
        "revenue_event", "cogs_event", "status",
    ])
    return document


def _route_trace(route):
    production_run = route.production_run if hasattr(route, "production_run") else None
    product_lot = (
        production_run.product_lot
        if production_run is not None and hasattr(production_run, "product_lot")
        else None
    )
    merchant = route.merchant_demand if hasattr(route, "merchant_demand") else None
    merchant_layer = (
        merchant.receipt_movement.cost_layers.order_by("id").first()
        if merchant is not None and merchant.receipt_movement_id else None
    )
    return {
        "uuid": str(route.uuid), "kind": route.route_kind,
        "quantity": str(route.quantity), "status": route.status,
        "reservation_uuid": str(route.reservation.uuid) if route.reservation_id else None,
        "production_run_uuid": str(production_run.uuid) if production_run else None,
        "product_lot_uuid": str(product_lot.uuid) if product_lot else None,
        "purchase_request_uuid": (
            str(route.shortage_request.uuid) if route.shortage_request_id else None
        ),
        "merchant_demand_uuid": str(merchant.uuid) if merchant else None,
        "merchant_status": merchant.status if merchant else None,
        "merchant_receipt_movement_uuid": (
            str(merchant.receipt_movement.uuid)
            if merchant is not None and merchant.receipt_movement_id else None
        ),
        "merchant_lot_uuid": str(merchant_layer.uuid) if merchant_layer else None,
    }


def delivery_trace(sale):
    delivery = DeliveryDocument.objects.filter(sale=sale).select_related(
        "sale_event__journal", "cogs_event__journal"
    ).first()
    plans = []
    for sale_line in sale.line_items.all():
        plan = FulfillmentPlan.objects.filter(sale_line=sale_line).first()
        if plan:
            plans.append({
                "sale_line_id": sale_line.pk,
                "status": plan.status,
                "routes": [_route_trace(route) for route in plan.lines.all()],
            })
    payload = {"sale_uuid": str(sale.uuid), "plans": plans, "delivery": None, "payments": []}
    if delivery:
        payload["delivery"] = {
            "uuid": str(delivery.uuid), "status": delivery.status,
            "total_actual_cogs": str(delivery.total_actual_cogs),
            "sale_event_id": delivery.sale_event_id, "cogs_event_id": delivery.cogs_event_id,
            "lines": [{
                "id": line.pk, "sale_line_id": line.sale_line_id,
                "route_uuid": str(line.fulfillment_plan_line.uuid),
                "quantity": str(line.quantity), "actual_cost": str(line.total_actual_cost),
                "consumption_uuid": str(line.consumption.uuid),
                "product_lot_uuid": str(line.product_lot.uuid) if line.product_lot_id else None,
                "allocations": [{
                    "lot_uuid": str(allocation.cost_layer.uuid),
                    "quantity": str(allocation.quantity), "unit_cost": str(allocation.unit_cost),
                } for allocation in line.consumption.allocations.select_related("cost_layer").all()],
            } for line in delivery.lines.select_related(
                "sale_line", "fulfillment_plan_line", "consumption", "product_lot"
            ).all()],
            "returns": [{
                "uuid": str(item.uuid), "status": item.status,
                "revenue_amount": str(item.revenue_amount),
                "vat_amount": str(item.vat_amount),
                "actual_cogs": str(item.total_actual_cogs),
                "revenue_event_id": item.revenue_event_id, "cogs_event_id": item.cogs_event_id,
            } for item in delivery.returns.all()],
        }
    payload["payments"] = [{
        "id": event.pk, "source_key": event.source_key, "status": event.status,
        "amount": event.payload.get("amount"), "journal_id": event.journal_id,
    } for event in FinancialEvent.objects.filter(
        source_module="treasury", event_type__in=["payment_received", "check_registered", "check_cleared"],
        payload__sale_uuid=str(sale.uuid),
    )]
    return payload
