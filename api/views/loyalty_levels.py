"""endpointهای سطوح باشگاه — /api/loyalty-levels/."""

from backend.models import Customer, LoyaltyLevel

from api.helpers import api_view, fail, parse_json, success
from api.serializers import level_to_dict
from auth.permissions import MANAGE_LOYALTY, VIEW_LOYALTY, has_permission
from logic.levels import update_customer_level
from logic.audit import log_action


def _to_decimal_or_none(value):
    if value in (None, "", "null"):
        return None
    return value


@api_view("GET", "POST")
def level_list(request):
    if request.method == "GET":
        if not has_permission(request.user, VIEW_LOYALTY):
            return fail("Permission denied", status=403)
        levels = LoyaltyLevel.objects.all()
        return success({"results": [level_to_dict(l) for l in levels]})

    if not has_permission(request.user, MANAGE_LOYALTY):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return fail("Level name is required", status=400)

    level = LoyaltyLevel.objects.create(
        name=name,
        min_purchase=data.get("min_purchase") or 0,
        max_purchase=_to_decimal_or_none(data.get("max_purchase")),
        discount_percent=data.get("discount_percent") or 0,
        points=data.get("points") or 0,
        description=(data.get("description") or "").strip(),
        color=data.get("color") or "#6366f1",
    )
    _recalculate_all()
    log_action(
        request.user,
        "create",
        f"سطح باشگاه: {name}",
        entity_type="LoyaltyLevel",
        entity_id=level.id,
    )
    return success(level_to_dict(level), status=201)


@api_view("PUT", "DELETE")
def level_detail(request, pk):
    try:
        level = LoyaltyLevel.objects.get(pk=pk)
    except LoyaltyLevel.DoesNotExist:
        return fail("Level not found", status=404)

    if request.method in ("PUT", "DELETE") and not has_permission(request.user, MANAGE_LOYALTY):
        return fail("Permission denied", status=403)

    if request.method == "DELETE":
        level.soft_delete()
        _recalculate_all()
        log_action(
            request.user,
            "delete",
            f"حذف سطح {level.name}",
            entity_type="LoyaltyLevel",
            entity_id=level.id,
        )
        return success({"deleted": True})

    data = parse_json(request)
    if "name" in data:
        level.name = data["name"]
    if "min_purchase" in data:
        level.min_purchase = data.get("min_purchase") or 0
    if "max_purchase" in data:
        level.max_purchase = _to_decimal_or_none(data.get("max_purchase"))
    if "discount_percent" in data:
        level.discount_percent = data.get("discount_percent") or 0
    if "points" in data:
        level.points = data.get("points") or 0
    if "description" in data:
        level.description = data.get("description") or ""
    if "color" in data:
        level.color = data.get("color")
    if "is_active" in data:
        level.is_active = bool(data.get("is_active"))
    level.save()
    _recalculate_all()
    log_action(
        request.user,
        "update",
        f"ویرایش سطح {level.name}",
        entity_type="LoyaltyLevel",
        entity_id=level.id,
    )
    return success(level_to_dict(level))


def _recalculate_all():
    for customer in Customer.objects.all():
        update_customer_level(customer, reason="Loyalty level definition changed")
