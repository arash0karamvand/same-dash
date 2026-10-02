"""Lock-safe reservations, purchase lots, FIFO allocation, and stock adjustments."""

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from auth.permissions import CREATE_ACCOUNTING, MANAGE_MATERIALS, MANAGE_PRODUCTS, has_permission
from backend.models import (
    InventoryAllocation,
    InventoryConsumption,
    InventoryCostLayer,
    InventoryReservation,
    InventoryTransaction,
    Material,
    ProductVariant,
)
from logic.accounting import create_journal
from logic.accounting_accounts import get_account
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.ledger import OFFICE_LEDGER
from logic.stock_locations import location_transaction_kwargs


def _rial(value):
    return Decimal(value or 0).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _qty(value):
    return Decimal(str(value or 0))


def _item_kwargs(item):
    if isinstance(item, Material):
        return {"material": item, "variant": None}
    if isinstance(item, ProductVariant):
        return {"material": None, "variant": item}
    raise ValueError("Inventory item must be a material or product variant.")


def _location_filter(location):
    if not location:
        return {}
    values = {"location_kind": location["kind"]}
    if location["kind"] == InventoryTransaction.LOCATION_WAREHOUSE:
        values["warehouse_id"] = location.get("warehouse_id") or location["warehouse"].pk
    else:
        branch = location.get("branch_id") or location.get("branch")
        values["branch_id"] = branch.pk if hasattr(branch, "pk") else branch
    return values


def _on_hand(item, location=None):
    qs = item.inventory_movements.all()
    if location:
        qs = qs.filter(**_location_filter(location))
    return _qty(qs.aggregate(total=Sum("quantity"))["total"])


def ensure_opening_layer(item, *, location=None):
    item_fields = _item_kwargs(item)
    layers = InventoryCostLayer.objects.filter(
        **{key: value for key, value in item_fields.items() if value is not None},
        qty_remaining__gt=0,
    )
    if location:
        layers = layers.filter(**_location_filter(location))
    if layers.exists():
        return
    stock = _on_hand(item, location)
    if stock <= 0:
        return
    unit_cost = item.unit_cost if isinstance(item, Material) else 0
    InventoryCostLayer.objects.create(
        **item_fields,
        unit_cost=_rial(unit_cost),
        original_qty=stock,
        qty_remaining=stock,
        **location_transaction_kwargs(location),
        metadata={"backfilled_opening_balance": True},
    )


def _refresh_fifo_unit_cost(material):
    layers = list(material.cost_layers.filter(qty_remaining__gt=0))
    total_qty = sum(_qty(layer.qty_remaining) for layer in layers)
    if total_qty <= 0:
        return
    total_value = sum(_qty(layer.qty_remaining) * Decimal(layer.unit_cost or 0) for layer in layers)
    material.unit_cost = _rial(total_value / total_qty)
    material.save(update_fields=["unit_cost", "updated_at"])


def inventory_value(material):
    ensure_opening_layer(material)
    total = Decimal(0)
    for layer in material.cost_layers.filter(qty_remaining__gt=0):
        total += _qty(layer.qty_remaining) * Decimal(layer.unit_cost or 0)
    return int(_rial(total))


def set_valuation_method(material, method):
    from logic.lookups import require_active_code

    method = require_active_code(
        "material_valuation_method",
        method,
        "روش ارزیابی نامعتبر است.",
        default=Material.VALUATION_WEIGHTED,
    )
    if material.valuation_method == method:
        return material
    if method == Material.VALUATION_FIFO:
        material.valuation_method = method
        material.save(update_fields=["valuation_method", "updated_at"])
        ensure_opening_layer(material)
        return material
    layers = list(material.cost_layers.filter(qty_remaining__gt=0))
    total_qty = sum(_qty(layer.qty_remaining) for layer in layers)
    if total_qty > 0:
        total_value = sum(_qty(layer.qty_remaining) * Decimal(layer.unit_cost or 0) for layer in layers)
        material.unit_cost = _rial(total_value / total_qty)
    material.valuation_method = method
    material.save(update_fields=["valuation_method", "unit_cost", "updated_at"])
    return material


def issue_cost(material, quantity):
    """Compatibility API: consume inventory and return the allocated unit cost."""
    result = consume_stock(material, quantity, reason="legacy_issue_cost")
    return result["unit_cost"]


