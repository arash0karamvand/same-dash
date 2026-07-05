"""مدیریت فروشندگان — فقط نام و شعبه، بدون نام کاربری."""

from api.helpers import api_view, fail, parse_json, success
from auth.branches import BRANCH_CHOICES, BRANCH_LABELS, DEFAULT_BRANCH
from auth.permissions import DELETE_STAFF, MANAGE_STAFF, VIEW_ATTENDANCE, has_permission
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
    }


@api_view("GET", "POST")
def staff_list(request):
    if request.method == "GET":
        if not has_permission(request.user, VIEW_ATTENDANCE) and not has_permission(
            request.user, MANAGE_STAFF
        ):
            return fail("Permission denied", status=403)

        branch = (request.GET.get("branch") or "").strip()
        qs = Seller.objects.filter(is_active=True).order_by("full_name")
        if branch:
            qs = qs.filter(branch=branch)

        return success({
            "branches": [{"value": v, "label": l} for v, l in BRANCH_CHOICES],
            "results": [_seller_to_dict(s) for s in qs],
        })

    if not has_permission(request.user, MANAGE_STAFF):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    full_name = (data.get("full_name") or "").strip()
    branch = (data.get("branch") or DEFAULT_BRANCH).strip()
    phone = (data.get("phone") or "").strip()

    if not full_name:
        return fail("full_name is required", status=400)
    if branch not in dict(BRANCH_CHOICES):
        return fail("Invalid branch", status=400)

    seller = Seller.objects.create(full_name=full_name, branch=branch, phone=phone)
    log_action(
        request.user,
        "create",
        f"افزودن فروشنده {full_name} به {BRANCH_LABELS.get(branch, branch)}",
        entity_type="Seller",
        entity_id=seller.id,
    )
    return success(_seller_to_dict(seller), status=201)


@api_view("DELETE")
def staff_detail(request, pk):
    if not has_permission(request.user, DELETE_STAFF):
        return fail("Permission denied", status=403)

    try:
        seller = Seller.objects.get(pk=pk)
    except Seller.DoesNotExist:
        return fail("Seller not found", status=404)

    seller.is_active = False
    seller.save(update_fields=["is_active"])
    log_action(
        request.user,
        "delete",
        f"غیرفعال‌سازی فروشنده {seller.full_name}",
        entity_type="Seller",
        entity_id=seller.id,
    )
    return success({"deleted": True})
