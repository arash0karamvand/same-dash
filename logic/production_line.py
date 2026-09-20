"""اتوماسیون خط تولید — ساخت کار کارگاه‌ها هنگام دریافت سفارش کارخانه."""

from decimal import Decimal

from backend.models import (
    BetaAssemblyJob,
    BetaCarpentryWorkshop,
    BetaClearanceJob,
    BetaCushionJob,
    BetaFabricNeed,
    BetaFoamJob,
    BetaPaintOrder,
    BetaUpholsteryJob,
)
from logic import beta_workshops as L
from logic.receive_kinds import clearance_destination
from logic.workshop_recipes import (
    PIPELINE_END_ASSEMBLY,
    build_workset_from_product,
)
from logic.furniture_worksets import piece_label


def _line_workset(line):
    config = line.workset_config or {}
    if config:
        return config
    if line.product_id:
        config = build_workset_from_product(line.product)
        if config:
            line.workset_config = config
            line.save(update_fields=["workset_config"])
    return config or {}


def _fabric_meters(block):
    total = Decimal(0)
    for row in (block or {}).get("materials") or []:
        total += Decimal(str(row.get("quantity") or 0))
    return total


def _has_recipe(block):
    return bool(block and (block.get("name") or block.get("id") or block.get("materials")))


def _spawn_units(line):
    workset = _line_workset(line)
    pieces = workset.get("pieces") or []
    line_qty = int(line.quantity or 1)
    if pieces:
        units = []
        for piece in pieces:
            label = piece.get("piece_label") or piece_label(piece.get("piece_kind"), piece.get("arm_style"))
            unit = dict(workset)
            unit.update(piece)
            unit["product_name"] = f"{line.product_name} — {label}" if label else line.product_name
            unit["line_quantity"] = line_qty * int(piece.get("quantity") or 1)
            units.append(unit)
        return units
    unit = dict(workset)
    unit["product_name"] = line.product_name
    unit["line_quantity"] = line_qty
    return [unit]