def availability(item, *, location=None):
    item_fields = _item_kwargs(item)
    reservations = InventoryReservation.objects.filter(
        **{key: value for key, value in item_fields.items() if value is not None},
        status=InventoryReservation.STATUS_ACTIVE,
    )
    if location:
        reservations = reservations.filter(**_location_filter(location))
    reserved = _qty(reservations.aggregate(total=Sum("quantity"))["total"])
    on_hand = _on_hand(item, location)
    return {
        "on_hand": on_hand,
        "reserved": reserved,
        "available": on_hand - reserved,
        # Transfers are currently posted at completion, so no open transit balance is synthesized.
        "in_transit": Decimal("0"),
    }


@transaction.atomic
def reserve_stock(
    item,
    quantity,
    *,
    location,
    user=None,
    sale=None,
    order_line=None,
    production_order=None,
    reference="",
    reason="",
):
    qty = _qty(quantity)
    if qty <= 0:
        raise ValueError("Reservation quantity must be greater than zero.")
    if order_line is not None and sale is not None and order_line.sale_id != sale.pk:
        raise ValueError("Order line does not belong to the supplied sale.")
    item_fields = _item_kwargs(item)
    model = type(item)
    locked = model.objects.select_for_update().get(pk=item.pk)
    balances = availability(locked, location=location)
    if balances["available"] < qty:
        raise ValueError("Available inventory is insufficient for this reservation.")
    return InventoryReservation.objects.create(
        **_item_kwargs(locked),
        quantity=qty,
        reserved_by=user,
        sale=sale,
        order_line=order_line,
        production_order=production_order,
        reference=(reference or "").strip(),
        reason=(reason or "").strip(),
        **location_transaction_kwargs(location),
    )


@transaction.atomic
def release_reservation(reservation, *, user=None, reason=""):
    locked = InventoryReservation.objects.select_for_update().get(pk=reservation.pk)
    if locked.status != InventoryReservation.STATUS_ACTIVE:
        raise ValueError("Only an active reservation can be released.")
    locked.status = InventoryReservation.STATUS_RELEASED
    locked.released_by = user
    locked.released_at = timezone.now()
    if reason:
        locked.reason = (reason or "").strip()
    locked.save(update_fields=["status", "released_by", "released_at", "reason"])
    return locked


def _override_allowed(user):
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_superuser", False)
            or has_permission(user, CREATE_ACCOUNTING)
            or has_permission(user, MANAGE_MATERIALS)
            or has_permission(user, MANAGE_PRODUCTS)
        )
    )


def _normalize_override(override_layers):
    if not override_layers:
        return None
    normalized = []
    for row in override_layers:
        if isinstance(row, dict):
            layer_id = row.get("layer_id") or row.get("id")
            quantity = row.get("quantity")
        else:
            layer_id, quantity = row, None
        if not layer_id:
            raise ValueError("Every lot override must identify a cost layer.")
        normalized.append((int(layer_id), None if quantity in (None, "") else _qty(quantity)))
    if len({row[0] for row in normalized}) != len(normalized):
        raise ValueError("A lot cannot appear twice in an override.")
    return normalized


