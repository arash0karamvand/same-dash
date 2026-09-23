"""API دست مبلمان."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import MANAGE_FRAMES, VIEW_FRAMES, VIEW_PRODUCTS, VIEW_SALES, has_permission
from logic.audit import log_action
from backend.models import Frame, FurnitureWorkset
from logic.dynamic_choices import choice_options
from logic.furniture_worksets import (
    allowed_arms,
    arm_style_labels,
    create_workset,
    delete_workset,
    filter_worksets,
    piece_kind_labels,
    piece_slots,
    products_for_workset,
    update_workset,
    workset_to_dict,
)
from logic.products import product_to_dict


def _can_view(user):
    return (
        has_permission(user, VIEW_FRAMES)
        or has_permission(user, VIEW_PRODUCTS)
        or has_permission(user, VIEW_SALES)
    )


def _can_manage(user):
    return has_permission(user, MANAGE_FRAMES)


@api_view("GET")
def workset_options(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    design_styles = choice_options("frame_design_style") or [
        {"value": k, "label": v} for k, v in Frame.DESIGN_STYLE_CHOICES
    ]
    return success(
        {
            "piece_kinds": [{"value": k, "label": v} for k, v in piece_kind_labels().items()],
            "arm_styles": [{"value": k, "label": v} for k, v in arm_style_labels().items()],
            "allowed_arms": {kind: list(styles) for kind, styles in allowed_arms().items()},
            "piece_slots": piece_slots(),
            "design_styles": design_styles,
        }
    )


@api_view("GET", "POST")
def workset_list(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)

    if request.method == "GET":
        search = (request.GET.get("search") or "").strip()
        include_inactive = request.GET.get("include_inactive") == "1" and _can_manage(request.user)
        qs = FurnitureWorkset.objects.filter(is_deleted=False)
        qs = filter_worksets(qs, search=search, active_only=not include_inactive)
        from logic.pagination import paginate

        page, meta = paginate(qs, request.GET)
        return success({"results": [workset_to_dict(w) for w in page], **meta})

    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    try:
        workset = create_workset(parse_json(request))
        log_action(request.user, "create", f"دست مبلمان: {workset.name}")
        return success(workset_to_dict(workset), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def workset_detail(request, pk):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    workset = FurnitureWorkset.objects.filter(pk=pk, is_deleted=False).first()
    if not workset:
        return fail("دست یافت نشد.", status=404)

    if request.method == "GET":
        return success(workset_to_dict(workset, include_frames=True))

    if not _can_manage(request.user):
        return fail("Permission denied", status=403)

    if request.method == "DELETE":
        delete_workset(workset)
        log_action(request.user, "delete", f"دست مبلمان: {workset.name}")
        return success({"id": pk})

    try:
        update_workset(workset, parse_json(request))
        log_action(request.user, "update", f"دست مبلمان: {workset.name}")
        return success(workset_to_dict(workset, include_frames=True))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET")
def workset_products(request, pk):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    workset = FurnitureWorkset.objects.filter(pk=pk, is_deleted=False).first()
    if not workset:
        return fail("دست یافت نشد.", status=404)
    from api.views.products import _product_audience

    audience = _product_audience(request.user)
    products = products_for_workset(workset)
    return success(
        {
            "workset": workset_to_dict(workset),
            "results": [product_to_dict(p, audience=audience) for p in products],
        }
    )
