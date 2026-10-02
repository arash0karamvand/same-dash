"""Inventory availability, reservations, lot traceability, and attachments."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import (
    CREATE_ACCOUNTING,
    MANAGE_MATERIALS,
    MANAGE_PRODUCTS,
    MANAGE_PROCUREMENT,
    VIEW_ACCOUNTING,
    VIEW_MATERIALS,
    VIEW_PRODUCTS,
    VIEW_PROCUREMENT,
    can_view_costs,
    has_permission,
)
from backend.models import (
    DocumentAttachment,
    InventoryConsumption,
    InventoryCostLayer,
    InventoryReservation,
    Material,
    ProductVariant,
    ProductionOrder,
    Sale,
    SaleLineItem,
)
from logic.document_attachments import (
    attachment_to_dict,
    create_attachment,
    resolve_source,
)
from logic.inventory_costing import (
    availability,
    consume_stock,
    release_reservation,
    reserve_stock,
)
from logic.stock_locations import parse_location


def _number(value):
    value = Decimal(value or 0)
    return int(value) if value == value.to_integral_value() else float(value)


def _can_view(user):
    return (
        has_permission(user, VIEW_MATERIALS)
        or has_permission(user, VIEW_PRODUCTS)
        or has_permission(user, VIEW_ACCOUNTING)
        or has_permission(user, VIEW_PROCUREMENT)
    )


def _can_manage(user):
    return (
        has_permission(user, MANAGE_MATERIALS)
        or has_permission(user, MANAGE_PRODUCTS)
        or has_permission(user, MANAGE_PROCUREMENT)
    )


def _item(material_id=None, variant_id=None):
    if bool(material_id) == bool(variant_id):
        raise ValueError("Exactly one of material_id or variant_id is required.")
    if material_id:
        item = Material.objects.filter(pk=material_id, is_deleted=False).first()
    else:
        item = ProductVariant.objects.filter(pk=variant_id, is_active=True).first()
    if item is None:
        raise ValueError("Inventory item was not found.")
    return item


def _request_location(data, *, required=False):
    raw = data.get("location") if isinstance(data.get("location"), dict) else data
    has_location = any(
        raw.get(key) not in (None, "") for key in ("kind", "location_kind", "warehouse_id", "branch")
    )
    return parse_location(raw, required=required) if required or has_location else None


def _related(model, pk, label):
    if not pk:
        return None
    obj = model.objects.filter(pk=pk).first()
    if obj is None:
        raise ValueError(f"{label} was not found.")
    return obj


@api_view("GET")
def inventory_availability(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    try:
        item = _item(request.GET.get("material_id"), request.GET.get("variant_id"))
        location = _request_location(request.GET, required=False)
        result = availability(item, location=location)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success({key: _number(value) for key, value in result.items()})


@api_view("GET")
def inventory_lots(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    try:
        item = _item(request.GET.get("material_id"), request.GET.get("variant_id"))
    except ValueError as exc:
        return fail(str(exc), status=400)
    filters = {"material": item} if isinstance(item, Material) else {"variant": item}
    rows = InventoryCostLayer.objects.filter(**filters).select_related(
        "supplier", "purchase_invoice", "warehouse", "branch", "source_transaction"
    )
    payload = {
            "results": [
                {
                    "id": row.id,
                    "uuid": str(row.uuid),
                    "original_qty": _number(row.original_qty),
                    "remaining_qty": _number(row.qty_remaining),
                    "unit_cost": _number(row.unit_cost),
                    "supplier_id": row.supplier_id,
                    "supplier": row.supplier.name if row.supplier_id else None,
                    "purchase_invoice_id": row.purchase_invoice_id,
                    "invoice_number": row.invoice_number,
                    "source_transaction_id": row.source_transaction_id,
                    "location_kind": row.location_kind,
                    "warehouse_id": row.warehouse_id,
                    "branch": row.branch_id,
                    "metadata": row.metadata,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]
        }
    if not can_view_costs(request.user):
        from logic.materials import mask_cost_fields
        payload = mask_cost_fields(payload)
    return success(payload)


@api_view("GET")
def inventory_consumptions(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    try:
        item = _item(request.GET.get("material_id"), request.GET.get("variant_id"))
    except ValueError as exc:
        return fail(str(exc), status=400)
    filters = {"material": item} if isinstance(item, Material) else {"variant": item}
    rows = InventoryConsumption.objects.filter(**filters).select_related(
        "recorded_by", "overridden_by", "movement", "reservation"
    ).prefetch_related("allocations__cost_layer")
    payload = {
            "results": [
                {
                    "id": row.id,
                    "uuid": str(row.uuid),
                    "quantity": _number(row.quantity),
                    "total_cost": _number(row.total_cost),
                    "unit_cost": _number(Decimal(row.total_cost) / Decimal(row.quantity)),
                    "movement_id": row.movement_id,
                    "reservation_uuid": str(row.reservation.uuid) if row.reservation_id else None,
                    "reference": row.reference,
                    "override_reason": row.override_reason,
                    "overridden_by": row.overridden_by_id,
                    "recorded_by": row.recorded_by_id,
                    "created_at": row.created_at.isoformat(),
                    "allocations": [
                        {
                            "layer_id": allocation.cost_layer_id,
                            "layer_uuid": str(allocation.cost_layer.uuid),
                            "quantity": _number(allocation.quantity),
                            "unit_cost": _number(allocation.unit_cost),
                        }
                        for allocation in row.allocations.all()
                    ],
                }
                for row in rows
            ]
        }
    if not can_view_costs(request.user):
        from logic.materials import mask_cost_fields
        payload = mask_cost_fields(payload)
    return success(payload)


@api_view("POST")
def reservation_create(request):
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    data = parse_json(request)
    try:
        item = _item(data.get("material_id"), data.get("variant_id"))
        reservation = reserve_stock(
            item,
            data.get("quantity"),
            location=_request_location(data, required=True),
            user=request.user,
            sale=_related(Sale, data.get("sale_id"), "Sale"),
            order_line=_related(SaleLineItem, data.get("order_line_id"), "Order line"),
            production_order=_related(
                ProductionOrder, data.get("production_order_id"), "Production order"
            ),
            reference=data.get("reference") or "",
            reason=data.get("reason") or "",
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(
        {
            "id": reservation.id,
            "uuid": str(reservation.uuid),
            "quantity": _number(reservation.quantity),
            "status": reservation.status,
        },
        status=201,
    )


@api_view("POST")
def reservation_release(request, reservation_uuid):
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    reservation = InventoryReservation.objects.filter(uuid=reservation_uuid).first()
    if reservation is None:
        return fail("Reservation not found", status=404)
    try:
        reservation = release_reservation(
            reservation,
            user=request.user,
            reason=parse_json(request).get("reason") or "",
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success({"uuid": str(reservation.uuid), "status": reservation.status})


@api_view("POST")
def inventory_consume(request):
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    data = parse_json(request)
    try:
        item = _item(data.get("material_id"), data.get("variant_id"))
        reservation = None
        if data.get("reservation_uuid"):
            reservation = InventoryReservation.objects.filter(uuid=data["reservation_uuid"]).first()
            if reservation is None:
                raise ValueError("Reservation not found.")
        result = consume_stock(
            item,
            data.get("quantity"),
            location=_request_location(data, required=False),
            reservation=reservation,
            override_layers=data.get("override_layers"),
            override_reason=data.get("override_reason") or "",
            user=request.user,
            reason=data.get("reason") or "api_consumption",
            reference=data.get("reference") or "",
            sale=_related(Sale, data.get("sale_id"), "Sale"),
            order_line=_related(SaleLineItem, data.get("order_line_id"), "Order line"),
            production_order=_related(
                ProductionOrder, data.get("production_order_id"), "Production order"
            ),
        )
    except PermissionDenied as exc:
        return fail(str(exc), status=403)
    except ValueError as exc:
        return fail(str(exc), status=400)
    payload = {
            "uuid": str(result["consumption"].uuid),
            "movement_id": result["movement"].id,
            "quantity": _number(result["quantity"]),
            "unit_cost": _number(result["unit_cost"]),
            "total_cost": _number(result["total_cost"]),
            "allocations": [
                {key: _number(value) if isinstance(value, Decimal) else value for key, value in row.items()}
                for row in result["allocations"]
            ],
        }
    if not can_view_costs(request.user):
        from logic.materials import mask_cost_fields
        payload = mask_cost_fields(payload)
    return success(payload, status=201)


@api_view("GET", "POST")
def document_attachments(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    source_type = request.POST.get("source_type") if request.method == "POST" else request.GET.get("source_type")
    source_id = request.POST.get("source_id") if request.method == "POST" else request.GET.get("source_id")
    try:
        field, source = resolve_source(source_type, source_id)
    except (TypeError, ValueError) as exc:
        return fail(str(exc), status=400)
    if request.method == "GET":
        rows = DocumentAttachment.objects.filter(**{field: source}).select_related("uploaded_by")
        return success({"results": [attachment_to_dict(row) for row in rows]})
    if not _can_manage(request.user) and not has_permission(request.user, CREATE_ACCOUNTING):
        return fail("Permission denied", status=403)
    upload = request.FILES.get("file")
    if upload is None:
        return fail("file is required", status=400)
    try:
        row = create_attachment(
            upload,
            source_type=source_type,
            source_id=source_id,
            user=request.user,
            description=request.POST.get("description") or "",
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(attachment_to_dict(row), status=201)
