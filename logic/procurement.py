"""Unified shortage, purchasing, receipt, inventory, and AP workflow."""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from backend.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    InventoryAllocation,
    Material,
    ProcurementAdjustment,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
)
from logic.accounting_events import issue_through_gateway
from logic.feature_flags import PROCUREMENT, require_feature
from logic.inventory_costing import availability, receive_stock
from logic.ledger import LEGAL_LEDGER
from logic.stock_locations import location_transaction_kwargs


def _qty(value):
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError("Quantity is invalid.") from exc
    return result.quantize(Decimal("0.001"))


def _money(value):
    try:
        result = Decimal(str(value or 0))
    except Exception as exc:
        raise ValueError("Price is invalid.") from exc
    return result.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _actor(user):
    return user if getattr(user, "is_authenticated", False) else None


def _location_from_model(row):
    return {
        "kind": row.destination_kind,
        "warehouse": row.warehouse,
        "warehouse_id": row.warehouse_id,
        "branch": row.branch,
        "branch_id": row.branch_id,
    }


def _location_fields(location):
    values = {
        "destination_kind": location["kind"],
        "warehouse": None,
        "branch": None,
    }
    if location["kind"] == "warehouse":
        values["warehouse"] = location.get("warehouse")
    else:
        values["branch"] = location.get("branch")
    return values


def _source_objects(raw):
    from backend.models import ProductionOrder, Sale, SaleLineItem

    result = {}
    for key, model in (
        ("sale", Sale),
        ("order_line", SaleLineItem),
        ("production_order", ProductionOrder),
    ):
        pk = raw.get(f"{key}_id")
        if pk:
            value = model.objects.filter(pk=pk).first()
            if value is None:
                raise ValueError(f"{key} source was not found.")
            result[key] = value
    if result.get("sale") and result.get("order_line") and result["order_line"].sale_id != result["sale"].pk:
        raise ValueError("Order line does not belong to the supplied sale.")
    return result


def _incoming(material, location):
    rows = PurchaseOrderLine.objects.filter(
        material=material,
        order__status__in=[PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIAL],
        order__destination_kind=location["kind"],
    )
    if location["kind"] == "warehouse":
        rows = rows.filter(order__warehouse_id=location["warehouse_id"])
    else:
        rows = rows.filter(order__branch_id=location["branch_id"])
    totals = rows.aggregate(ordered=Sum("ordered_quantity"), received=Sum("received_quantity"))
    return _qty(totals["ordered"] or 0) - _qty(totals["received"] or 0)


@transaction.atomic
def generate_shortage_requests(requirements, *, location, user=None, note=""):
    """Net demand against available stock and approved incoming POs.

    Idempotency is the unique demand source/type/material tuple. Every demand
    remains a separate request line even when lines are grouped into one request.
    """
    require_feature(PROCUREMENT)
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("At least one material requirement is required.")
    pools = {}
    created_specs = []
    existing = []
    seen = set()
    for raw in requirements:
        material_id = raw.get("material_id")
        material = Material.objects.select_for_update().filter(
            pk=material_id, is_deleted=False, is_active=True
        ).first()
        if material is None:
            raise ValueError("Material was not found; purchases must use the existing material master.")
        required = _qty(raw.get("quantity"))
        if required <= 0:
            raise ValueError("Required quantity must be greater than zero.")
        source_type = (raw.get("source_type") or "").strip().lower()
        source_key = str(raw.get("source_key") or "").strip()
        if not source_type or not source_key:
            raise ValueError("Every requirement needs source_type and source_key.")
        identity = (source_type, source_key, material.pk)
        if identity in seen:
            raise ValueError("A demand source/material cannot appear twice.")
        seen.add(identity)
        prior = PurchaseRequestLine.objects.filter(
            source_type=source_type, source_key=source_key, material=material
        ).select_related("request").first()
        if prior:
            existing.append(prior)
            continue
        if material.pk not in pools:
            pools[material.pk] = max(
                _qty(availability(material, location=location)["available"]), Decimal("0")
            ) + max(_incoming(material, location), Decimal("0"))
        covered = min(pools[material.pk], required)
        pools[material.pk] -= covered
        shortage = required - covered
        if shortage > 0:
            created_specs.append(
                {
                    "material": material,
                    "quantity": shortage,
                    "source_type": source_type,
                    "source_key": source_key,
                    **_source_objects(raw),
                }
            )
    request = None
    created = []
    if created_specs:
        request = PurchaseRequest.objects.create(
            **_location_fields(location),
            note=(note or "").strip()[:500],
            requested_by=_actor(user),
        )
        for spec in created_specs:
            created.append(PurchaseRequestLine.objects.create(request=request, **spec))
    return {"request": request, "created_lines": created, "existing_lines": existing}


