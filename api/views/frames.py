"""API کلاف — کاتالوگ کلاف و سرویس مبلمان."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import MANAGE_FRAMES, VIEW_FRAMES, has_permission
from backend.models import Frame
from logic.audit import log_action
from logic.frame_materials import preview_frame_requirements
from logic.frames import (
    component_type_labels,
    create_frame,
    delete_frame,
    design_style_labels,
    filter_frames,
    frame_to_dict,
    rule_key_labels,
    update_frame,
    wood_type_labels,
)
from logic.furniture_worksets import (
    allowed_arms,
    arm_style_labels,
    create_product_from_frame,
    piece_kind_labels,
)
from logic.products import product_to_dict


def _can_view(user):
    return has_permission(user, VIEW_FRAMES)


def _can_manage(user):
    return has_permission(user, MANAGE_FRAMES)


@api_view("GET")
def frame_options(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    return success(
        {
            "design_styles": [{"value": k, "label": v} for k, v in design_style_labels().items()],
            "wood_types": [{"value": k, "label": v} for k, v in wood_type_labels().items()],
            "component_types": [{"value": k, "label": v} for k, v in component_type_labels().items()],
            "rule_keys": [{"value": k, "label": v} for k, v in rule_key_labels().items()],
            "piece_kinds": [{"value": k, "label": v} for k, v in piece_kind_labels().items()],
            "arm_styles": [{"value": k, "label": v} for k, v in arm_style_labels().items()],
            "allowed_arms": {kind: list(styles) for kind, styles in allowed_arms().items()},
        }
    )


@api_view("GET", "POST")
def frame_list(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)

    if request.method == "GET":
        search = (request.GET.get("search") or "").strip()
        workset_id = request.GET.get("workset_id")
        include_inactive = request.GET.get("include_inactive") == "1" and _can_manage(request.user)
        qs = Frame.objects.filter(is_deleted=False)
        qs = filter_frames(
            qs,
            search=search,
            active_only=not include_inactive,
            workset_id=workset_id or None,
        )
        from logic.pagination import paginate

        page, meta = paginate(qs, request.GET)
        return success({"results": [frame_to_dict(f) for f in page], **meta})

    if not _can_manage(request.user):
        return fail("Permission denied", status=403)

    try:
        data = parse_json(request)
        frame = create_frame(data)
        log_action(request.user, "create", f"کلاف: {frame.name}")
        return success(frame_to_dict(frame), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def frame_detail(request, pk):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)

    frame = Frame.objects.filter(pk=pk, is_deleted=False).first()
    if not frame:
        return fail("کلاف یافت نشد.", status=404)

    if request.method == "GET":
        qs = filter_frames(Frame.objects.filter(pk=pk), active_only=False)
        frame = qs.first()
        return success(frame_to_dict(frame))

    if not _can_manage(request.user):
        return fail("Permission denied", status=403)

    if request.method == "DELETE":
        delete_frame(frame)
        log_action(request.user, "delete", f"کلاف: {frame.name}")
        return success({"id": pk})

    try:
        data = parse_json(request)
        update_frame(frame, data)
        log_action(request.user, "update", f"کلاف: {frame.name}")
        qs = filter_frames(Frame.objects.filter(pk=frame.id), active_only=False)
        return success(frame_to_dict(qs.first()))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "POST")
def frame_requirements_preview(request, pk):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)

    frame = Frame.objects.filter(pk=pk, is_deleted=False).first()
    if not frame:
        return fail("کلاف یافت نشد.", status=404)

    if request.method == "POST":
        data = parse_json(request)
    else:
        data = {
            "frame_model_id": request.GET.get("frame_model_id"),
            "quantity": request.GET.get("quantity") or 1,
            "frame_config": {},
        }

    frame_model_id = data.get("frame_model_id")
    frame_config = data.get("frame_config") if isinstance(data.get("frame_config"), dict) else {}
    quantity = data.get("quantity") or 1

    try:
        requirements = preview_frame_requirements(
            frame,
            frame_model_id=frame_model_id,
            frame_config=frame_config,
            quantity=quantity,
        )
        return success({"requirements": requirements})
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("POST")
def frame_create_product(request, pk):
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    frame = Frame.objects.filter(pk=pk, is_deleted=False).select_related("workset").first()
    if not frame:
        return fail("کلاف یافت نشد.", status=404)
    try:
        product = create_product_from_frame(frame, parse_json(request))
        log_action(request.user, "create", f"محصول از کلاف {frame.name}: {product.name}")
        from api.views.products import _product_audience

        return success(product_to_dict(product, audience=_product_audience(request.user)), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)