def spawn_workshop_jobs_for_sale(sale):
    """برای هر جزء دست‌کار یک کار کارگاه می‌سازد — تکراری نمی‌سازد."""
    created = []
    warnings = []
    lines = list(sale.line_items.select_related("frame", "product", "furniture_workset").all())
    if not lines:
        return {"created": created, "warnings": warnings}

    default_workshop = (
        BetaCarpentryWorkshop.objects.filter(is_active=True, kind=BetaCarpentryWorkshop.KIND_INTERNAL)
        .order_by("id")
        .first()
        or BetaCarpentryWorkshop.objects.filter(is_active=True).order_by("id").first()
    )

    has_frame = any(
        line.frame_id
        or getattr(line, "furniture_workset_id", None)
        or _line_workset(line).get("frame_id")
        or _line_workset(line).get("pieces")
        or _line_workset(line).get("furniture_workset_id")
        for line in lines
    )
    if has_frame and not sale.beta_carpentry_orders.exists():
        if default_workshop:
            primary = next(
                (
                    line
                    for line in lines
                    if line.frame_id
                    or getattr(line, "furniture_workset_id", None)
                    or _line_workset(line).get("frame_id")
                    or _line_workset(line).get("pieces")
                ),
                lines[0],
            )
            workset = _line_workset(primary)
            piece_qty = sum(int(unit.get("line_quantity") or 1) for unit in _spawn_units(primary))
            L.create_carpentry_order(
                {
                    "workshop_id": default_workshop.id,
                    "sale_id": sale.id,
                    "frame_id": primary.frame_id or workset.get("frame_id"),
                    "product_name": primary.product_name,
                    "quantity": piece_qty or int(primary.quantity or 1),
                }
            )
            created.append("carpentry")
        else:
            warnings.append("واحد نجاری فعال تعریف نشده؛ دستور کلاف ساخته نشد.")

    wants_assembly = False
    for line in lines:
        for unit in _spawn_units(line):
            product_name = unit.get("product_name") or line.product_name
            needs_paint = unit.get("needs_paint", True)
            pipeline_end = unit.get("pipeline_end") or "upholstery"
            if pipeline_end == PIPELINE_END_ASSEMBLY:
                wants_assembly = True

            paint = unit.get("paint") or {}
            if needs_paint and _has_recipe(paint):
                if not BetaPaintOrder.objects.filter(sale=sale, product_name=product_name).exists():
                    L.create_paint_order(
                        {
                            "sale_id": sale.id,
                            "product_name": product_name,
                            "color_name": paint.get("color_name") or paint.get("name") or "",
                            "kind": BetaPaintOrder.KIND_NORMAL,
                        }
                    )
                    created.append("paint")

            fabric = unit.get("fabric") or {}
            if _has_recipe(fabric):
                if not BetaFabricNeed.objects.filter(sale=sale, product_name=product_name).exists():
                    meters = _fabric_meters(fabric) * Decimal(unit.get("line_quantity") or 1)
                    L.create_fabric_need(
                        {
                            "sale_id": sale.id,
                            "product_name": product_name,
                            "color_name": fabric.get("color_name") or "",
                            "recipe_name": fabric.get("name") or "",
                            "meters": meters,
                        }
                    )
                    created.append("fabric")

            foam = unit.get("foam") or {}
            if _has_recipe(foam):
                if not BetaFoamJob.objects.filter(sale=sale, product_name=product_name).exists():
                    L.create_foam_job(
                        {
                            "sale_id": sale.id,
                            "product_name": product_name,
                            "foam_name": foam.get("name") or foam.get("color_name") or "",
                        }
                    )
                    created.append("foam")

            cushion = unit.get("cushion") or {}
            if _has_recipe(cushion):
                if not BetaCushionJob.objects.filter(sale=sale, product_name=product_name).exists():
                    L.create_cushion_job(
                        {
                            "sale_id": sale.id,
                            "product_name": product_name,
                            "cushion_name": cushion.get("name") or cushion.get("color_name") or "",
                        }
                    )
                    created.append("cushion")

            webbing = unit.get("webbing") or {}
            if (_has_recipe(foam) or _has_recipe(fabric) or _has_recipe(cushion) or _has_recipe(webbing)) and not (
                BetaUpholsteryJob.objects.filter(sale=sale, product_name=product_name).exists()
            ):
                L.create_upholstery_job(
                    {
                        "sale_id": sale.id,
                        "order_ref": sale.invoice_number or str(sale.id),
                        "product_name": product_name,
                        "foam_material": foam.get("name") or foam.get("color_name") or "",
                    }
                )
                created.append("upholstery")

            if pipeline_end == PIPELINE_END_ASSEMBLY and not BetaAssemblyJob.objects.filter(
                sale=sale, product_name=product_name
            ).exists():
                L.create_assembly_job(
                    {
                        "sale_id": sale.id,
                        "product_name": product_name,
                        "assembly_name": unit.get("piece_label") or unit.get("frame_name") or product_name,
                    }
                )
                created.append("assembly")

    primary = lines[0]
    if not sale.beta_qc_inspections.exists():
        L.create_qc_inspection(
            {
                "sale_id": sale.id,
                "order_ref": sale.invoice_number or str(sale.id),
                "invoice_ref": sale.invoice_number or "",
                "product_name": primary.product_name,
                "buyer_name": sale.customer.full_name if sale.customer_id else (sale.contract_party or ""),
                "origin": "خط کلاف",
            }
        )
        created.append("qc")

    if not sale.beta_clearance_jobs.exists():
        dest = clearance_destination(sale.receive_kind or "customer")
        L.create_clearance_job(
            {
                "sale_id": sale.id,
                "product_name": primary.product_name,
                "destination": dest,
            }
        )
        created.append("clearance")

    if wants_assembly:
        pass
    return {"created": created, "warnings": warnings}