@transaction.atomic
def approve_request(request, *, supplier, prices=None, expected_at=None, user=None):
    require_feature(PROCUREMENT)
    locked = PurchaseRequest.objects.select_for_update().prefetch_related("lines").get(pk=request.pk)
    if hasattr(locked, "purchase_order"):
        return locked.purchase_order
    if locked.status not in {PurchaseRequest.STATUS_DRAFT, PurchaseRequest.STATUS_APPROVED}:
        raise ValueError("Purchase request cannot be approved in its current status.")
    if not supplier.is_active:
        raise ValueError("Supplier is inactive.")
    prices = prices or {}
    order = PurchaseOrder.objects.create(
        request=locked,
        supplier=supplier,
        expected_at=expected_at or None,
        approved_by=_actor(user),
        **_location_fields(_location_from_model(locked)),
    )
    for request_line in locked.lines.all():
        price = _money(prices.get(str(request_line.pk), prices.get(request_line.pk, 0)))
        PurchaseOrderLine.objects.create(
            order=order,
            request_line=request_line,
            material=request_line.material,
            ordered_quantity=request_line.quantity,
            unit_price=price,
        )
    locked.status = PurchaseRequest.STATUS_ORDERED
    locked.approved_by = _actor(user)
    locked.approved_at = timezone.now()
    locked.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return order


