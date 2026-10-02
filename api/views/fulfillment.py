"""Fulfillment planning and traceable stock-transfer endpoints."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import (
    APPROVE_SALE_ACCOUNTING,
    MANAGE_PRODUCTS,
    VIEW_PRODUCTS,
    has_permission,
)
from backend.models import (
    FulfillmentPlan,
    MerchantSupplyDemand,
    ProductVariant,
    SaleLineItem,
    StockTransfer,
)
from logic.fulfillment import (
    complete_stock_transfer,
    execute_fulfillment_plan,
    plan_to_dict,
    release_fulfillment_plan,
    receive_merchant_supply,
    save_fulfillment_plan,
    start_stock_transfer,
)
from logic.inventory_costing import availability
from logic.stock_locations import list_stock_locations, parse_location


def _can_view(user):
    return has_permission(user, VIEW_PRODUCTS) or has_permission(user, APPROVE_SALE_ACCOUNTING)


def _can_manage(user):
    return has_permission(user, MANAGE_PRODUCTS) or has_permission(user, APPROVE_SALE_ACCOUNTING)


@api_view("GET")
def line_availability(request, line_id):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    line = SaleLineItem.objects.select_related("variant").filter(pk=line_id).first()
    if line is None:
        return fail("Sale line not found", status=404)
    rows = []
    for raw in list_stock_locations():
        location = parse_location(raw, required=True)
        balance = (
            availability(line.variant, location=location)
            if line.variant_id
            else {"on_hand": 0, "reserved": 0, "available": 0, "in_transit": 0}
        )
        rows.append({**raw, **{key: float(value) for key, value in balance.items()}})
    plan = FulfillmentPlan.objects.filter(sale_line=line).first()
    return success({"sale_line_id": line.pk, "quantity": float(line.quantity), "locations": rows,
                    "plan": plan_to_dict(plan) if plan else None})


@api_view("GET", "PUT")
def line_plan(request, line_id):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    line = SaleLineItem.objects.filter(pk=line_id).first()
    if line is None:
        return fail("Sale line not found", status=404)
    if request.method == "GET":
        plan = FulfillmentPlan.objects.filter(sale_line=line).first()
        return success(plan_to_dict(plan) if plan else None)
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    try:
        plan = save_fulfillment_plan(line, (parse_json(request) or {}).get("lines"), user=request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(plan_to_dict(plan))


@api_view("POST")
def plan_release(request, plan_uuid):
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    plan = FulfillmentPlan.objects.filter(uuid=plan_uuid).first()
    if plan is None:
        return fail("Fulfillment plan not found", status=404)
    try:
        plan = release_fulfillment_plan(plan, user=request.user, cancel=bool(parse_json(request).get("cancel")))
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(plan_to_dict(plan))


@api_view("POST")
def plan_execute(request, plan_uuid):
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    plan = FulfillmentPlan.objects.filter(uuid=plan_uuid).first()
    if plan is None:
        return fail("Fulfillment plan not found", status=404)
    try:
        plan = execute_fulfillment_plan(plan, user=request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(plan_to_dict(plan))


@api_view("POST")
def merchant_receive(request, demand_uuid):
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    demand = MerchantSupplyDemand.objects.filter(uuid=demand_uuid).first()
    if demand is None:
        return fail("Merchant demand not found", status=404)
    try:
        demand = receive_merchant_supply(
            demand, unit_cost=(parse_json(request) or {}).get("unit_cost"), user=request.user
        )
    except (ValueError, TypeError) as exc:
        return fail(str(exc), status=400)
    return success({
        "uuid": str(demand.uuid),
        "status": demand.status,
        "receipt_movement_id": demand.receipt_movement_id,
    })


@api_view("POST")
def transfer_start(request):
    if not has_permission(request.user, MANAGE_PRODUCTS):
        return fail("Permission denied", status=403)
    data = parse_json(request)
    variant = ProductVariant.objects.filter(pk=data.get("variant_id"), is_active=True).first()
    if variant is None:
        return fail("Variant not found", status=404)
    try:
        transfer = start_stock_transfer(
            variant,
            parse_location(data.get("source"), required=True),
            parse_location(data.get("destination"), required=True),
            data.get("quantity"),
            idempotency_key=data.get("idempotency_key"),
            user=request.user,
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success({"uuid": str(transfer.uuid), "status": transfer.status}, status=201)


@api_view("POST")
def transfer_complete(request, transfer_uuid):
    if not has_permission(request.user, MANAGE_PRODUCTS):
        return fail("Permission denied", status=403)
    transfer = StockTransfer.objects.filter(uuid=transfer_uuid).first()
    if transfer is None:
        return fail("Transfer not found", status=404)
    try:
        transfer = complete_stock_transfer(transfer, user=request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success({
        "uuid": str(transfer.uuid),
        "status": transfer.status,
        "issue_movement_id": transfer.issue_movement_id,
        "receipt_movement_id": transfer.receipt_movement_id,
        "accounting_event_id": transfer.accounting_event_id,
    })
