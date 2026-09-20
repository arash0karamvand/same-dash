"""دست مبلمان — قطعات با تعداد در کلاف، رنگ و پارچه در محصول."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from backend.models import Frame, FurnitureWorkset, FurnitureWorksetPiece, Product

PIECE_KIND_LABELS = dict(Frame.PIECE_KIND_CHOICES)
ARM_STYLE_LABELS = dict(Frame.ARM_STYLE_CHOICES)

ALLOWED_ARMS = {
    Frame.PIECE_ARMCHAIR: (Frame.ARM_NONE, Frame.ARM_ONE, Frame.ARM_TWO),
    Frame.PIECE_SOFA_2: (Frame.ARM_ONE_LEFT, Frame.ARM_ONE_RIGHT, Frame.ARM_TWO),
    Frame.PIECE_SOFA_3: (Frame.ARM_ONE_LEFT, Frame.ARM_ONE_RIGHT, Frame.ARM_TWO),
    Frame.PIECE_SOFA_4: (Frame.ARM_ONE_LEFT, Frame.ARM_ONE_RIGHT, Frame.ARM_TWO),
    Frame.PIECE_SOFA_5: (Frame.ARM_ONE_LEFT, Frame.ARM_ONE_RIGHT, Frame.ARM_TWO),
    Frame.PIECE_CHAISE: (Frame.ARM_ONE_LEFT, Frame.ARM_ONE_RIGHT),
    Frame.PIECE_POUF: (Frame.ARM_NONE,),
    Frame.PIECE_BENCH: (Frame.ARM_NONE,),
    Frame.PIECE_LOVESEAT: (Frame.ARM_NONE,),
    Frame.PIECE_SIDE_TABLE: (Frame.ARM_NONE,),
    Frame.PIECE_COFFEE_TABLE: (Frame.ARM_NONE,),
}

ASSEMBLY_PIECES = {Frame.PIECE_SIDE_TABLE, Frame.PIECE_COFFEE_TABLE}
RECIPE_ID_KEYS = (
    "paint_recipe_id",
    "fabric_recipe_id",
    "foam_recipe_id",
    "cushion_recipe_id",
    "webbing_recipe_id",
)


def validate_piece_arm(piece_kind, arm_style):
    kind = (piece_kind or "").strip()
    style = (arm_style or "").strip()
    if not kind:
        return "", ""
    if kind not in ALLOWED_ARMS:
        raise ValueError("نوع قطعه نامعتبر است.")
    allowed = ALLOWED_ARMS[kind]
    if not style:
        style = allowed[0]
    if style not in allowed:
        label = PIECE_KIND_LABELS.get(kind, kind)
        raise ValueError(f"حالت دسته برای «{label}» نامعتبر است.")
    return kind, style


def piece_label(piece_kind, arm_style=""):
    kind = (piece_kind or "").strip()
    style = (arm_style or "").strip()
    base = PIECE_KIND_LABELS.get(kind, kind)
    if not kind:
        return ""
    if style and style != Frame.ARM_NONE:
        return f"{base} {ARM_STYLE_LABELS.get(style, style)}"
    if style == Frame.ARM_NONE and kind == Frame.PIECE_ARMCHAIR:
        return f"{base} بدون دسته"
    return base


def piece_slots():
    slots = []
    for kind, styles in ALLOWED_ARMS.items():
        group = PIECE_KIND_LABELS[kind]
        for style in styles:
            slots.append(
                {
                    "piece_kind": kind,
                    "arm_style": style,
                    "label": piece_label(kind, style),
                    "group": group,
                    "arm_label": ARM_STYLE_LABELS.get(style, style),
                    "show_arm": bool(style) and (style != Frame.ARM_NONE or kind == Frame.PIECE_ARMCHAIR),
                }
            )
    return slots


def piece_to_dict(row):
    return {
        "id": row.id,
        "piece_kind": row.piece_kind,
        "arm_style": row.arm_style,
        "quantity": row.quantity,
        "sort_order": row.sort_order,
        "piece_label": piece_label(row.piece_kind, row.arm_style),
        "piece_kind_display": PIECE_KIND_LABELS.get(row.piece_kind, row.piece_kind),
        "arm_style_display": ARM_STYLE_LABELS.get(row.arm_style, row.arm_style),
    }


def workset_to_dict(workset, *, include_frames=False):
    pieces = [piece_to_dict(row) for row in workset.pieces.all()]
    data = {
        "id": workset.id,
        "name": workset.name,
        "design_style": workset.design_style or "",
        "seat_count": workset.seat_count,
        "is_active": workset.is_active,
        "pieces": pieces,
        "piece_count": sum(row["quantity"] for row in pieces),
        "frame_count": len(pieces),
        "created_at": workset.created_at.isoformat() if workset.created_at else None,
        "updated_at": workset.updated_at.isoformat() if getattr(workset, "updated_at", None) else None,
    }
    if include_frames:
        from logic.frames import frame_to_dict

        data["frames"] = [
            frame_to_dict(frame)
            for frame in workset.frames.filter(is_deleted=False).order_by("name", "id")
        ]
    return data


def filter_worksets(queryset, *, search="", active_only=True):
    if active_only:
        queryset = queryset.filter(is_active=True)
    if search:
        queryset = queryset.filter(Q(name__icontains=search))
    return queryset.prefetch_related("pieces")


def _parse_seat_count(value):
    if value in (None, ""):
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        raise ValueError("تعداد نفر نامعتبر است.")
    if count < 1:
        raise ValueError("تعداد نفر باید حداقل ۱ باشد.")
    return count


def _parse_quantity(value):
    try:
        qty = int(value)
    except (TypeError, ValueError):
        raise ValueError("تعداد قطعه نامعتبر است.")
    if qty < 0:
        raise ValueError("تعداد قطعه نمی‌تواند منفی باشد.")
    if qty > 99:
        raise ValueError("تعداد قطعه بیش از حد است.")
    return qty


def _parse_pieces(raw):
    if raw in (None, ""):
        return None
    if not isinstance(raw, list):
        raise ValueError("فهرست قطعات نامعتبر است.")
    pieces = []
    seen = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        kind, style = validate_piece_arm(item.get("piece_kind"), item.get("arm_style"))
        if not kind:
            continue
        qty = _parse_quantity(item.get("quantity") or 0)
        if qty == 0:
            continue
        key = (kind, style)
        if key in seen:
            raise ValueError(f"قطعه تکراری: {piece_label(kind, style)}")
        seen.add(key)
        pieces.append(
            {
                "piece_kind": kind,
                "arm_style": style,
                "quantity": qty,
                "sort_order": index,
            }
        )
    return pieces


def _sync_pieces(workset, pieces):
    FurnitureWorksetPiece.objects.filter(workset=workset).delete()
    FurnitureWorksetPiece.objects.bulk_create(
        [
            FurnitureWorksetPiece(workset=workset, **row)
            for row in pieces
        ]
    )


@transaction.atomic
def create_workset(data):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("نام دست الزامی است.")
    workset = FurnitureWorkset.objects.create(
        name=name,
        design_style=(data.get("design_style") or "").strip(),
        seat_count=_parse_seat_count(data.get("seat_count")),
        is_active=data.get("is_active", True) is not False,
    )
    if "pieces" in data:
        pieces = _parse_pieces(data.get("pieces")) or []
        if not pieces:
            raise ValueError("حداقل یک قطعه با تعداد بیشتر از صفر انتخاب کنید.")
        _sync_pieces(workset, pieces)
    return FurnitureWorkset.objects.prefetch_related("pieces").get(pk=workset.pk)


@transaction.atomic
def update_workset(workset, data):
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("نام دست الزامی است.")
        workset.name = name
    if "design_style" in data:
        workset.design_style = (data.get("design_style") or "").strip()
    if "seat_count" in data:
        workset.seat_count = _parse_seat_count(data.get("seat_count"))
    if "is_active" in data:
        workset.is_active = data.get("is_active", True) is not False
    workset.save()
    if "pieces" in data:
        pieces = _parse_pieces(data.get("pieces")) or []
        if not pieces:
            raise ValueError("حداقل یک قطعه با تعداد بیشتر از صفر انتخاب کنید.")
        _sync_pieces(workset, pieces)
    return FurnitureWorkset.objects.prefetch_related("pieces").get(pk=workset.pk)


def delete_workset(workset):
    workset.soft_delete()
    Frame.objects.filter(workset=workset, is_deleted=False).update(workset=None)
    return workset


def products_for_workset(workset):
    return Product.objects.filter(is_deleted=False, is_active=True).filter(
        Q(furniture_workset=workset) | Q(frame__workset=workset, frame__is_deleted=False)
    ).select_related(
        "furniture_workset",
        "frame",
        "frame__workset",
        "paint_recipe",
        "fabric_recipe",
        "foam_recipe",
        "cushion_recipe",
        "webbing_recipe",
    ).prefetch_related("variants").distinct()


def _optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_money(value):
    if value in (None, ""):
        return Decimal(0)
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("قیمت قطعه نامعتبر است.")
    if amount < 0:
        raise ValueError("قیمت قطعه نمی‌تواند منفی باشد.")
    return amount


def normalize_suite_config(workset, raw_pieces=None):
    from logic.workshop_recipes import (
        KIND_TO_PRODUCT_FIELD,
        PIPELINE_END_ASSEMBLY,
        PIPELINE_END_UPHOLSTERY,
        PIPELINE_ENDS,
        resolve_recipe,
        snapshot_recipe,
    )

    composition = list(workset.pieces.all())
    if not composition:
        raise ValueError("این دست قطعه‌ای ندارد. اول در تولید کلاف تعداد قطعات را بگذارید.")

    incoming = {}
    for item in raw_pieces or []:
        if not isinstance(item, dict):
            continue
        kind, style = validate_piece_arm(item.get("piece_kind"), item.get("arm_style"))
        if kind:
            incoming[(kind, style)] = item

    result = []
    for row in composition:
        item = incoming.get((row.piece_kind, row.arm_style), {})
        qty = _parse_quantity(item.get("quantity") if item.get("quantity") not in (None, "") else row.quantity)
        if qty < 1:
            qty = row.quantity
        needs_paint = item.get("needs_paint", True) is not False
        pipeline_end = (item.get("pipeline_end") or "").strip()
        if pipeline_end and pipeline_end not in PIPELINE_ENDS:
            raise ValueError("انتهای خط ساخت نامعتبر است.")
        if not pipeline_end:
            pipeline_end = (
                PIPELINE_END_ASSEMBLY if row.piece_kind in ASSEMBLY_PIECES else PIPELINE_END_UPHOLSTERY
            )
        unit_price = _parse_money(item.get("unit_price"))
        piece = {
            "piece_kind": row.piece_kind,
            "arm_style": row.arm_style,
            "piece_label": piece_label(row.piece_kind, row.arm_style),
            "quantity": qty,
            "needs_paint": needs_paint,
            "pipeline_end": pipeline_end,
            "unit_price": str(int(unit_price)),
        }
        for kind, field in KIND_TO_PRODUCT_FIELD.items():
            key = f"{field}_id"
            raw_id = item.get(key, item.get(f"{kind}_recipe_id"))
            recipe_id = _optional_int(raw_id)
            if kind == "paint" and not needs_paint:
                recipe_id = None
            recipe = resolve_recipe(recipe_id, kind=kind) if recipe_id else None
            piece[key] = recipe.id if recipe else None
            piece[kind] = snapshot_recipe(recipe) if recipe else None
        result.append(piece)
    return result


def suite_price(pieces):
    total = Decimal(0)
    for piece in pieces or []:
        total += _parse_money(piece.get("unit_price")) * int(piece.get("quantity") or 1)
    return total


def default_frame_name(workset, piece_kind, arm_style):
    label = piece_label(piece_kind, arm_style) or "کلاف"
    if workset and workset.name:
        return f"{workset.name} — {label}"
    return label


def default_product_name(workset, fabric_name=""):
    parts = [workset.name] if workset and workset.name else []
    if fabric_name:
        parts.append(fabric_name)
    return " — ".join(parts) if parts else "محصول دست"


def _first_fabric_name(pieces):
    for piece in pieces or []:
        block = piece.get("fabric") or {}
        name = block.get("name") or ""
        if name:
            return name
    return ""


def apply_suite_to_product(product, workset, pieces):
    product.furniture_workset = workset
    product.suite_config = pieces
    product.build_model = "frame_line"
    product.needs_paint = any(piece.get("needs_paint", True) for piece in pieces)
    product.pipeline_end = (
        "assembly"
        if any(piece.get("pipeline_end") == "assembly" for piece in pieces)
        else "upholstery"
    )
    first = pieces[0] if pieces else {}
    from logic.workshop_recipes import KIND_TO_PRODUCT_FIELD, resolve_recipe

    for kind, field in KIND_TO_PRODUCT_FIELD.items():
        recipe_id = first.get(f"{field}_id")
        setattr(product, field, resolve_recipe(recipe_id, kind=kind) if recipe_id else None)
    fabric_name = _first_fabric_name(pieces)
    if fabric_name and not (product.fabric or "").strip():
        product.fabric = fabric_name
    if not (product.product_model or "").strip() and workset:
        product.product_model = workset.name
    product.default_price = suite_price(pieces)
    return product


@transaction.atomic
def create_product_from_workset(workset, data):
    from logic.products import create_product

    if not workset or getattr(workset, "is_deleted", False):
        raise ValueError("دست یافت نشد.")
    pieces = normalize_suite_config(workset, data.get("pieces") or data.get("suite_config"))
    fabric_name = _first_fabric_name(pieces)
    name = (data.get("name") or "").strip() or default_product_name(workset, fabric_name)
    payload = {
        "name": name,
        "sku": (data.get("sku") or "").strip(),
        "brand": (data.get("brand") or "").strip(),
        "product_model": (data.get("product_model") or "").strip() or workset.name,
        "fabric": (data.get("fabric") or "").strip() or fabric_name,
        "description": (data.get("description") or "").strip(),
        "unit": (data.get("unit") or "عدد").strip() or "عدد",
        "default_price": data.get("default_price") if data.get("default_price") not in (None, "") else suite_price(pieces),
        "is_active": data.get("is_active", True) is not False,
        "furniture_workset_id": workset.id,
        "suite_config": pieces,
        "build_model": "frame_line",
    }
    for key in RECIPE_ID_KEYS:
        if pieces:
            payload[key] = pieces[0].get(key)
    payload["needs_paint"] = any(piece.get("needs_paint", True) for piece in pieces)
    payload["pipeline_end"] = (
        "assembly" if any(piece.get("pipeline_end") == "assembly" for piece in pieces) else "upholstery"
    )
    return create_product(payload, allow_sales_price=True, allow_materials=True)


@transaction.atomic
def create_product_from_frame(frame, data):
    from logic.products import create_product

    if not frame or getattr(frame, "is_deleted", False):
        raise ValueError("کلاف یافت نشد.")
    fabric_name = ""
    fabric_id = data.get("fabric_recipe_id")
    if fabric_id:
        from logic.workshop_recipes import resolve_recipe

        recipe = resolve_recipe(fabric_id, kind="fabric")
        fabric_name = recipe.name if recipe else ""
    name = (data.get("name") or "").strip() or default_product_name(getattr(frame, "workset", None), fabric_name)
    if not name or name == "محصول دست":
        label = piece_label(frame.piece_kind, frame.arm_style) or frame.name
        parts = []
        if frame.workset_id and frame.workset.name:
            parts.append(frame.workset.name)
        parts.append(label)
        if fabric_name:
            parts.append(fabric_name)
        name = " — ".join(parts)
    piece = frame.piece_kind
    pipeline_end = data.get("pipeline_end") or (
        "assembly" if piece in ASSEMBLY_PIECES else "upholstery"
    )
    payload = {
        "name": name,
        "sku": (data.get("sku") or "").strip(),
        "brand": (data.get("brand") or "").strip(),
        "product_model": (data.get("product_model") or "").strip() or (frame.workset.name if frame.workset_id else ""),
        "fabric": (data.get("fabric") or "").strip() or fabric_name,
        "description": (data.get("description") or "").strip(),
        "unit": (data.get("unit") or "عدد").strip() or "عدد",
        "default_price": data.get("default_price") or 0,
        "is_active": data.get("is_active", True) is not False,
        "frame_id": frame.id,
        "furniture_workset_id": frame.workset_id,
        "needs_paint": data.get("needs_paint", True) is not False,
        "pipeline_end": pipeline_end,
        "build_model": "frame_line",
        "paint_recipe_id": data.get("paint_recipe_id"),
        "fabric_recipe_id": data.get("fabric_recipe_id"),
        "foam_recipe_id": data.get("foam_recipe_id"),
        "cushion_recipe_id": data.get("cushion_recipe_id"),
        "webbing_recipe_id": data.get("webbing_recipe_id"),
    }
    if data.get("needs_paint") is False:
        payload["paint_recipe_id"] = None
    return create_product(payload, allow_sales_price=True, allow_materials=True)
