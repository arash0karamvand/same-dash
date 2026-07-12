"""endpointهای مشتریان — /api/customers/."""

from backend.models import Customer

from api.helpers import api_view, fail, parse_json, success
from api.serializers import customer_to_dict, level_history_to_dict, sale_to_dict
from auth.permissions import (
    CREATE_CUSTOMER,
    DELETE_CUSTOMER,
    EDIT_CUSTOMER,
    MANAGE_LOYALTY,
    RECALCULATE_LEVELS,
    VIEW_CUSTOMERS,
    has_permission,
)
from logic.levels import update_customer_level
from logic.audit import log_action
from logic.analytics import top_repeat_buyers_year
from logic.customers import apply_customer_filters


def _parse_birthday(data):
    if "birthday" not in data:
        return None, False
    raw = data.get("birthday")
    if not raw:
        return None, True
    from django.utils.dateparse import parse_date

    parsed = parse_date(str(raw).strip()[:10])
    if not parsed:
        raise ValueError("تاریخ تولد نامعتبر است.")
    return parsed, True


@api_view("GET", "POST")
def customer_list(request):
    if request.method == "GET":
        if not has_permission(request.user, VIEW_CUSTOMERS):
            return fail("Permission denied", status=403)
        qs = Customer.objects.select_related("level").all()
        qs = apply_customer_filters(qs, request.GET)
        return success({"results": [customer_to_dict(c) for c in qs]})

    if not has_permission(request.user, CREATE_CUSTOMER):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    full_name = (data.get("full_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not full_name or not phone:
        return fail("Full name and phone are required", status=400)
    if Customer.objects.filter(phone=phone).exists():
        return fail("Customer with this phone already exists", status=400)

    try:
        birthday, has_birthday = _parse_birthday(data)
    except ValueError as exc:
        return fail(str(exc), status=400)

    from logic.membership import generate_membership_code

    customer = Customer.objects.create(
        full_name=full_name,
        phone=phone,
        email=(data.get("email") or "").strip(),
        address=(data.get("address") or "").strip(),
        notes=(data.get("notes") or "").strip(),
        membership_code=generate_membership_code(),
    )
    birthday, has_birthday = _parse_birthday(data)
    if has_birthday:
        customer.birthday = birthday
        customer.save(update_fields=["birthday"])
    log_action(
        request.user,
        "create",
        f"مشتری جدید: {full_name} — {phone}",
        entity_type="Customer",
        entity_id=customer.id,
    )
    from logic.sms_club import maybe_send_welcome

    maybe_send_welcome(customer, user=request.user)
    return success(customer_to_dict(customer), status=201)


@api_view("GET", "PUT", "DELETE")
def customer_detail(request, pk):
    try:
        customer = Customer.objects.select_related("level").get(pk=pk)
    except Customer.DoesNotExist:
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

    data = parse_json(request)
    try:
        birthday, has_birthday = _parse_birthday(data)
    except ValueError as exc:
        return fail(str(exc), status=400)
    for field in ("full_name", "email", "notes", "address"):
        if field in data:
            setattr(customer, field, (data.get(field) or "").strip())
    if "phone" in data:
        new_phone = (data.get("phone") or "").strip()
        if Customer.objects.filter(phone=new_phone).exclude(pk=customer.pk).exists():
            return fail("Phone number already used by another customer", status=400)
        customer.phone = new_phone
    if "is_active" in data:
        customer.is_active = bool(data.get("is_active"))
    if has_birthday:
        customer.birthday = birthday
    customer.save()
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
    try:
        customer = Customer.objects.get(pk=pk)
    except Customer.DoesNotExist:
        return fail("Customer not found", status=404)

    sales = customer.sales.prefetch_related("line_items").order_by("-sold_at")
    history = customer.level_history.select_related("previous_level", "new_level").all()
    return success(
        {
            "sales": [sale_to_dict(s, include_lines=True) for s in sales],
            "level_history": [level_history_to_dict(h) for h in history],
        }
    )


@api_view("POST", permission=MANAGE_LOYALTY)
def recalculate_level(request, pk):
    try:
        customer = Customer.objects.select_related("level").get(pk=pk)
    except Customer.DoesNotExist:
        return fail("Customer not found", status=404)

    new_level = update_customer_level(customer, reason="Manual recalculation via API")
    customer.refresh_from_db()
    log_action(
        request.user,
        "update",
        f"بازمحاسبه سطح مشتری {customer.full_name}",
        entity_type="Customer",
        entity_id=customer.id,
    )
    return success(
        {
            "customer": customer_to_dict(customer),
            "level": new_level.name if new_level else None,
        }
    )


@api_view("POST", permission=RECALCULATE_LEVELS)
def recalculate_all_levels(request):
    count = 0
    for customer in Customer.objects.all():
        update_customer_level(customer, reason="Bulk recalculation via API")
        count += 1
    log_action(request.user, "update", f"بازمحاسبه سطح {count} مشتری")
    return success({"recalculated_count": count})


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
