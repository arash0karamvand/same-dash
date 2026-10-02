"""منطق متریال و ارتباط محصول–متریال."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from backend.models import InventoryTransaction, Material, Product, ProductMaterial
from logic.lookups import require_active_code, stored_label

MATERIAL_APPROVAL_LABELS = {
    Material.APPROVAL_PENDING: "در انتظار تایید اداری",
    Material.APPROVAL_APPROVED: "تایید شده",
    Material.APPROVAL_REJECTED: "رد شده",
}

COST_FIELD_NAMES = {
    "unit_cost",
    "inventory_value",
    "line_cost",
    "material_cost_total",
    "actual_cost",
    "total_cost",
    "overhead_cost",
    "actual_material_cost",
    "total_actual_cogs",
    "cost_breakdown",
    "profit_margin",
}


def mask_cost_fields(value):
    if isinstance(value, list):
        return [mask_cost_fields(item) for item in value]
    if isinstance(value, dict):
        return {
            key: mask_cost_fields(item)
            for key, item in value.items()
            if key not in COST_FIELD_NAMES
        }
    return value


def approved_materials_filter(prefix=""):
    field = f"{prefix}approval_status" if prefix else "approval_status"
    return {field: Material.APPROVAL_APPROVED}


def material_to_dict(m, *, include_cost=True):
    submitted_by = getattr(m, "submitted_by", None)
    approved_by = getattr(m, "approved_by", None)
    stock = m.stock
    unit_cost = int(m.unit_cost or 0)
    inventory_value = int(Decimal(stock) * Decimal(unit_cost)) if stock is not None else None
    data = {
        "id": m.id,
        "name": m.name,
        "usage_kind": getattr(m, "usage_kind", Material.USAGE_OTHER) or Material.USAGE_OTHER,
        "usage_kind_display": stored_label(
            "material_usage_kind",
            getattr(m, "usage_kind", Material.USAGE_OTHER) or Material.USAGE_OTHER,
        ),
        "color_name": m.color_name or "",
        "color_hex": m.color_hex,
        "sku": m.sku or "",
        "unit": m.unit,
        "valuation_method": getattr(m, "valuation_method", Material.VALUATION_WEIGHTED),
        "reorder_point": float(m.reorder_point or 0),
        "below_reorder": bool(
            stock is not None and Decimal(m.reorder_point or 0) > 0 and Decimal(stock) < Decimal(m.reorder_point or 0)
        ),
        "stock": float(stock) if stock is not None else None,
        "description": m.description or "",
        "is_active": m.is_active,
        "approval_status": getattr(m, "approval_status", Material.APPROVAL_APPROVED),
        "approval_status_display": MATERIAL_APPROVAL_LABELS.get(
            getattr(m, "approval_status", Material.APPROVAL_APPROVED),
            getattr(m, "approval_status", Material.APPROVAL_APPROVED),
        ),
        "submitted_by": submitted_by.username if submitted_by else None,
        "approved_by": approved_by.username if approved_by else None,
        "approved_at": m.approved_at.isoformat() if getattr(m, "approved_at", None) else None,
        "rejection_reason": getattr(m, "rejection_reason", "") or "",
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if getattr(m, "updated_at", None) else None,
    }
    if include_cost:
        data["unit_cost"] = unit_cost
        data["inventory_value"] = inventory_value
    return data


def product_material_to_dict(pm, *, include_cost=True):
    material = pm.material
    qty = Decimal(pm.quantity or 0)
    unit_cost = Decimal(material.unit_cost or 0)
    line_cost = qty * unit_cost
    data = {
        "id": f"{pm.product_id}:{pm.material_id}",
        "material_id": material.id,
        "material": material_to_dict(material, include_cost=include_cost),
        "quantity": float(qty),
        "normal_spoilage_rate": float(getattr(pm, "normal_spoilage_rate", 0) or 0),
        "sort_order": pm.sort_order,
    }
    if include_cost:
        data["line_cost"] = int(line_cost)
    return data


def compute_product_material_cost(product):
    return sum(
        (Decimal(str(row.get("line_cost") or 0)) for row in resolve_material_requirements(
            product=product, quantity=1
        )),
        Decimal(0),
    )


def resolve_material_requirements(
    *, product=None, workset_config=None, quantity=1, include_unapproved=False
):
    """Single source for catalog, order-snapshot, fulfillment and costing material demand."""
    from collections import defaultdict

    from backend.models import Frame, ProductMaterial

    try:
        multiplier = Decimal(str(quantity or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("تعداد محصول نامعتبر است.")
    if multiplier <= 0:
        return []
    if workset_config is None and product is not None:
        from logic.workshop_recipes import build_workset_from_product

        workset_config = build_workset_from_product(product)
    config = workset_config if isinstance(workset_config, dict) else {}
    totals = defaultdict(lambda: {"quantity": Decimal(0), "spoilage": Decimal(0), "sources": set()})

    def add(material_id, amount, source, spoilage=0):
        try:
            material_id = int(material_id)
            amount = Decimal(str(amount or 0))
        except (TypeError, ValueError, InvalidOperation):
            return
        if amount <= 0:
            return
        totals[material_id]["quantity"] += amount * multiplier
        totals[material_id]["spoilage"] = max(
            totals[material_id]["spoilage"], Decimal(str(spoilage or 0))
        )
        totals[material_id]["sources"].add(source)

    if product is not None:
        product_rows = ProductMaterial.objects.filter(
            product=product, material__is_deleted=False
        ).select_related("material")
        if not include_unapproved:
            product_rows = product_rows.filter(
                material__is_active=True,
                material__approval_status_ref_id=Material.APPROVAL_APPROVED,
            )
        for row in product_rows:
            add(row.material_id, row.quantity, "product", row.normal_spoilage_rate)

    pieces = config.get("pieces") or []
    units = pieces if pieces else [config]
    for piece in units:
        piece_factor = Decimal(int(piece.get("quantity") or 1)) if pieces else Decimal(1)
        for kind in ("paint", "fabric", "foam", "cushion", "webbing"):
            if kind == "paint" and piece.get("needs_paint", config.get("needs_paint", True)) is False:
                continue
            for row in (piece.get(kind) or {}).get("materials") or []:
                add(row.get("material_id"), Decimal(str(row.get("quantity") or 0)) * piece_factor, kind)
        frame_id = piece.get("frame_id") if pieces else config.get("frame_id")
        if frame_id:
            frame = Frame.objects.filter(
                pk=frame_id, is_deleted=False, is_active=True
            ).prefetch_related("models__wood_requirements").first()
            model = frame.models.filter(is_active=True).order_by("sort_order", "id").first() if frame else None
            if model:
                for wood in model.wood_requirements.all():
                    if wood.material_id:
                        add(wood.material_id, Decimal(wood.quantity or 0) * piece_factor, "frame")

    material_rows = Material.objects.filter(pk__in=totals, is_deleted=False)
    if not include_unapproved:
        material_rows = material_rows.filter(
            is_active=True, approval_status_ref_id=Material.APPROVAL_APPROVED
        )
    materials = {
        material.pk: material
        for material in material_rows
    }
    result = []
    for material_id, aggregate in sorted(totals.items()):
        material = materials.get(material_id)
        if not material:
            continue
        required = aggregate["quantity"]
        result.append(
            {
                "material_id": material_id,
                "material": material_to_dict(material),
                "required_quantity": float(required),
                "unit": material.unit,
                "unit_cost": int(material.unit_cost or 0),
                "line_cost": int(required * Decimal(material.unit_cost or 0)),
                "source": "+".join(sorted(aggregate["sources"])),
                "source_labels": sorted(aggregate["sources"]),
                "normal_spoilage_rate": float(aggregate["spoilage"]),
            }
        )
    return result


def _parse_usage_kind(value, *, required=False):
    if not (value or "").strip():
        if required:
            raise ValueError("نوع مصرف متریال را انتخاب کنید.")
        return require_active_code(
            "material_usage_kind",
            Material.USAGE_OTHER,
            "نوع مصرف متریال نامعتبر است.",
            default=Material.USAGE_OTHER,
        )
    return require_active_code("material_usage_kind", value, "نوع مصرف متریال نامعتبر است.")


def filter_materials(
    queryset,
    *,
    search="",
    active_only=True,
    approved_only=False,
    approval_status=None,
    usage_kind=None,
):
    if active_only:
        queryset = queryset.filter(is_active=True, is_deleted=False)
    if approved_only:
        queryset = queryset.filter(**approved_materials_filter())
    if approval_status:
        queryset = queryset.filter(approval_status=approval_status)
    if usage_kind:
        queryset = queryset.filter(usage_kind=usage_kind)
    if search:
        q = Q(name__icontains=search) | Q(sku__icontains=search) | Q(color_name__icontains=search)
        queryset = queryset.filter(q)
    return queryset.order_by("name")


@transaction.atomic
def create_material(data, *, user=None, auto_approve=False):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("نام متریال الزامی است.")
    try:
        unit_cost = Decimal(str(data.get("unit_cost") or 0))
    except (InvalidOperation, TypeError):
        raise ValueError("قیمت متریال نامعتبر است.")
    stock = _parse_stock(data.get("stock"))
    if auto_approve:
        from django.utils import timezone

        approval_status = Material.APPROVAL_APPROVED
        is_active = bool(data.get("is_active", True))
        approved_at = timezone.now()
        approved_by = user
    else:
        approval_status = Material.APPROVAL_PENDING
        is_active = False
        approved_at = None
        approved_by = None
    material = Material.objects.create(
        name=name,
        usage_kind=_parse_usage_kind(data.get("usage_kind")),
        color_name=(data.get("color_name") or "").strip(),
        color_hex=(data.get("color_hex") or "#cccccc").strip()[:7],
        sku=(data.get("sku") or "").strip(),
        unit=(data.get("unit") or "متر").strip() or "متر",
        unit_cost=unit_cost,
        valuation_method=require_active_code(
            "material_valuation_method",
            data.get("valuation_method"),
            "روش ارزیابی نامعتبر است.",
            default=Material.VALUATION_WEIGHTED,
        ),
        reorder_point=_parse_reorder(data.get("reorder_point")),
        description=(data.get("description") or "").strip(),
        is_active=is_active,
        approval_status=approval_status,
        submitted_by=user,
        approved_at=approved_at,
        approved_by=approved_by,
    )
    if stock not in (None, 0):
        from logic.inventory_costing import receive_stock

        receive_stock(
            material,
            stock,
            unit_cost,
            freight_amount=data.get("freight_amount") or 0,
            freight_treatment=require_active_code(
                "material_freight_treatment",
                data.get("freight_treatment"),
                "نحوه ثبت حمل نامعتبر است.",
                default="capitalize",
            ),
            previous_unit_cost=0,
            reason="initial_stock",
            reference=f"material:{material.pk}",
            recorded_by=user,
        )
    if auto_approve:
        from logic.material_accounting import post_material_inventory_receipt

        post_material_inventory_receipt(material)
    return material


@transaction.atomic
def update_material(material, data):
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("نام متریال الزامی است.")
        material.name = name
    if "usage_kind" in data:
        material.usage_kind = _parse_usage_kind(data.get("usage_kind"))
    if "color_name" in data:
        material.color_name = (data.get("color_name") or "").strip()
    if "color_hex" in data:
        material.color_hex = (data.get("color_hex") or "#cccccc").strip()[:7]
    if "sku" in data:
        material.sku = (data.get("sku") or "").strip()
    if "unit" in data:
        material.unit = (data.get("unit") or "متر").strip() or "متر"
    previous_cost = Decimal(material.unit_cost or 0)
    incoming_cost = None
    if "unit_cost" in data:
        try:
            incoming_cost = Decimal(str(data.get("unit_cost") or 0))
        except (InvalidOperation, TypeError):
            raise ValueError("قیمت متریال نامعتبر است.")
    if "valuation_method" in data:
        from logic.inventory_costing import set_valuation_method

        set_valuation_method(material, data.get("valuation_method"))
    if "reorder_point" in data:
        try:
            reorder = Decimal(str(data.get("reorder_point") or 0))
        except (InvalidOperation, TypeError):
            raise ValueError("نقطه سفارش نامعتبر است.")
        if reorder < 0:
            raise ValueError("نقطه سفارش نمی‌تواند منفی باشد.")
        material.reorder_point = reorder
    stock_change = "stock" in data
    new_stock = _parse_stock(data.get("stock")) if stock_change else None
    increased = new_stock is not None and Decimal(new_stock) > Decimal(material.stock or 0)
    if stock_change:
        _apply_stock_update(
            material,
            new_stock,
            receipt_unit_cost=data.get("receipt_unit_cost", incoming_cost if incoming_cost is not None else previous_cost),
            freight_amount=data.get("freight_amount") or 0,
            freight_treatment=require_active_code(
                "material_freight_treatment",
                data.get("freight_treatment"),
                "نحوه ثبت حمل نامعتبر است.",
                default="capitalize",
            ),
            previous_unit_cost=previous_cost,
            user=None,
        )
    if incoming_cost is not None and not increased:
        material.unit_cost = incoming_cost
    if "description" in data:
        material.description = (data.get("description") or "").strip()
    if "is_active" in data:
        material.is_active = bool(data.get("is_active"))
    material.save()
    return material


@transaction.atomic
def approve_material(material, user):
    if material.approval_status == Material.APPROVAL_APPROVED:
        return material
    from django.utils import timezone

    material.approval_status = Material.APPROVAL_APPROVED
    material.is_active = True
    material.approved_at = timezone.now()
    material.approved_by = user
    material.rejection_reason = ""
    material.save(
        update_fields=[
            "approval_status",
            "is_active",
            "approved_at",
            "approved_by_id",
            "rejection_reason",
            "updated_at",
        ]
    )
    from logic.material_accounting import post_material_inventory_receipt

    post_material_inventory_receipt(material)
    return material


@transaction.atomic
def reject_material(material, user, reason=""):
    material.approval_status = Material.APPROVAL_REJECTED
    material.is_active = False
    material.rejection_reason = (reason or "").strip()
    material.save(update_fields=["approval_status", "is_active", "rejection_reason", "updated_at"])
    return material


def _parse_reorder(raw):
    if raw in (None, ""):
        return Decimal(0)
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError):
        raise ValueError("نقطه سفارش نامعتبر است.")
    if value < 0:
        raise ValueError("نقطه سفارش نمی‌تواند منفی باشد.")
    return value


def _parse_stock(raw):
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError):
        raise ValueError("موجودی نامعتبر است.")


def _apply_stock_update(
    material,
    new_stock,
    *,
    receipt_unit_cost=None,
    freight_amount=0,
    freight_treatment="capitalize",
    previous_unit_cost=None,
    user=None,
):
    """Represent an absolute-stock edit as an append-only receipt."""
    if new_stock is None:
        return
    current = Decimal(material.stock or 0)
    if Decimal(new_stock) < current:
        raise ValueError("کاهش موجودی فقط با پایان ساخت سفارش در کارخانه امکان‌پذیر است.")
    delta = Decimal(new_stock) - current
    if not delta:
        return
    from logic.inventory_costing import receive_stock

    cost = receipt_unit_cost if receipt_unit_cost not in (None, "") else material.unit_cost
    receive_stock(
        material,
        delta,
        cost,
        freight_amount=freight_amount or 0,
        freight_treatment=freight_treatment or "capitalize",
        previous_unit_cost=previous_unit_cost if previous_unit_cost is not None else material.unit_cost,
        reason="manual_adjustment",
        reference=f"material:{material.pk}",
        recorded_by=user,
    )


def _parse_product_materials(raw_items):
    if not raw_items:
        return []
    parsed = []
    for idx, item in enumerate(raw_items):
        material_id = item.get("material_id")
        if not material_id:
            continue
        try:
            quantity = Decimal(str(item.get("quantity") or 1))
        except (InvalidOperation, TypeError):
            raise ValueError("مقدار مصرف متریال نامعتبر است.")
        if quantity <= 0:
            raise ValueError("مقدار مصرف متریال باید بزرگ‌تر از صفر باشد.")
        try:
            spoilage = Decimal(str(item.get("normal_spoilage_rate") or 0))
        except (InvalidOperation, TypeError):
            raise ValueError("نرخ ضایعات عادی نامعتبر است.")
        if spoilage < 0 or spoilage > 100:
            raise ValueError("نرخ ضایعات عادی باید بین ۰ و ۱۰۰ باشد.")
        parsed.append(
            {
                "material_id": int(material_id),
                "quantity": quantity,
                "normal_spoilage_rate": spoilage,
                "sort_order": int(item.get("sort_order") if item.get("sort_order") is not None else idx),
            }
        )
    return parsed


@transaction.atomic
def sync_product_materials(product, raw_items):
    items = _parse_product_materials(raw_items)
    keep_material_ids = []
    for item in items:
        material = Material.objects.filter(
            pk=item["material_id"],
            is_deleted=False,
            **approved_materials_filter(),
        ).first()
        if not material:
            raise ValueError("متریال انتخاب‌شده یافت نشد یا هنوز تایید اداری نشده است.")
        pm, _ = ProductMaterial.objects.get_or_create(product=product, material=material)
        pm.quantity = item["quantity"]
        pm.normal_spoilage_rate = item["normal_spoilage_rate"]
        pm.sort_order = item["sort_order"]
        pm.save()
        keep_material_ids.append(material.pk)
    product.product_materials.exclude(material_id__in=keep_material_ids).delete()
    return product


FACTORY_QUEUE_STAGES = None


def factory_queue_stages():
    global FACTORY_QUEUE_STAGES
    if FACTORY_QUEUE_STAGES is None:
        from backend.models import Sale

        FACTORY_QUEUE_STAGES = (
            Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
            Sale.WORKFLOW_STAGE_MERCHANT_ASSIGNED,
            Sale.WORKFLOW_STAGE_IN_PRODUCTION,
        )
    return FACTORY_QUEUE_STAGES


def _add_workset_snapshot_demand(totals, workset, line_qty):
    if not isinstance(workset, dict) or line_qty <= 0:
        return
    pieces = workset.get("pieces") or []
    units = pieces if pieces else [workset]
    for unit in units:
        factor = line_qty * Decimal(int(unit.get("quantity") or 1) if pieces else 1)
        for kind in ("paint", "fabric", "foam", "cushion", "webbing"):
            for row in (unit.get(kind) or {}).get("materials") or []:
                material_id = row.get("material_id")
                if not material_id:
                    continue
                qty = Decimal(str(row.get("quantity") or 0)) * factor
                if qty > 0:
                    totals[int(material_id)] += qty


def committed_material_demand(exclude_sale_id=None):
    """جمع نیاز متریال سفارش‌های صف کارخانه که هنوز کسر نشده‌اند."""
    from collections import defaultdict

    from backend.models import ProductMaterial, SaleLineItem

    lines = SaleLineItem.objects.filter(
        sale__workflow_stage_id__in=factory_queue_stages(),
        sale__materials_deducted_at__isnull=True,
    )
    if exclude_sale_id:
        lines = lines.exclude(sale_id=exclude_sale_id)
    rows = list(lines.values("product_id", "quantity", "workset_config"))
    totals = defaultdict(lambda: Decimal(0))
    if not rows:
        return {}

    product_ids = {row["product_id"] for row in rows if row["product_id"]}
    bom_map = defaultdict(list)
    if product_ids:
        for pm in ProductMaterial.objects.filter(
            product_id__in=product_ids,
            material__is_deleted=False,
            material__is_active=True,
            material__approval_status_ref_id=Material.APPROVAL_APPROVED,
        ).values("product_id", "material_id", "quantity"):
            bom_map[pm["product_id"]].append(pm)

    for row in rows:
        line_qty = Decimal(row["quantity"] or 0)
        if line_qty <= 0:
            continue
        for pm in bom_map.get(row["product_id"], []):
            totals[pm["material_id"]] += line_qty * Decimal(pm["quantity"] or 0)
        _add_workset_snapshot_demand(totals, row.get("workset_config") or {}, line_qty)
    return dict(totals)


def _apply_stock_and_queue(items, *, exclude_sale_id=None, queue_aware=True):
    committed = committed_material_demand(exclude_sale_id=exclude_sale_id) if queue_aware else {}
    for item in items:
        material = item.get("material") or {}
        stock = material.get("stock")
        if stock is None:
            stock = item.get("available_stock")
        stock_val = Decimal(str(stock)) if stock is not None else None
        req = Decimal(str(item.get("required_quantity") or 0))
        others = Decimal(str(committed.get(item["material_id"], 0)))
        item["committed_by_others"] = float(others)
        item["available_stock"] = float(stock_val) if stock_val is not None else None
        if stock_val is None:
            item["available_after_queue"] = None
            item["shortage"] = None
            item["sufficient"] = True
            continue
        available_after = stock_val - others if queue_aware else stock_val
        item["available_after_queue"] = float(available_after)
        item["shortage"] = float(max(Decimal(0), req - available_after))
        item["sufficient"] = available_after >= req
    return items


def compute_factory_order_material_requirements(factory_order, *, queue_aware=True):
    """محاسبه متریال مورد نیاز سفارش از resolver مشترک محصول/اسنپ‌شات."""
    from logic.frame_materials import merge_material_requirements

    merged = []
    line_items = list(factory_order.line_items.all())
    for line in line_items:
        rows = resolve_material_requirements(
            product=line.product if line.product_id else None,
            workset_config=line.workset_config or None,
            quantity=line.quantity,
        )
        for row in rows:
            stock = row["material"].get("stock")
            stock_value = Decimal(str(stock)) if stock is not None else None
            required = Decimal(str(row["required_quantity"]))
            row["available_stock"] = float(stock_value) if stock_value is not None else None
            row["shortage"] = (
                float(max(Decimal(0), required - stock_value)) if stock_value is not None else None
            )
            row["sufficient"] = stock_value is None or stock_value >= required
        merged = merge_material_requirements(merged, rows)
    return _apply_stock_and_queue(
        merged,
        exclude_sale_id=getattr(factory_order, "pk", None),
        queue_aware=queue_aware,
    )


def factory_order_materials_summary(factory_order):
    from logic.workshop_recipes import (
        compute_workset_recipe_requirements,
        workset_summary_from_lines,
    )

    requirements = compute_factory_order_material_requirements(factory_order)
    recipe_requirements = compute_workset_recipe_requirements(
        list(factory_order.line_items.select_related("product").all())
    )
    tracked = [item for item in requirements if item["available_stock"] is not None]
    material_cost_total = sum(int(item.get("line_cost") or 0) for item in requirements)
    return {
        "material_requirements": requirements,
        "recipe_requirements": recipe_requirements,
        "material_cost_total": material_cost_total,
        "workset_summary": workset_summary_from_lines(list(factory_order.line_items.all())),
        "materials_deducted": bool(getattr(factory_order, "materials_deducted_at", None)),
        "materials_deducted_at": (
            factory_order.materials_deducted_at.isoformat()
            if getattr(factory_order, "materials_deducted_at", None)
            else None
        ),
        "materials_all_sufficient": all(item["sufficient"] for item in tracked) if tracked else True,
        "has_material_shortage": any(not item["sufficient"] for item in tracked),
        "has_recipe_shortage": any(not item["sufficient"] for item in recipe_requirements),
    }


def _format_material_shortages(requirements):
    parts = []
    for item in requirements:
        if item["available_stock"] is None or item["sufficient"]:
            continue
        name = item["material"]["name"]
        if item["material"].get("color_name"):
            name = f"{name} ({item['material']['color_name']})"
        parts.append(
            f"«{name}»: نیاز {item['required_quantity']} {item['unit']}، موجود {item['available_stock']}"
        )
    return parts


@transaction.atomic
def deduct_materials_for_factory_order(factory_order):
    from backend.models import Material, Sale

    factory_order = Sale.objects.select_for_update().get(pk=factory_order.pk)
    if getattr(factory_order, "materials_deducted_at", None):
        return factory_order

    requirements = compute_factory_order_material_requirements(factory_order, queue_aware=False)
    tracked = [item for item in requirements if item["available_stock"] is not None]
    material_ids = sorted({item["material_id"] for item in tracked})
    locked = {}
    if material_ids:
        locked = {
            material.pk: material
            for material in Material.objects.select_for_update().filter(pk__in=material_ids).order_by("pk")
        }
    for item in tracked:
        material = locked[item["material_id"]]
        stock = Decimal(material.stock or 0)
        req_qty = Decimal(str(item["required_quantity"]))
        shortage = max(Decimal(0), req_qty - stock)
        item["available_stock"] = float(stock)
        item["shortage"] = float(shortage)
        item["sufficient"] = stock >= req_qty

    shortages = _format_material_shortages(requirements)
    if shortages:
        raise ValueError("موجودی متریال کافی نیست — " + "؛ ".join(shortages))

    from logic.inventory_costing import consume_stock

    for item in tracked:
        material = locked[item["material_id"]]
        req_qty = Decimal(str(item["required_quantity"]))
        consumed = consume_stock(
            material,
            req_qty,
            reason="production_consumption",
            reference=f"sale:{factory_order.pk}",
            sale=factory_order,
        )
        cost = consumed["unit_cost"]
        item["unit_cost"] = int(cost)
        item["line_cost"] = int(consumed["total_cost"])

    from logic.material_accounting import post_factory_material_consumption

    post_factory_material_consumption(factory_order, requirements)

    from django.utils import timezone

    factory_order.materials_deducted_at = timezone.now()
    factory_order.save(update_fields=["materials_deducted_at"])
    return factory_order


@transaction.atomic
def restore_materials_for_factory_order(factory_order):
    from backend.models import Material, Sale

    factory_order = Sale.objects.select_for_update().get(pk=factory_order.pk)
    if not getattr(factory_order, "materials_deducted_at", None):
        return factory_order

    requirements = compute_factory_order_material_requirements(factory_order, queue_aware=False)
    tracked = [item for item in requirements if item["available_stock"] is not None]
    material_ids = sorted({item["material_id"] for item in tracked})
    locked = {}
    if material_ids:
        locked = {
            material.pk: material
            for material in Material.objects.select_for_update().filter(pk__in=material_ids).order_by("pk")
        }
    from logic.inventory_costing import receive_stock

    for item in tracked:
        material = locked[item["material_id"]]
        issued = InventoryTransaction.objects.filter(
            material=material,
            reference=f"sale:{factory_order.pk}",
            reason="production_consumption",
        ).order_by("-id").first()
        cost = issued.unit_cost if issued else material.unit_cost
        receive_stock(
            material,
            Decimal(str(item["required_quantity"])),
            cost,
            previous_unit_cost=material.unit_cost,
            reason="production_rollback",
            reference=f"sale:{factory_order.pk}",
        )

    from logic.material_accounting import reverse_factory_material_consumption

    reverse_factory_material_consumption(factory_order, requirements)

    factory_order.materials_deducted_at = None
    factory_order.save(update_fields=["materials_deducted_at"])
    return factory_order
