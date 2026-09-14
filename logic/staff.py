"""منطق مدیریت فروشندگان و مدیران (Seller)."""

from django.db.models import Q

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


def seller_to_dict(seller):
    return {
        "id": seller.id,
        "full_name": seller.full_name,
        "branch": seller.branch_id,
        "branch_label": BRANCH_LABELS.get(seller.branch_id, "—"),
        "phone": seller.phone,
        "has_login": seller.user_id is not None,
        "is_active": seller.is_active,
        "staff_kind": seller.staff_kind,
        "staff_kind_display": seller.get_staff_kind_display(),
    }


def parse_staff_kind(value, default=Seller.STAFF_KIND_SELLER):
    kind = (value or default).strip()
    valid = {Seller.STAFF_KIND_SELLER, Seller.STAFF_KIND_MANAGER}
    if kind not in valid:
        return default
    return kind


def view_perm_for_kind(staff_kind):
    if staff_kind == Seller.STAFF_KIND_MANAGER:
        return VIEW_MANAGERS
    return VIEW_SELLERS


def manage_perm_for_kind(staff_kind):
    if staff_kind == Seller.STAFF_KIND_MANAGER:
        return MANAGE_MANAGERS
    return MANAGE_STAFF


def delete_perm_for_kind(staff_kind):
    if staff_kind == Seller.STAFF_KIND_MANAGER:
        return DELETE_MANAGERS
    return DELETE_STAFF


def can_view_staff(user, staff_kind):
    if has_permission(user, view_perm_for_kind(staff_kind)):
        return True
    if has_permission(user, manage_perm_for_kind(staff_kind)):
        return True
    if staff_kind == Seller.STAFF_KIND_SELLER and has_permission(user, VIEW_ATTENDANCE):
        return True
    return False


def list_staff(staff_kind, branch="", params=None):
    params = params or {}
    qs = Seller.objects.filter(is_active=True, staff_kind=staff_kind).order_by("full_name")
    if branch:
        qs = qs.filter(branch=branch)
    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(Q(full_name__icontains=search) | Q(phone__icontains=search))
    from logic.pagination import paginate

    page, meta = paginate(qs, params)
    return {
        "branches": [{"value": v, "label": l} for v, l in BRANCH_CHOICES],
        "results": [seller_to_dict(s) for s in page],
        **meta,
    }


def create_staff(full_name, branch=None, phone="", staff_kind=None):
    full_name = (full_name or "").strip()
    branch = (branch or DEFAULT_BRANCH).strip()
    phone = (phone or "").strip()
    staff_kind = parse_staff_kind(staff_kind, Seller.STAFF_KIND_SELLER)

    if not full_name:
        raise ValueError("full_name is required")
    if branch not in dict(BRANCH_CHOICES):
        raise ValueError("Invalid branch")

    return Seller.objects.create(
        full_name=full_name,
        branch_id=branch,
        phone=phone,
        staff_kind=staff_kind,
    )


def deactivate_staff(seller):
    seller.is_active = False
    seller.save(update_fields=["is_active"])
    return seller


def staff_kind_label(staff_kind):
    return "مدیر" if staff_kind == Seller.STAFF_KIND_MANAGER else "فروشنده"
