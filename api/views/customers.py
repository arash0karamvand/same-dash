"""endpointهای مشتریان — /api/customers/."""

from api.helpers import api_view, fail, parse_json, success
from api.serializers import customer_to_dict, level_history_to_dict, sale_to_dict
from auth.permissions import (
    CREATE_CUSTOMER,
    DELETE_CUSTOMER,
    EDIT_CUSTOMER,
    MANAGE_LOYALTY,
    MANAGE_RFM,
    RECALCULATE_LEVELS,
    VIEW_CUSTOMERS,
    has_permission,
)
from logic.analytics import top_repeat_buyers_year
from logic.audit import log_action
from logic.customers import (
    create_customer,
    customer_history_payload,
    get_customer,
    list_customers,
    update_customer,
)
from logic.rfm import recalculate_all_rfm, recalculate_customer_rfm
from logic.sms_club import maybe_send_welcome


@api_view("GET", "POST")
def customer_list(request):
    if request.method == "GET":
        if not has_permission(request.user, VIEW_CUSTOMERS):
            return fail("Permission denied", status=403)
        from logic.pagination import paginate

        qs = list_customers(request.GET)
        page, meta = paginate(qs, request.GET)
        return success({"results": [customer_to_dict(c) for c in page], **meta})

    if not has_permission(request.user, CREATE_CUSTOMER):
        return fail("Permission denied", status=403)

    try:
        customer = create_customer(parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "create",
        f"مشتری جدید: {customer.full_name} — {customer.phone}",
        entity_type="Customer",
        entity_id=customer.id,
    )
    maybe_send_welcome(customer, user=request.user)
    return success(customer_to_dict(customer), status=201)


@api_view("GET", "PUT", "DELETE")
def customer_detail(request, pk):
    customer = get_customer(pk, with_level=True)
    if customer is None:
        return fail("Customer not found", status=404)

    if request.method == "GET":
        if not has_permission(request.user, VIEW_CUSTOMERS):
            return fail("Permission denied", status=403)
        return success(customer_to_dict(customer))

    if request.method == "DELETE":
        if not has_permission(request.user, DELETE_CUSTOMER):
            return fail("Permission denied", status=403)
        customer.soft_delete()
        log_action(
            request.user,
            "delete",
            f"حذف مشتری {customer.full_name}",
            entity_type="Customer",
            entity_id=customer.id,
        )
        return success({"deleted": True})

    if not has_permission(request.user, EDIT_CUSTOMER):
        return fail("Permission denied", status=403)

    try:
        update_customer(customer, parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "update",
        f"ویرایش مشتری {customer.full_name}",
        entity_type="Customer",
        entity_id=customer.id,
    )
    return success(customer_to_dict(customer))


@api_view("GET", permission=VIEW_CUSTOMERS)
def customer_history(request, pk):
    customer = get_customer(pk)
    if customer is None:
        return fail("Customer not found", status=404)
    return success(customer_history_payload(customer, sale_to_dict, level_history_to_dict))


@api_view("POST")
def recalculate_level(request, pk):
    if not has_permission(request.user, MANAGE_LOYALTY) and not has_permission(request.user, MANAGE_RFM):
        return fail("Permission denied", status=403)
    customer = get_customer(pk, with_level=True)
    if customer is None:
        return fail("Customer not found", status=404)

    score = recalculate_customer_rfm(customer, user=request.user)
    customer.refresh_from_db()
    log_action(
        request.user,
        "update",
        f"بازمحاسبه RFM مشتری {customer.full_name}",
        entity_type="Customer",
        entity_id=customer.id,
    )
    segment_name = score.segment.name if score and score.segment_id else None
    return success(
        {
            "customer": customer_to_dict(customer),
            "level": segment_name,
        }
    )


@api_view("POST")
def recalculate_all_levels(request):
    if not has_permission(request.user, RECALCULATE_LEVELS) and not has_permission(request.user, MANAGE_RFM):
        return fail("Permission denied", status=403)
    result = recalculate_all_rfm(send_actions=False)
    log_action(request.user, "update", f"بازمحاسبه RFM {result.get('scored', 0)} مشتری")
    return success({"recalculated_count": result.get("scored", 0), **result})


@api_view("GET")
def customer_top_buyers(request):
    if not has_permission(request.user, VIEW_CUSTOMERS):
        return fail("Permission denied", status=403)
    try:
        limit = min(max(int(request.GET.get("limit") or 20), 1), 50)
        min_purchases = max(int(request.GET.get("min_purchases") or 2), 2)
        days = max(int(request.GET.get("days") or 365), 1)
    except (TypeError, ValueError):
        limit, min_purchases, days = 20, 2, 365

    results = top_repeat_buyers_year(limit=limit, min_purchases=min_purchases, days=days)
    return success(
        {
            "results": results,
            "top": results[0] if results else None,
            "limit": limit,
            "min_purchases": min_purchases,
            "days": days,
        }
    )
