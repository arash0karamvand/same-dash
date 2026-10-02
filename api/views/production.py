"""Versioned BOM and production-run APIs."""

from django.core.exceptions import PermissionDenied, ValidationError

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import (
    MANAGE_FACTORY_ORDERS,
    MANAGE_PRODUCTS,
    VIEW_FACTORY_ORDERS,
    VIEW_PRODUCTS,
    can_view_costs,
    has_permission,
)
from backend.models import (
    BOMVersion,
    FulfillmentPlanLine,
    Material,
    MaterialRequirement,
    ProductionEvent,
    ProductionRun,
    Product,
)
from logic.production import (
    complete_run,
    consume_extra,
    consume_requirement,
    create_run,
    publish_bom_version,
    record_scrap,
    release_run,
    return_material,
    run_to_dict,
)


def _view_allowed(user):
    return has_permission(user, VIEW_FACTORY_ORDERS) or has_permission(user, VIEW_PRODUCTS)


def _manage_allowed(user):
    return has_permission(user, MANAGE_FACTORY_ORDERS)


def _run_payload(run, user):
    from logic.materials import mask_cost_fields

    payload = run_to_dict(run)
    return payload if can_view_costs(user) else mask_cost_fields(payload)


def _bom_to_dict(row):
    return {
        "uuid": str(row.uuid),
        "product_id": row.product_id,
        "version": row.version,
        "status": row.status,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "published_by": row.published_by_id,
        "lines": [
            {
                "id": line.pk,
                "material_id": line.material_id,
                "material": line.material.name,
                "quantity": float(line.quantity),
                "normal_spoilage_rate": float(line.normal_spoilage_rate),
                "source_kind": line.source_kind,
                "source_reference": line.source_reference,
            }
            for line in row.lines.select_related("material")
        ],
    }


@api_view("GET")
def bom_versions(request):
    if not _view_allowed(request.user):
        return fail("Permission denied", status=403)
    rows = BOMVersion.objects.select_related("product", "published_by")
    if request.GET.get("product_id"):
        rows = rows.filter(product_id=request.GET["product_id"])
    return success({"results": [_bom_to_dict(row) for row in rows]})


@api_view("POST")
def bom_publish(request, product_id):
    if not has_permission(request.user, MANAGE_PRODUCTS):
        return fail("Permission denied", status=403)
    product = Product.objects.filter(pk=product_id, is_deleted=False, is_active=True).first()
    if product is None:
        return fail("Product not found", status=404)
    try:
        row = publish_bom_version(product, user=request.user)
    except (ValueError, ValidationError) as exc:
        return fail(str(exc), status=400)
    return success(_bom_to_dict(row), status=201)


@api_view("GET", "POST")
def production_runs(request):
    if not _view_allowed(request.user):
        return fail("Permission denied", status=403)
    if request.method == "GET":
        rows = ProductionRun.objects.select_related(
            "production_order", "fulfillment_plan_line", "product", "variant",
            "bom_version", "warehouse",
        )
        if request.GET.get("status"):
            rows = rows.filter(status=request.GET["status"])
        if request.GET.get("sale_id"):
            rows = rows.filter(sale_id=request.GET["sale_id"])
        return success({"results": [_run_payload(row, request.user) for row in rows]})
    if not _manage_allowed(request.user):
        return fail("Permission denied", status=403)
    data = parse_json(request)
    line = FulfillmentPlanLine.objects.filter(uuid=data.get("fulfillment_plan_line_uuid")).first()
    if line is None:
        return fail("Fulfillment plan line not found", status=404)
    try:
        run = create_run(line, user=request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(_run_payload(run, request.user), status=201)


def _run(run_uuid):
    return ProductionRun.objects.filter(uuid=run_uuid).select_related(
        "production_order", "fulfillment_plan_line", "product", "variant",
        "bom_version", "warehouse",
    ).first()


@api_view("GET")
def production_run_detail(request, run_uuid):
    if not _view_allowed(request.user):
        return fail("Permission denied", status=403)
    run = _run(run_uuid)
    return success(_run_payload(run, request.user)) if run else fail("Production run not found", status=404)


def _run_action(request, run_uuid, action):
    if not _manage_allowed(request.user):
        return fail("Permission denied", status=403)
    run = _run(run_uuid)
    if run is None:
        return fail("Production run not found", status=404)
    try:
        result = action(run, parse_json(request))
    except PermissionDenied as exc:
        return fail(str(exc), status=403)
    except (ValueError, ValidationError) as exc:
        return fail(str(exc), status=400)
    run.refresh_from_db()
    return success(_run_payload(run, request.user) | {"event_uuid": str(result.uuid) if result else None})


@api_view("POST")
def production_run_release(request, run_uuid):
    return _run_action(request, run_uuid, lambda run, _data: (release_run(run, user=request.user), None)[1])


@api_view("POST")
def production_requirement_consume(request, run_uuid, requirement_id):
    def action(run, data):
        req = MaterialRequirement.objects.filter(pk=requirement_id, run=run).first()
        if req is None:
            raise ValueError("Production requirement not found.")
        return consume_requirement(
            req, user=request.user, idempotency_key=data.get("idempotency_key")
        )

    return _run_action(request, run_uuid, action)


@api_view("POST")
def production_extra_consume(request, run_uuid):
    def action(run, data):
        material = Material.objects.filter(pk=data.get("material_id"), is_deleted=False).first()
        if material is None:
            raise ValueError("Material not found.")
        return consume_extra(
            run, material, data.get("quantity"), reason=data.get("reason") or "",
            user=request.user, idempotency_key=data.get("idempotency_key"),
        )

    return _run_action(request, run_uuid, action)


@api_view("POST")
def production_return(request, run_uuid):
    def action(run, data):
        original = ProductionEvent.objects.filter(
            uuid=data.get("original_event_uuid"), run=run
        ).first()
        if original is None:
            raise ValueError("Original production event not found.")
        return return_material(
            original, data.get("quantity"), reason=data.get("reason") or "",
            user=request.user, idempotency_key=data.get("idempotency_key"),
        )

    return _run_action(request, run_uuid, action)


@api_view("POST")
def production_scrap(request, run_uuid):
    def action(run, data):
        material = Material.objects.filter(pk=data.get("material_id"), is_deleted=False).first()
        if material is None:
            raise ValueError("Material not found.")
        return record_scrap(
            run, material, data.get("quantity"), reason=data.get("reason") or "",
            user=request.user, idempotency_key=data.get("idempotency_key"),
        )

    return _run_action(request, run_uuid, action)


@api_view("POST")
def production_complete(request, run_uuid):
    return _run_action(
        request,
        run_uuid,
        lambda run, data: complete_run(
            run,
            overhead_cost=data.get("overhead_cost") or 0,
            user=request.user,
            idempotency_key=data.get("idempotency_key"),
        ),
    )