@transaction.atomic
def receive_order(order, lines, *, receipt_number, invoice_number, user=None):
    require_feature(PROCUREMENT)
    locked = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if locked.status not in {PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIAL}:
        raise ValueError("Only an open approved order can be received.")
    receipt_number = (receipt_number or "").strip()
    invoice_number = (invoice_number or "").strip()
    if not receipt_number or not invoice_number:
        raise ValueError("Receipt number and invoice number are required.")
    if not isinstance(lines, list) or not lines:
        raise ValueError("At least one receipt line is required.")
    order_lines = {
        row.pk: row
        for row in PurchaseOrderLine.objects.select_for_update().filter(order=locked)
    }
    receipt = GoodsReceipt.objects.create(
        order=locked,
        receipt_number=receipt_number[:80],
        invoice_number=invoice_number[:80],
        created_by=_actor(user),
    )
    proposed = {}
    for raw in lines:
        try:
            line_id = int(raw.get("order_line_id"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Order line is invalid.") from exc
        if line_id in proposed:
            raise ValueError("An order line cannot appear twice in one receipt.")
        order_line = order_lines.get(line_id)
        if order_line is None:
            raise ValueError("Receipt line does not belong to this purchase order.")
        received = _qty(raw.get("received_quantity"))
        expected = _qty(raw.get("expected_quantity", received))
        price = _money(raw.get("unit_price", order_line.unit_price))
        if received <= 0 or expected <= 0:
            raise ValueError("Receipt quantities must be greater than zero.")
        pending = GoodsReceiptLine.objects.filter(
            order_line=order_line, receipt__status=GoodsReceipt.STATUS_DRAFT
        ).exclude(receipt=receipt).aggregate(total=Sum("received_quantity"))["total"] or 0
        remaining = _qty(order_line.ordered_quantity) - _qty(order_line.received_quantity) - _qty(pending)
        if received > remaining:
            raise ValueError("Received quantity exceeds the strict remaining order quantity.")
        qty_reason = (raw.get("quantity_variance_reason") or "").strip()
        price_reason = (raw.get("price_variance_reason") or "").strip()
        if expected != received and not qty_reason:
            raise ValueError("Quantity difference requires an explicit adjustment reason.")
        if price != _money(order_line.unit_price) and not price_reason:
            raise ValueError("Price difference requires an explicit adjustment reason.")
        receipt_line = GoodsReceiptLine.objects.create(
            receipt=receipt,
            order_line=order_line,
            material=order_line.material,
            expected_quantity=expected,
            received_quantity=received,
            ordered_unit_price=order_line.unit_price,
            received_unit_price=price,
        )
        if expected != received:
            ProcurementAdjustment.objects.create(
                receipt_line=receipt_line,
                kind=ProcurementAdjustment.KIND_QUANTITY,
                expected_value=expected,
                actual_value=received,
                reason=qty_reason[:500],
                created_by=_actor(user),
            )
        if price != _money(order_line.unit_price):
            ProcurementAdjustment.objects.create(
                receipt_line=receipt_line,
                kind=ProcurementAdjustment.KIND_PRICE,
                expected_value=order_line.unit_price,
                actual_value=price,
                reason=price_reason[:500],
                created_by=_actor(user),
            )
        proposed[line_id] = received
    all_complete = True
    for line_id, order_line in order_lines.items():
        drafts = GoodsReceiptLine.objects.filter(
            order_line=order_line, receipt__status=GoodsReceipt.STATUS_DRAFT
        ).aggregate(total=Sum("received_quantity"))["total"] or 0
        if _qty(order_line.received_quantity) + _qty(drafts) != _qty(order_line.ordered_quantity):
            all_complete = False
            break
    receipt.is_final = all_complete
    receipt.save(update_fields=["is_final"])
    return receipt


@transaction.atomic
def approve_goods_receipt(receipt, *, user=None):
    require_feature(PROCUREMENT)
    locked = GoodsReceipt.objects.select_for_update().select_related(
        "order__supplier__account", "order__warehouse", "order__branch"
    ).get(pk=receipt.pk)
    if locked.status == GoodsReceipt.STATUS_APPROVED:
        return locked
    if not locked.attachments.exists():
        raise ValueError("An invoice image or document is required before receipt approval.")
    order = PurchaseOrder.objects.select_for_update().get(pk=locked.order_id)
    lines = list(
        GoodsReceiptLine.objects.select_for_update().filter(receipt=locked).select_related(
            "material", "order_line"
        )
    )
    total = sum(
        (_qty(row.received_quantity) * _money(row.received_unit_price) for row in lines),
        Decimal("0"),
    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if total <= 0:
        raise ValueError("Receipt value must be greater than zero.")
    if PurchaseInvoice.objects.filter(
        supplier=order.supplier, invoice_number=locked.invoice_number
    ).exists():
        raise ValueError("This supplier invoice number has already been approved.")
    event, journal, _created = issue_through_gateway(
        source_module="procurement",
        source_type="goods_receipt",
        source=locked,
        source_uuid=locked.uuid,
        event_type="goods_receipt_approved",
        rule_name="material_receipt",
        amounts={"value": total},
        accounts={"accounts_payable": order.supplier.account},
        entry_type="adjustment",
        description=f"رسید خرید {locked.receipt_number} — {order.supplier.name}",
        payload={
            "receipt_uuid": str(locked.uuid),
            "order_uuid": str(order.uuid),
            "invoice_number": locked.invoice_number,
            "value": str(total),
            "lines": [
                {
                    "material_id": row.material_id,
                    "quantity": str(row.received_quantity),
                    "unit_price": str(row.received_unit_price),
                }
                for row in lines
            ],
        },
        ledger=LEGAL_LEDGER,
        branch=order.branch,
        warehouse=order.warehouse,
        user=_actor(user),
    )
    event.refresh_from_db()
    today = date.today()
    invoice = PurchaseInvoice.objects.create(
        supplier=order.supplier,
        invoice_number=locked.invoice_number,
        warehouse_receipt=locked.receipt_number,
        invoice_date=today,
        due_date=today + timedelta(days=order.supplier.credit_days),
        goods_net=total,
        inventory_amount=total,
        payable_amount=total,
        vat_rate=0,
        vat_amount=0,
        journal=journal,
        description=f"Generated from procurement receipt {locked.uuid}",
        created_by=_actor(user),
    )
    location = _location_from_model(order)
    for index, row in enumerate(lines, 1):
        order_line = PurchaseOrderLine.objects.select_for_update().get(pk=row.order_line_id)
        remaining = _qty(order_line.ordered_quantity) - _qty(order_line.received_quantity)
        if _qty(row.received_quantity) > remaining:
            raise ValueError("Received quantity exceeds remaining quantity; approval rolled back.")
        move = receive_stock(
            row.material,
            row.received_quantity,
            row.received_unit_price,
            reason="procurement_receipt",
            reference=f"goods-receipt:{locked.uuid}",
            recorded_by=_actor(user),
            location=location,
            supplier=order.supplier,
            purchase_invoice=invoice,
            invoice_number=locked.invoice_number,
            metadata={
                "goods_receipt_uuid": str(locked.uuid),
                "goods_receipt_line_id": row.pk,
                "purchase_order_uuid": str(order.uuid),
            },
        )
        row.inventory_move = move
        row.save(update_fields=["inventory_move"])
        PurchaseInvoiceLine.objects.create(
            invoice=invoice,
            material=row.material,
            quantity=row.received_quantity,
            unit_price=row.received_unit_price,
            goods_net=_qty(row.received_quantity) * _money(row.received_unit_price),
            inventory_amount=_qty(row.received_quantity) * _money(row.received_unit_price),
            unit_cost=row.received_unit_price,
            inventory_move=move,
            line_number=index,
        )
        order_line.received_quantity = _qty(order_line.received_quantity) + _qty(row.received_quantity)
        order_line.save(update_fields=["received_quantity"])
    complete = not PurchaseOrderLine.objects.filter(order=order).exclude(
        received_quantity=F("ordered_quantity")
    ).exists()
    order.status = PurchaseOrder.STATUS_RECEIVED if complete else PurchaseOrder.STATUS_PARTIAL
    order.save(update_fields=["status", "updated_at"])
    locked.status = GoodsReceipt.STATUS_APPROVED
    locked.purchase_invoice = invoice
    locked.accounting_event = event
    locked.approved_by = _actor(user)
    locked.approved_at = timezone.now()
    locked.save(update_fields=[
        "status", "purchase_invoice", "accounting_event", "approved_by", "approved_at"
    ])
    return locked


def trace_consumption(consumption_uuid):
    allocations = InventoryAllocation.objects.filter(
        consumption__uuid=consumption_uuid
    ).select_related(
        "cost_layer__purchase_invoice__goods_receipt__order__supplier",
        "cost_layer__source_transaction",
    )
    return [
        {
            "lot_uuid": str(row.cost_layer.uuid),
            "quantity": row.quantity,
            "unit_cost": row.unit_cost,
            "inventory_transaction_uuid": (
                str(row.cost_layer.source_transaction.uuid)
                if row.cost_layer.source_transaction_id else None
            ),
            "purchase_invoice_id": row.cost_layer.purchase_invoice_id,
            "goods_receipt_uuid": (
                str(row.cost_layer.purchase_invoice.goods_receipt.uuid)
                if row.cost_layer.purchase_invoice_id
                and hasattr(row.cost_layer.purchase_invoice, "goods_receipt")
                else None
            ),
        }
        for row in allocations
    ]