@transaction.atomic
def consume_stock(
    item,
    quantity,
    *,
    location=None,
    reservation=None,
    override_layers=None,
    override_reason="",
    system_override=False,
    user=None,
    reason="consumption",
    reference="",
    sale=None,
    order_line=None,
    production_order=None,
):
    qty = _qty(quantity)
    if qty <= 0:
        raise ValueError("Consumption quantity must be greater than zero.")
    if order_line is not None and sale is not None and order_line.sale_id != sale.pk:
        raise ValueError("Order line does not belong to the supplied sale.")
    normalized_override = _normalize_override(override_layers)
    if normalized_override:
        if not (override_reason or "").strip():
            raise ValueError("A nonempty reason is required for a lot override.")
        if not system_override and not _override_allowed(user):
            raise PermissionDenied("The current user is not authorized to override FIFO lots.")
    elif (override_reason or "").strip():
        raise ValueError("An override reason is only valid with caller-supplied lots.")

    locked_item = type(item).objects.select_for_update().get(pk=item.pk)
    locked_reservation = None
    if reservation is not None:
        locked_reservation = InventoryReservation.objects.select_for_update().get(pk=reservation.pk)
        if locked_reservation.status != InventoryReservation.STATUS_ACTIVE:
            raise ValueError("The reservation is not active.")
        if locked_reservation.material_id != getattr(locked_item, "pk", None) and isinstance(
            locked_item, Material
        ):
            raise ValueError("Reservation item does not match consumption.")
        if locked_reservation.variant_id != getattr(locked_item, "pk", None) and isinstance(
            locked_item, ProductVariant
        ):
            raise ValueError("Reservation item does not match consumption.")
        if _qty(locked_reservation.quantity) != qty:
            raise ValueError("A reservation must be consumed for its exact quantity.")
        reservation_location = {
            "kind": locked_reservation.location_kind,
            "warehouse": locked_reservation.warehouse,
            "warehouse_id": locked_reservation.warehouse_id,
            "branch": locked_reservation.branch,
            "branch_id": locked_reservation.branch_id,
        }
        if location and _location_filter(location) != _location_filter(reservation_location):
            raise ValueError("Reservation location does not match consumption.")
        location = reservation_location
    else:
        reservation_qs = InventoryReservation.objects.select_for_update().filter(
            **{
                key: value
                for key, value in _item_kwargs(locked_item).items()
                if value is not None
            },
            status=InventoryReservation.STATUS_ACTIVE,
        )
        if location:
            reservation_qs = reservation_qs.filter(**_location_filter(location))
        list(reservation_qs.values_list("pk", flat=True))
        if availability(locked_item, location=location)["available"] < qty:
            raise ValueError("Inventory shortage after active reservations.")

    ensure_opening_layer(locked_item, location=location)
    layer_qs = InventoryCostLayer.objects.select_for_update().filter(
        **{key: value for key, value in _item_kwargs(locked_item).items() if value is not None},
        qty_remaining__gt=0,
    )
    if location:
        layer_qs = layer_qs.filter(**_location_filter(location))
    layer_map = {layer.pk: layer for layer in layer_qs.order_by("created_at", "id")}

    picks = []
    remaining = qty
    if normalized_override:
        for layer_id, requested in normalized_override:
            layer = layer_map.get(layer_id)
            if layer is None:
                raise ValueError("An override lot is unavailable or belongs to another item/location.")
            take = min(_qty(layer.qty_remaining), remaining) if requested is None else requested
            if take <= 0 or take > _qty(layer.qty_remaining) or take > remaining:
                raise ValueError("Lot override quantity is invalid.")
            picks.append((layer, take))
            remaining -= take
        if remaining:
            raise ValueError("Lot override quantities must exactly equal the consumption quantity.")
    else:
        for layer in layer_map.values():
            take = min(_qty(layer.qty_remaining), remaining)
            if take > 0:
                picks.append((layer, take))
                remaining -= take
            if remaining <= 0:
                break
        if remaining > 0:
            raise ValueError("Inventory lot shortage; consumption was not recorded.")

    total_cost = sum(
        (take * Decimal(layer.unit_cost or 0) for layer, take in picks),
        Decimal("0"),
    )
    unit_cost = _rial(total_cost / qty)
    movement = InventoryTransaction.objects.create(
        **_item_kwargs(locked_item),
        quantity=-qty,
        unit_cost=unit_cost,
        reason=reason,
        reference=reference,
        recorded_by=user,
        order_line=order_line,
        **location_transaction_kwargs(location),
    )
    consumption = InventoryConsumption.objects.create(
        **_item_kwargs(locked_item),
        quantity=qty,
        total_cost=_rial(total_cost),
        movement=movement,
        reservation=locked_reservation,
        sale=sale,
        order_line=order_line,
        production_order=production_order,
        reference=reference,
        override_reason=(override_reason or "").strip() if normalized_override else "",
        overridden_by=user if normalized_override else None,
        recorded_by=user,
    )
    allocation_details = []
    for layer, take in picks:
        InventoryAllocation.objects.create(
            consumption=consumption,
            cost_layer=layer,
            quantity=take,
            unit_cost=layer.unit_cost,
        )
        layer.qty_remaining = _qty(layer.qty_remaining) - take
        layer.save(update_fields=["qty_remaining"])
        allocation_details.append(
            {
                "layer_id": layer.pk,
                "layer_uuid": str(layer.uuid),
                "quantity": take,
                "unit_cost": Decimal(layer.unit_cost or 0),
                "line_cost": _rial(take * Decimal(layer.unit_cost or 0)),
            }
        )
    if locked_reservation:
        locked_reservation.status = InventoryReservation.STATUS_CONSUMED
        locked_reservation.save(update_fields=["status"])
    if isinstance(locked_item, Material):
        _refresh_fifo_unit_cost(locked_item)
    return {
        "consumption": consumption,
        "movement": movement,
        "quantity": qty,
        "unit_cost": unit_cost,
        "total_cost": _rial(total_cost),
        "allocations": allocation_details,
    }


