"""مدیریت فروشندگان و مدیران — فقط نام و شعبه، بدون نام کاربری."""

from api.helpers import api_view, fail, parse_json, success
from auth.branches import BRANCH_LABELS
from auth.permissions import has_permission
from backend.models import Seller
from logic.audit import log_action
from logic.staff import (
    can_view_staff,
    create_staff,
    deactivate_staff,
    delete_perm_for_kind,
    list_staff,
    manage_perm_for_kind,
    parse_staff_kind,
    seller_to_dict,
    staff_kind_label,
)


@api_view("GET", "POST")
def staff_list(request):
    if request.method == "GET":
        staff_kind = parse_staff_kind(request.GET.get("kind"), Seller.STAFF_KIND_SELLER)
        if not can_view_staff(request.user, staff_kind):
            return fail("Permission denied", status=403)
        branch = (request.GET.get("branch") or "").strip()
        return success(list_staff(staff_kind, branch=branch))

    data = parse_json(request)
    staff_kind = parse_staff_kind(data.get("staff_kind"), Seller.STAFF_KIND_SELLER)

    if not has_permission(request.user, manage_perm_for_kind(staff_kind)):
        return fail("Permission denied", status=403)

    try:
        seller = create_staff(
            full_name=data.get("full_name"),
            branch=data.get("branch"),
            phone=data.get("phone") or "",
            staff_kind=staff_kind,
        )
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "create",
        f"افزودن {staff_kind_label(staff_kind)} {seller.full_name} به {BRANCH_LABELS.get(seller.branch, seller.branch)}",
        entity_type="Seller",
        entity_id=seller.id,
    )
    return success(seller_to_dict(seller), status=201)


@api_view("DELETE")
def staff_detail(request, pk):
    try:
        seller = Seller.objects.get(pk=pk)
    except Seller.DoesNotExist:
        return fail("Seller not found", status=404)

    if not has_permission(request.user, delete_perm_for_kind(seller.staff_kind)):
        return fail("Permission denied", status=403)

    deactivate_staff(seller)
    log_action(
        request.user,
        "delete",
        f"غیرفعال‌سازی {staff_kind_label(seller.staff_kind)} {seller.full_name}",
        entity_type="Seller",
        entity_id=seller.id,
    )
    return success({"deleted": True})
