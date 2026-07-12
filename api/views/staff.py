"""مدیریت فروشندگان و مدیران — فقط نام و شعبه، بدون نام کاربری."""

from api.helpers import api_view, fail, parse_json, success
from auth.branches import BRANCH_CHOICES, BRANCH_LABELS, DEFAULT_BRANCH
from auth.permissions import (
    DELETE_MANAGERS,
    DELETE_STAFF,
    MANAGE_MANAGERS,
    MANAGE_STAFF,
    VIEW_ATTENDANCE,
    VIEW_MANAGERS,
    VIEW_SELLERS,
    has_permission,
)
from backend.models import Seller
from logic.audit import log_action


def _seller_to_dict(seller):
    return {
        "id": seller.id,
        "full_name": seller.full_name,
        "branch": seller.branch,
        "branch_label": BRANCH_LABELS.get(seller.branch, "—"),
        "phone": seller.phone,
        "has_login": seller.user_id is not None,
        "is_active": seller.is_active,
        "staff_kind": seller.staff_kind,
        "staff_kind_display": seller.get_staff_kind_display(),
    }


def _parse_staff_kind(value, default=Seller.STAFF_KIND_SELLER):
    kind = (value or default).strip()
    valid = {Seller.STAFF_KIND_SELLER, Seller.STAFF_KIND_MANAGER}
    if kind not in valid:
        return default
    return kind


def _view_perm_for_kind(staff_kind):
    if staff_kind == Seller.STAFF_KIND_MANAGER:
        return VIEW_MANAGERS
    return VIEW_SELLERS


def _manage_perm_for_kind(staff_kind):
    if staff_kind == Seller.STAFF_KIND_MANAGER:
        return MANAGE_MANAGERS
    return MANAGE_STAFF


def _delete_perm_for_kind(staff_kind):
    if staff_kind == Seller.STAFF_KIND_MANAGER:
        return DELETE_MANAGERS
    return DELETE_STAFF


def _can_view_staff(user, staff_kind):
    if has_permission(user, _view_perm_for_kind(staff_kind)):
        return True
    if has_permission(user, _manage_perm_for_kind(staff_kind)):
        return True
    if staff_kind == Seller.STAFF_KIND_SELLER and has_permission(user, VIEW_ATTENDANCE):
        return True
    return False


@api_view("GET", "POST")
def staff_list(request):
    if request.method == "GET":
        staff_kind = _parse_staff_kind(request.GET.get("kind"), Seller.STAFF_KIND_SELLER)
        if not _can_view_staff(request.user, staff_kind):
            return fail("Permission denied", status=403)

        branch = (request.GET.get("branch") or "").strip()
        qs = Seller.objects.filter(is_active=True, staff_kind=staff_kind).order_by("full_name")
        if branch:
            qs = qs.filter(branch=branch)

        return success({
            "branches": [{"value": v, "label": l} for v, l in BRANCH_CHOICES],
            "results": [_seller_to_dict(s) for s in qs],
        })

    data = parse_json(request)
    full_name = (data.get("full_name") or "").strip()
    branch = (data.get("branch") or DEFAULT_BRANCH).strip()
    phone = (data.get("phone") or "").strip()
    staff_kind = _parse_staff_kind(data.get("staff_kind"), Seller.STAFF_KIND_SELLER)

    if not has_permission(request.user, _manage_perm_for_kind(staff_kind)):
        return fail("Permission denied", status=403)

    if not full_name:
        return fail("full_name is required", status=400)
    if branch not in dict(BRANCH_CHOICES):
        return fail("Invalid branch", status=400)

    seller = Seller.objects.create(
        full_name=full_name,
        branch=branch,
        phone=phone,
        staff_kind=staff_kind,
    )
    kind_label = "مدیر" if staff_kind == Seller.STAFF_KIND_MANAGER else "فروشنده"
    log_action(
        request.user,
        "create",
        f"افزودن {kind_label} {full_name} به {BRANCH_LABELS.get(branch, branch)}",
        entity_type="Seller",
        entity_id=seller.id,
    )
    return success(_seller_to_dict(seller), status=201)


@api_view("DELETE")
def staff_detail(request, pk):
    try:
        seller = Seller.objects.get(pk=pk)
    except Seller.DoesNotExist:
        return fail("Seller not found", status=404)

    if not has_permission(request.user, _delete_perm_for_kind(seller.staff_kind)):
        return fail("Permission denied", status=403)

    seller.is_active = False
    seller.save(update_fields=["is_active"])
    kind_label = "مدیر" if seller.staff_kind == Seller.STAFF_KIND_MANAGER else "فروشنده"
    log_action(
        request.user,
        "delete",
        f"غیرفعال‌سازی {kind_label} {seller.full_name}",
        entity_type="Seller",
        entity_id=seller.id,
    )
    return success({"deleted": True})