def _post_period_freight(material, freight, user=None):
    amount = int(_rial(freight))
    if amount <= 0:
        return None
    expense = get_account(ACCOUNT_SLUGS.DISTRIBUTION_SALES_EXPENSE, ledger=OFFICE_LEDGER)
    payable = get_account(ACCOUNT_SLUGS.ACCOUNTS_PAYABLE, ledger=OFFICE_LEDGER)
    label = material.name
    return create_journal(
        lines=[
            {"account": expense, "debit": amount, "credit": 0, "description": f"حمل {label}"},
            {"account": payable, "debit": 0, "credit": amount, "description": f"حمل {label}"},
        ],
        entry_type="adjustment",
        description=f"هزینه حمل دوره — {label}",
        is_approved=False,
        ledger=OFFICE_LEDGER,
        user=user,
    )


@transaction.atomic
def receive_stock(
    material,
    quantity,
    unit_cost,
    *,
    freight_amount=0,
    freight_treatment="capitalize",
    previous_unit_cost=None,
    reason="receipt",
    reference="",
    recorded_by=None,
    location=None,
    supplier=None,
    purchase_invoice=None,
    invoice_number="",
    metadata=None,
):
    qty = _qty(quantity)
    if qty <= 0:
        raise ValueError("مقدار رسید باید بزرگ‌تر از صفر باشد.")
    cost = _rial(unit_cost)
    freight = _rial(freight_amount)
    if freight < 0 or cost < 0:
        raise ValueError("بهای رسید نامعتبر است.")
    from logic.lookups import require_active_code

    treatment = require_active_code(
        "material_freight_treatment",
        freight_treatment,
        "نحوه ثبت حمل نامعتبر است.",
        default="capitalize",
    )
    goods = qty * cost
    if treatment == "capitalize":
        inbound_value = goods + freight
    else:
        inbound_value = goods
        if freight > 0:
            _post_period_freight(material, freight, user=recorded_by)
    effective = _rial(inbound_value / qty)
    on_hand = _qty(material.stock)
    prior = Decimal(previous_unit_cost if previous_unit_cost is not None else material.unit_cost or 0)
    if material.valuation_method == Material.VALUATION_FIFO:
        material.unit_cost = effective if on_hand <= 0 else material.unit_cost
        material.save(update_fields=["unit_cost", "updated_at"])
    else:
        new_qty = on_hand + qty
        if new_qty > 0:
            material.unit_cost = _rial((on_hand * prior + inbound_value) / new_qty)
        else:
            material.unit_cost = effective
        material.save(update_fields=["unit_cost", "updated_at"])
    txn = InventoryTransaction.objects.create(
        material=material,
        quantity=qty,
        unit_cost=effective,
        reason=reason,
        reference=reference or f"material:{material.pk}",
        recorded_by=recorded_by,
        **location_transaction_kwargs(location),
    )
    InventoryCostLayer.objects.create(
        material=material,
        source_transaction=txn,
        unit_cost=effective,
        original_qty=qty,
        qty_remaining=qty,
        supplier=supplier,
        purchase_invoice=purchase_invoice,
        invoice_number=(invoice_number or "").strip(),
        metadata=metadata or {},
        **location_transaction_kwargs(location),
    )
    if material.valuation_method == Material.VALUATION_FIFO:
        _refresh_fifo_unit_cost(material)
    return txn


@transaction.atomic
def adjust_stock(
    item,
    quantity_delta,
    *,
    unit_cost=None,
    location=None,
    user=None,
    reason,
    reference="",
):
    """Explicit service for catalog/stocktake corrections; never edits ledger rows."""
    delta = _qty(quantity_delta)
    if not delta:
        raise ValueError("Stock adjustment cannot be zero.")
    if isinstance(item, Material) and delta > 0:
        return receive_stock(
            item,
            delta,
            unit_cost if unit_cost is not None else item.unit_cost,
            location=location,
            recorded_by=user,
            reason=reason,
            reference=reference,
            metadata={"adjustment": True},
        )
    if delta < 0:
        return consume_stock(
            item,
            -delta,
            location=location,
            user=user,
            reason=reason,
            reference=reference,
        )["movement"]
    # Product receipts have no material weighted-cost behavior but still create a true lot.
    locked = ProductVariant.objects.select_for_update().get(pk=item.pk)
    cost = _rial(unit_cost or 0)
    movement = InventoryTransaction.objects.create(
        variant=locked,
        quantity=delta,
        unit_cost=cost,
        reason=reason,
        reference=reference,
        recorded_by=user,
        **location_transaction_kwargs(location),
    )
    InventoryCostLayer.objects.create(
        variant=locked,
        source_transaction=movement,
        unit_cost=cost,
        original_qty=delta,
        qty_remaining=delta,
        metadata={"adjustment": True},
        **location_transaction_kwargs(location),
    )
    return movement
