"""کاتالوگ دستور دست‌کار و اسنپ‌شات سفارش."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from backend.models import Material, Product, WorkshopRecipe, WorkshopRecipeMaterial

RECIPE_KINDS = {code: label for code, label in WorkshopRecipe.KIND_CHOICES}
KIND_TO_PRODUCT_FIELD = {
    WorkshopRecipe.KIND_PAINT: "paint_recipe",
    WorkshopRecipe.KIND_FABRIC: "fabric_recipe",
    WorkshopRecipe.KIND_FOAM: "foam_recipe",
    WorkshopRecipe.KIND_CUSHION: "cushion_recipe",
    WorkshopRecipe.KIND_WEBBING: "webbing_recipe",
}

BUILD_MODEL_FRAME_LINE = "frame_line"
PIPELINE_END_UPHOLSTERY = "upholstery"
PIPELINE_END_ASSEMBLY = "assembly"
PIPELINE_ENDS = {PIPELINE_END_UPHOLSTERY, PIPELINE_END_ASSEMBLY}


def _text(value, default=""):
    return str(value).strip() if value is not None else default


def _optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _qty(value, default="1"):
    try:
        qty = Decimal(str(value if value not in (None, "") else default))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("مقدار متریال نامعتبر است.")
    if qty <= 0:
        raise ValueError("مقدار متریال باید بزرگ‌تر از صفر باشد.")
    return qty


def recipe_material_to_dict(row):
    material = row.material
    return {
        "id": row.id,
        "material_id": material.id if material else None,
        "material_name": material.name if material else "",
        "material_color": (material.color_name if material else "") or "",
        "quantity": float(row.quantity or 0),
        "unit": row.unit or (material.unit if material else ""),
        "sort_order": row.sort_order,
    }


def recipe_to_dict(recipe, include_materials=True):
    data = {
        "id": recipe.id,
        "kind": recipe.kind,
        "kind_display": RECIPE_KINDS.get(recipe.kind, recipe.kind),
        "name": recipe.name,
        "color_name": recipe.color_name or "",
        "note": recipe.note or "",
        "is_active": recipe.is_active,
        "created_at": recipe.created_at.isoformat() if recipe.created_at else None,
        "updated_at": recipe.updated_at.isoformat() if recipe.updated_at else None,
    }
    if include_materials:
        rows = recipe.materials.select_related("material").all()
        data["materials"] = [recipe_material_to_dict(row) for row in rows]
    return data


def recipe_summary(recipe):
    if not recipe:
        return None
    return {
        "id": recipe.id,
        "kind": recipe.kind,
        "name": recipe.name,
        "color_name": recipe.color_name or "",
    }


def filter_recipes(qs, *, kind="", search="", active_only=True):
    if kind:
        qs = qs.filter(kind=kind)
    if active_only:
        qs = qs.filter(is_active=True)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(color_name__icontains=search))
    return qs


def _sync_recipe_materials(recipe, rows):
    keep_ids = []
    if not isinstance(rows, list):
        return
    for index, raw in enumerate(rows):
        material_id = _optional_int(raw.get("material_id") if isinstance(raw, dict) else None)
        if not material_id:
            continue
        material = Material.objects.filter(pk=material_id, is_deleted=False, is_active=True).first()
        if not material:
            raise ValueError("متریال دستور یافت نشد.")
        qty = _qty(raw.get("quantity") if isinstance(raw, dict) else None)
        unit = _text(raw.get("unit") if isinstance(raw, dict) else "") or material.unit or ""
        link, _ = WorkshopRecipeMaterial.objects.update_or_create(
            recipe=recipe,
            material=material,
            defaults={"quantity": qty, "unit": unit, "sort_order": index},
        )
        keep_ids.append(link.pk)
    recipe.materials.exclude(pk__in=keep_ids).delete()


@transaction.atomic
def create_recipe(data):
    kind = _text(data.get("kind"))
    if kind not in RECIPE_KINDS:
        raise ValueError("نوع دستور نامعتبر است.")
    name = _text(data.get("name"))
    if not name:
        raise ValueError("نام دستور را وارد کنید.")
    recipe = WorkshopRecipe.objects.create(
        kind=kind,
        name=name,
        color_name=_text(data.get("color_name")),
        note=_text(data.get("note")),
        is_active=bool(data.get("is_active", True)),
    )
    _sync_recipe_materials(recipe, data.get("materials") or [])
    return recipe


@transaction.atomic
def update_recipe(recipe, data):
    if "name" in data:
        name = _text(data.get("name"))
        if not name:
            raise ValueError("نام دستور را وارد کنید.")
        recipe.name = name
    if "color_name" in data:
        recipe.color_name = _text(data.get("color_name"))
    if "note" in data:
        recipe.note = _text(data.get("note"))
    if "is_active" in data:
        recipe.is_active = bool(data.get("is_active"))
    if "kind" in data:
        kind = _text(data.get("kind"))
        if kind not in RECIPE_KINDS:
            raise ValueError("نوع دستور نامعتبر است.")
        recipe.kind = kind
    recipe.save()
    if "materials" in data:
        _sync_recipe_materials(recipe, data.get("materials") or [])
    return recipe


def delete_recipe(recipe):
    recipe.soft_delete()


def resolve_recipe(recipe_id, *, kind=None):
    if not recipe_id:
        return None
    qs = WorkshopRecipe.objects.filter(pk=recipe_id, is_deleted=False, is_active=True)
    if kind:
        qs = qs.filter(kind=kind)
    recipe = qs.first()
    if not recipe:
        raise ValueError("دستور دست‌کار یافت نشد.")
    return recipe


def snapshot_recipe(recipe):
    if not recipe:
        return None
    materials = []
    for row in recipe.materials.select_related("material").all():
        if not row.material_id:
            continue
        materials.append(
            {
                "material_id": row.material_id,
                "quantity": float(row.quantity or 0),
                "unit": row.unit or row.material.unit or "",
            }
        )
    return {
        "id": recipe.id,
        "kind": recipe.kind,
        "name": recipe.name,
        "color_name": recipe.color_name or "",
        "materials": materials,
    }


def build_workset_from_product(product):
    if not product:
        return {}
    workset = {
        "build_model": getattr(product, "build_model", None) or BUILD_MODEL_FRAME_LINE,
        "needs_paint": bool(getattr(product, "needs_paint", True)),
        "pipeline_end": getattr(product, "pipeline_end", None) or PIPELINE_END_UPHOLSTERY,
    }
    if product.frame_id:
        workset["frame_id"] = product.frame_id
        workset["frame_name"] = product.frame.name if getattr(product, "frame", None) else ""
    furniture_workset = getattr(product, "furniture_workset", None)
    if getattr(product, "furniture_workset_id", None):
        workset["furniture_workset_id"] = product.furniture_workset_id
        workset["furniture_workset_name"] = furniture_workset.name if furniture_workset else ""
    pieces = list(getattr(product, "suite_config", None) or [])
    if pieces:
        workset["pieces"] = pieces
        workset["needs_paint"] = any(piece.get("needs_paint", True) for piece in pieces)
        if any(piece.get("pipeline_end") == PIPELINE_END_ASSEMBLY for piece in pieces):
            workset["pipeline_end"] = PIPELINE_END_ASSEMBLY
    for kind, field in KIND_TO_PRODUCT_FIELD.items():
        recipe = getattr(product, field, None)
        if recipe:
            workset[kind] = snapshot_recipe(recipe)
    return workset


def merge_workset_config(product, incoming=None):
    """اسنپ‌شات دست‌کار — ورودی فروش روی کاتالوگ محصول سوار می‌شود."""
    base = build_workset_from_product(product)
    if not isinstance(incoming, dict) or not incoming:
        return base
    merged = dict(base)
    if "needs_paint" in incoming:
        merged["needs_paint"] = bool(incoming.get("needs_paint"))
    if incoming.get("pipeline_end") in PIPELINE_ENDS:
        merged["pipeline_end"] = incoming.get("pipeline_end")
    if incoming.get("build_model"):
        merged["build_model"] = incoming.get("build_model")
    if incoming.get("frame_id"):
        merged["frame_id"] = incoming.get("frame_id")
        if incoming.get("frame_name"):
            merged["frame_name"] = incoming.get("frame_name")
    if incoming.get("furniture_workset_id"):
        merged["furniture_workset_id"] = incoming.get("furniture_workset_id")
        if incoming.get("furniture_workset_name"):
            merged["furniture_workset_name"] = incoming.get("furniture_workset_name")
    if incoming.get("pieces"):
        merged["pieces"] = incoming.get("pieces")
    for kind in RECIPE_KINDS:
        raw = incoming.get(kind)
        if not raw:
            continue
        if isinstance(raw, dict) and raw.get("id") and not raw.get("materials"):
            try:
                recipe = resolve_recipe(raw.get("id"), kind=kind)
            except ValueError:
                continue
            merged[kind] = snapshot_recipe(recipe)
            continue
        if isinstance(raw, dict):
            merged[kind] = raw
    return merged


def apply_product_workset(product, data):
    if "frame_id" in data:
        from backend.models import Frame

        frame_id = _optional_int(data.get("frame_id"))
        product.frame = Frame.objects.filter(pk=frame_id, is_deleted=False).first() if frame_id else None
    if "needs_paint" in data:
        product.needs_paint = bool(data.get("needs_paint"))
    if "pipeline_end" in data:
        end = _text(data.get("pipeline_end"))
        if end and end not in PIPELINE_ENDS:
            raise ValueError("انتهای خط ساخت نامعتبر است.")
        if end:
            product.pipeline_end = end
    if "build_model" in data:
        product.build_model = _text(data.get("build_model")) or BUILD_MODEL_FRAME_LINE
    for kind, field in KIND_TO_PRODUCT_FIELD.items():
        key = f"{field}_id"
        if key not in data and field not in data:
            continue
        recipe_id = _optional_int(data.get(key, data.get(field)))
        setattr(product, field, resolve_recipe(recipe_id, kind=kind) if recipe_id else None)
    if "furniture_workset_id" in data or "suite_config" in data or "pieces" in data:
        from backend.models import FurnitureWorkset
        from logic.furniture_worksets import apply_suite_to_product, normalize_suite_config

        workset_id = _optional_int(
            data.get("furniture_workset_id", getattr(product, "furniture_workset_id", None))
        )
        workset = (
            FurnitureWorkset.objects.filter(pk=workset_id, is_deleted=False)
            .prefetch_related("pieces")
            .first()
            if workset_id
            else None
        )
        if workset_id and not workset:
            raise ValueError("دست انتخاب‌شده یافت نشد.")
        if workset:
            raw = data.get("pieces") if "pieces" in data else data.get("suite_config")
            if raw is None:
                raw = getattr(product, "suite_config", None) or []
            apply_suite_to_product(product, workset, normalize_suite_config(workset, raw))
        else:
            product.furniture_workset = None
            product.suite_config = []
    return product


def compute_workset_line_requirements(line_item):
    """نیاز متریال دستورهای دست‌کار یک ردیف سفارش."""
    from logic.materials import material_to_dict

    config = getattr(line_item, "workset_config", None) or {}
    if not config and getattr(line_item, "product", None):
        config = build_workset_from_product(line_item.product)
    line_qty = Decimal(line_item.quantity or 0)
    if line_qty <= 0:
        return []

    results = []
    blocks = []
    pieces = config.get("pieces") or []
    if pieces:
        for piece in pieces:
            factor = Decimal(int(piece.get("quantity") or 1)) * line_qty
            for kind, label in RECIPE_KINDS.items():
                blocks.append((kind, label, piece.get(kind) or {}, factor))
    else:
        for kind, label in RECIPE_KINDS.items():
            blocks.append((kind, label, config.get(kind) or {}, line_qty))

    for kind, label, block, factor in blocks:
        for row in block.get("materials") or []:
            material_id = _optional_int(row.get("material_id"))
            if not material_id:
                continue
            material = Material.objects.filter(pk=material_id, is_deleted=False).first()
            if not material:
                continue
            req_qty = Decimal(str(row.get("quantity") or 0)) * factor
            if req_qty <= 0:
                continue
            stock = Decimal(material.stock or 0)
            results.append(
                {
                    "material_id": material.id,
                    "material": material_to_dict(material),
                    "required_quantity": float(req_qty),
                    "unit_cost": int(material.unit_cost or 0),
                    "line_cost": int(req_qty * Decimal(material.unit_cost or 0)),
                    "available_stock": float(stock),
                    "shortage": float(max(Decimal(0), req_qty - stock)),
                    "sufficient": stock >= req_qty,
                    "unit": row.get("unit") or material.unit,
                    "source": kind,
                    "source_labels": [label],
                }
            )
    return results


def workset_summary_from_lines(line_items):
    summary = {
        "frame": "",
        "paint": "",
        "fabric": "",
        "foam": "",
        "cushion": "",
        "webbing": "",
        "needs_paint": False,
        "pipeline_end": "",
        "build_model": BUILD_MODEL_FRAME_LINE,
    }
    for line in line_items:
        config = getattr(line, "workset_config", None) or {}
        if config.get("needs_paint"):
            summary["needs_paint"] = True
        if config.get("pipeline_end") and not summary["pipeline_end"]:
            summary["pipeline_end"] = config.get("pipeline_end")
        if config.get("build_model"):
            summary["build_model"] = config.get("build_model")
        if line.frame_id and not summary["frame"]:
            summary["frame"] = config.get("frame_name") or getattr(line.frame, "name", "") or "کلاف"
        if config.get("furniture_workset_name") and not summary["frame"]:
            summary["frame"] = config.get("furniture_workset_name")
        pieces = config.get("pieces") or []
        for piece in pieces:
            for kind in RECIPE_KINDS:
                block = piece.get(kind) or {}
                name = block.get("name") or block.get("color_name")
                if name and not summary[kind]:
                    extra = f" ({block['color_name']})" if block.get("color_name") and block.get("name") else ""
                    summary[kind] = f"{name}{extra}" if extra and block.get("name") != block.get("color_name") else name
        for kind in RECIPE_KINDS:
            block = config.get(kind) or {}
            name = block.get("name") or block.get("color_name")
            if name and not summary[kind]:
                extra = f" ({block['color_name']})" if block.get("color_name") and block.get("name") else ""
                summary[kind] = f"{name}{extra}" if extra and block.get("name") != block.get("color_name") else name
    return summary


def prefetch_product_workset(qs):
    return qs.select_related(
        "frame",
        "furniture_workset",
        "paint_recipe",
        "fabric_recipe",
        "foam_recipe",
        "cushion_recipe",
        "webbing_recipe",
    )
