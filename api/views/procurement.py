"""Protected API for unified procurement and automatic shortage supply."""

from decimal import Decimal

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import (
    APPROVE_PROCUREMENT,
    MANAGE_PROCUREMENT,
    VIEW_PROCUREMENT,
    has_permission,
)
from backend.models import (
    GoodsReceipt,
    MaterialSupplier,
    PurchaseOrder,
    PurchaseRequest,
)
from logic.procurement import (
    approve_goods_receipt,
    approve_request,
    generate_shortage_requests,
    receive_order,
    trace_consumption,
)
from logic.stock_locations import parse_location


def _number(value):
    value = Decimal(value or 0)
    return int(value) if value == value.to_integral_value() else float(value)


def _request_dict(row):
    return {
        "id": row.id,
        "uuid": str(row.uuid),
        "status": row.status,
        "destination_kind": row.destination_kind,
        "warehouse_id": row.warehouse_id,
        "branch": row.branch_id,
        "note": row.note,
        "created_at": row.created_at.isoformat(),
        "lines": [
            {
                "id": line.id,
                "material_id": line.material_id,
                "material": line.material.name,
                "quantity": _number(line.quantity),
                "source_type": line.source_type,
                "source_key": line.source_key,
                "sale_id": line.sale_id,
                "order_line_id": line.order_line_id,
                "production_order_id": line.production_order_id,
            }
            for line in row.lines.all()
        ],
    }


def _order_dict(row):
    return {
        "id": row.id,
        "uuid": str(row.uuid),
        "request_uuid": str(row.request.uuid),
        "supplier_id": row.supplier_id,
        "supplier": row.supplier.name,
        "status": row.status,
        "expected_at": row.expected_at.isoformat() if row.expected_at else None,
        "destination_kind": row.destination_kind,
        "warehouse_id": row.warehouse_id,
        "branch": row.branch_id,
        "lines": [
            {
                "id": line.id,
                "material_id": line.material_id,
                "material": line.material.name,
                "ordered_quantity": _number(line.ordered_quantity),
                "received_quantity": _number(line.received_quantity),
                "remaining_quantity": _number(line.ordered_quantity - line.received_quantity),
                "unit_price": _number(line.unit_price),
            }
            for line in row.lines.all()
        ],
    }


def _receipt_dict(row):
    return {
        "id": row.id,
        "uuid": str(row.uuid),
        "order_uuid": str(row.order.uuid),
        "status": row.status,
        "receipt_number": row.receipt_number,
        "invoice_number": row.invoice_number,
        "is_final": row.is_final,
        "purchase_invoice_id": row.purchase_invoice_id,
        "journal_id": row.accounting_event.journal_id if row.accounting_event_id else None,
        "has_attachment": row.attachments.exists(),
        "created_at": row.created_at.isoformat(),
        "lines": [
            {
                "id": line.id,
                "order_line_id": line.order_line_id,
                "material_id": line.material_id,
                "material": line.material.name,
                "expected_quantity": _number(line.expected_quantity),
                "received_quantity": _number(line.received_quantity),
                "ordered_unit_price": _number(line.ordered_unit_price),
                "received_unit_price": _number(line.received_unit_price),
                "inventory_move_id": line.inventory_move_id,
                "adjustments": [
                    {
                        "uuid": str(item.uuid),
                        "kind": item.kind,
                        "expected_value": _number(item.expected_value),
                        "actual_value": _number(item.actual_value),
                        "reason": item.reason,
                    }
                    for item in line.adjustments.all()
                ],
            }
            for line in row.lines.all()
        ],
    }


@api_view("GET", permission=VIEW_PROCUREMENT)
def purchase_requests(request):
    rows = PurchaseRequest.objects.select_related("warehouse", "branch").prefetch_related(
        "lines__material"
    )
    return success({"results": [_request_dict(row) for row in rows]})


@api_view("POST", permission=MANAGE_PROCUREMENT)
def shortage_generate(request):
    data = parse_json(request)
    try:
        result = generate_shortage_requests(
            data.get("requirements"),
            location=parse_location(data.get("destination") or data, required=True),
            user=request.user,
            note=data.get("note") or "",
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(
        {
            "request": _request_dict(result["request"]) if result["request"] else None,
            "created_line_ids": [row.id for row in result["created_lines"]],
            "existing_line_ids": [row.id for row in result["existing_lines"]],
        },
        status=201 if result["request"] else 200,
    )


@api_view("POST", permission=APPROVE_PROCUREMENT)
def purchase_request_approve(request, request_uuid):
    row = PurchaseRequest.objects.filter(uuid=request_uuid).first()
    if row is None:
        return fail("Purchase request not found", status=404)
    data = parse_json(request)
    supplier = MaterialSupplier.objects.filter(pk=data.get("supplier_id")).first()
    if supplier is None:
        return fail("Supplier not found", status=400)
    try:
        order = approve_request(
            row,
            supplier=supplier,
            prices=data.get("prices"),
            expected_at=data.get("expected_at"),
            user=request.user,
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    order = PurchaseOrder.objects.select_related("request", "supplier").prefetch_related(
        "lines__material"
    ).get(pk=order.pk)
    return success(_order_dict(order))


@api_view("GET", permission=VIEW_PROCUREMENT)
def purchase_orders(request):
    rows = PurchaseOrder.objects.select_related("request", "supplier").prefetch_related(
        "lines__material"
    )
    return success({"results": [_order_dict(row) for row in rows]})


@api_view("POST", permission=MANAGE_PROCUREMENT)
def purchase_order_receive(request, order_uuid):
    order = PurchaseOrder.objects.filter(uuid=order_uuid).first()
    if order is None:
        return fail("Purchase order not found", status=404)
    data = parse_json(request)
    try:
        receipt = receive_order(
            order,
            data.get("lines"),
            receipt_number=data.get("receipt_number"),
            invoice_number=data.get("invoice_number"),
            user=request.user,
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    receipt = GoodsReceipt.objects.select_related("order").prefetch_related(
        "lines__material", "lines__adjustments", "attachments"
    ).get(pk=receipt.pk)
    return success(_receipt_dict(receipt), status=201)


@api_view("GET", permission=VIEW_PROCUREMENT)
def goods_receipts(request):
    rows = GoodsReceipt.objects.select_related("order", "accounting_event").prefetch_related(
        "lines__material", "lines__adjustments", "attachments"
    )
    return success({"results": [_receipt_dict(row) for row in rows]})


@api_view("POST", permission=APPROVE_PROCUREMENT)
def goods_receipt_approve(request, receipt_uuid):
    row = GoodsReceipt.objects.filter(uuid=receipt_uuid).first()
    if row is None:
        return fail("Goods receipt not found", status=404)
    try:
        approved = approve_goods_receipt(row, user=request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    approved = GoodsReceipt.objects.select_related(
        "order", "accounting_event"
    ).prefetch_related("lines__material", "lines__adjustments", "attachments").get(pk=approved.pk)
    return success(_receipt_dict(approved))


@api_view("GET", permission=VIEW_PROCUREMENT)
def procurement_trace(request, consumption_uuid):
    return success({"results": trace_consumption(consumption_uuid)})
