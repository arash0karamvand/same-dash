"""API پیکربندی چرخه سفارش، انبارها و صف‌های نظارت."""

from api.helpers import api_view, fail, parse_json, success
from api.serializers import sale_to_dict
from auth.permissions import APPROVE_SALE_ACCOUNTING, has_permission, is_system_admin
from backend.models import Warehouse
from logic.audit import log_action
from logic.order_cycle import (
    can_list_pickup_orders,
    can_list_warehouse_orders,
    create_warehouse,
    cycle_flags_for_user,
    cycle_to_dict,
    list_warehouses,
    pickup_order_queryset,
    save_cycle,
    seed_order_cycle,
    update_warehouse,
    warehouse_order_queryset,
    warehouse_to_dict,
    watch_queryset,
)
from logic.pagination import paginate


def _require_admin(user):
    if not is_system_admin(user):
        return fail("فقط مدیر سیستم مجاز است.", status=403)
    return None


def _sale_page(qs, request, user):
    page, meta = paginate(qs, request.GET)
    return success(
        {
            "results": [sale_to_dict(s, include_lines=True, user=user) for s in page],
            **meta,
        }
    )


@api_view("GET", "PUT")
def cycle_config(request):
    seed_order_cycle()
    if request.method == "GET":
        denied = _require_admin(request.user)
        if denied:
            return denied
        return success(cycle_to_dict())

    denied = _require_admin(request.user)
    if denied:
        return denied
    try:
        cycle = save_cycle(parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(request.user, "update", "به‌روزرسانی چرخه سفارش")
    return success(cycle_to_dict(cycle))


@api_view("GET")
def cycle_me(request):
    seed_order_cycle()
    flags = cycle_flags_for_user(request.user)
    data = cycle_to_dict() if is_system_admin(request.user) else {
        "enabled_routes": flags["enabled_routes"],
        "warehouses": [warehouse_to_dict(w) for w in list_warehouses(active_only=True)],
    }
    data.update(flags)
    if is_system_admin(request.user) or has_permission(request.user, APPROVE_SALE_ACCOUNTING):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        data["colleagues"] = [
            {
                "id": u.id,
                "full_name": (u.get_full_name() or u.username).strip() or u.username,
            }
            for u in User.objects.filter(is_active=True).order_by("first_name", "last_name", "username")[:300]
        ]
    return success(data)


@api_view("GET", "POST")
def warehouse_list(request):
    seed_order_cycle()
    if request.method == "GET":
        active_only = not is_system_admin(request.user)
        return success({"results": [warehouse_to_dict(w) for w in list_warehouses(active_only=active_only)]})
    denied = _require_admin(request.user)
    if denied:
        return denied
    try:
        warehouse = create_warehouse(parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(request.user, "create", f"انبار {warehouse.label}")
    return success(warehouse_to_dict(warehouse), status=201)


@api_view("PUT", "DELETE")
def warehouse_detail(request, pk):
    denied = _require_admin(request.user)
    if denied:
        return denied
    warehouse = Warehouse.objects.filter(pk=pk).first()
    if warehouse is None:
        return fail("انبار یافت نشد", status=404)
    if request.method == "DELETE":
        warehouse.is_active = False
        warehouse.save(update_fields=["is_active"])
        log_action(request.user, "update", f"غیرفعال‌سازی انبار {warehouse.label}")
        return success(warehouse_to_dict(warehouse))
    try:
        warehouse = update_warehouse(warehouse, parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(request.user, "update", f"ویرایش انبار {warehouse.label}")
    return success(warehouse_to_dict(warehouse))


@api_view("GET")
def cycle_watch(request):
    seed_order_cycle()
    flags = cycle_flags_for_user(request.user)
    if not flags["can_watch_cycle"]:
        return fail("Permission denied", status=403)
    scope = (request.GET.get("scope") or "shop_crm").strip()
    if scope == "fulfillment" and not (
        flags["is_fulfillment_supervisor"] or is_system_admin(request.user) or flags["can_watch_cycle"]
    ):
        return fail("Permission denied", status=403)
    return _sale_page(watch_queryset(request.user, scope=scope), request, request.user)


@api_view("GET")
def cycle_warehouse_orders(request):
    if not can_list_warehouse_orders(request.user):
        return fail("Permission denied", status=403)
    return _sale_page(warehouse_order_queryset(request.user), request, request.user)


@api_view("GET")
def cycle_pickup_orders(request):
    if not can_list_pickup_orders(request.user):
        return fail("Permission denied", status=403)
    return _sale_page(pickup_order_queryset(request.user), request, request.user)
