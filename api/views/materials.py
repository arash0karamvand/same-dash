"""API متریال — کاتالوگ مواد اولیه."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import (
    APPROVE_MATERIALS,
    CREATE_MATERIALS,
    MANAGE_MATERIALS,
    VIEW_MATERIALS,
    can_view_costs,
    has_permission,
)
from backend.models import Material, MaterialStocktake
from logic.audit import log_action
from logic.material_reports import warehouse_report
from logic.material_stocktake import close_stocktake, create_stocktake, list_stocktakes, stocktake_sheet, update_stocktake
from logic.materials import (
    approve_material,
    create_material,
    filter_materials,
    material_to_dict,
    mask_cost_fields,
    reject_material,
    update_material,
)


def _can_view(user):
    return has_permission(user, VIEW_MATERIALS)


def _can_create(user):
    return (
        has_permission(user, CREATE_MATERIALS)
        or has_permission(user, APPROVE_MATERIALS)
        or has_permission(user, MANAGE_MATERIALS)
    )


def _can_approve(user):
    return has_permission(user, APPROVE_MATERIALS) or has_permission(user, MANAGE_MATERIALS)


def _serialize(material, user):
    return material_to_dict(material, include_cost=can_view_costs(user))


@api_view("GET")
def material_reports(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    try:
        payload = warehouse_report(request.GET)
        return success(payload if can_view_costs(request.user) else mask_cost_fields(payload))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "POST")
def material_list(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)

    if request.method == "GET":
        search = (request.GET.get("search") or "").strip()
        approval_status = (request.GET.get("approval_status") or "").strip()
        include_pending = request.GET.get("include_pending") == "1"
        include_inactive = request.GET.get("include_inactive") == "1" and _can_approve(request.user)
        approved_only = request.GET.get("approved_only") == "1" or (
            not include_pending and not approval_status and not _can_approve(request.user)
        )

        qs = Material.objects.filter(is_deleted=False).select_related("submitted_by", "approved_by")
        if not include_inactive:
            if include_pending or _can_approve(request.user):
                qs = qs.filter(
                    approval_status__in=[
                        Material.APPROVAL_APPROVED,
                        Material.APPROVAL_PENDING,
                        Material.APPROVAL_REJECTED,
                    ]
                )
            else:
                qs = qs.filter(is_active=True)
        qs = filter_materials(
            qs,
            search=search,
            active_only=False,
            approved_only=approved_only,
            approval_status=approval_status or None,
            usage_kind=(request.GET.get("usage_kind") or "").strip() or None,
        )
        from logic.pagination import paginate

        page, meta = paginate(qs, request.GET)
        return success({"results": [_serialize(m, request.user) for m in page], **meta})

    if not _can_create(request.user):
        return fail("Permission denied", status=403)

    try:
        data = parse_json(request)
        # تایید خودکار فقط با «ثبت مستقیم» از بخش اداری — نه از کارخانه
        auto_approve = _can_approve(request.user) and bool(data.get("auto_approve"))
        material = create_material(
            data,
            user=request.user,
            auto_approve=auto_approve,
        )
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "create",
        f"متریال: {material.name}",
        entity_type="Material",
        entity_id=material.id,
    )
    return success(_serialize(material, request.user), status=201)


@api_view("GET", "PUT", "DELETE")
def material_detail(request, pk):
    try:
        material = Material.objects.select_related("submitted_by", "approved_by").get(
            pk=pk, is_deleted=False
        )
    except Material.DoesNotExist:
        return fail("Material not found", status=404)

    if not _can_view(request.user):
        return fail("Permission denied", status=403)

    if request.method == "GET":
        return success(_serialize(material, request.user))

    if request.method == "DELETE":
        if not _can_approve(request.user):
            return fail("فقط اداری می‌تواند متریال را حذف کند.", status=403)
        if material.product_links.exists():
            return fail("این متریال در محصولات استفاده شده و قابل حذف نیست.", status=400)
        material.soft_delete()
        log_action(
            request.user,
            "delete",
            f"حذف متریال: {material.name}",
            entity_type="Material",
            entity_id=material.id,
        )
        return success({"deleted": True})

    if not _can_approve(request.user):
        return fail("فقط اداری می‌تواند متریال را ویرایش کند.", status=403)

    try:
        material = update_material(material, parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "update",
        f"ویرایش متریال: {material.name}",
        entity_type="Material",
        entity_id=material.id,
    )
    return success(_serialize(material, request.user))


@api_view("POST")
def material_approve(request, pk):
    if not _can_approve(request.user):
        return fail("Permission denied", status=403)
    try:
        material = Material.objects.get(pk=pk, is_deleted=False)
    except Material.DoesNotExist:
        return fail("Material not found", status=404)
    if material.approval_status == Material.APPROVAL_APPROVED:
        return success(_serialize(material, request.user))
    material = approve_material(material, request.user)
    log_action(
        request.user,
        "approve",
        f"تایید متریال: {material.name}",
        entity_type="Material",
        entity_id=material.id,
    )
    return success(_serialize(material, request.user))


@api_view("POST")
def material_reject(request, pk):
    if not _can_approve(request.user):
        return fail("Permission denied", status=403)
    try:
        material = Material.objects.get(pk=pk, is_deleted=False)
    except Material.DoesNotExist:
        return fail("Material not found", status=404)
    data = parse_json(request)
    material = reject_material(material, request.user, data.get("reason") or "")
    log_action(
        request.user,
        "reject",
        f"رد متریال: {material.name}",
        entity_type="Material",
        entity_id=material.id,
    )
    return success(_serialize(material, request.user))


def _stocktake_or_404(pk):
    return MaterialStocktake.objects.filter(pk=pk).first()


@api_view("GET", "POST")
def material_stocktake_list(request):
    if request.method == "GET":
        if not _can_view(request.user):
            return fail("Permission denied", status=403)
        return success(list_stocktakes())
    if not _can_create(request.user):
        return fail("Permission denied", status=403)
    try:
        sheet = create_stocktake(parse_json(request), request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(request.user, "create", f"برگه انبارگردانی متریال #{sheet['id']}")
    return success(sheet, status=201)


@api_view("GET", "PUT")
def material_stocktake_detail(request, pk):
    sheet = _stocktake_or_404(pk)
    if sheet is None:
        return fail("برگه انبارگردانی یافت نشد.", status=404)
    if request.method == "GET":
        if not _can_view(request.user):
            return fail("Permission denied", status=403)
        return success(stocktake_sheet(sheet))
    if not _can_create(request.user):
        return fail("Permission denied", status=403)
    try:
        data = update_stocktake(sheet, parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(request.user, "update", f"ویرایش برگه انبارگردانی #{sheet.id}")
    return success(data)


@api_view("POST")
def material_stocktake_close(request, pk):
    if not _can_create(request.user):
        return fail("Permission denied", status=403)
    sheet = _stocktake_or_404(pk)
    if sheet is None:
        return fail("برگه انبارگردانی یافت نشد.", status=404)
    data = close_stocktake(sheet, user=request.user)
    log_action(request.user, "update", f"بستن برگه انبارگردانی #{sheet.id}")
    return success(data)
