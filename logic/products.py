"""منطق کاتالوگ محصولات."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from backend.models import InventoryTransaction, Material, Product, ProductCategory, ProductVariant
from logic.materials import compute_product_material_cost, product_material_to_dict, sync_product_materials
from logic.stock_locations import (
    LOCATION_WAREHOUSE,
    default_warehouse,
    format_stock_summary,
    list_stock_locations,
    location_from_sale,
    parse_location,
    stock_breakdown_for_variant,
    stock_for_variant_at,
    variant_has_tracked_stock,
)


def category_to_dict(cat):
    if cat is None:
        return None
    return {
        "id": cat.id,
        "name": cat.name,
        "description": cat.description,
        "color": cat.color,
        "icon": cat.icon,
        "sort_order": cat.sort_order,
        "is_active": cat.is_active,
        "product_count": cat.products.filter(is_active=True, is_deleted=False).count(),
    }


def variant_to_dict(v, locations=None):
    locations = locations or list_stock_locations()
    breakdown = stock_breakdown_for_variant(v, locations)
    serialized = []
    for row in breakdown:
        qty = row["quantity"]
        serialized.append(
            {
                **row,
                "quantity": int(qty) if qty == qty.to_integral_value() else float(qty),
            }
        )
    total = v.stock
    return {
        "id": v.id,
        "color_name": v.color_name,
        "color_hex": v.color_hex,
        "sku": v.sku,
        "stock": int(total) if total == total.to_integral_value() else float(total),
        "stock_by_location": serialized,
        "stock_summary": format_stock_summary(breakdown),
        "is_active": v.is_active,
        "sort_order": v.sort_order,
    }


def product_to_dict(p, include_variants=True, *, audience="sales"):
    """audience: sales | factory | full — کنترل نمایش قیمت فروش و متریال."""
    variants = []
    if include_variants:
        locations = list_stock_locations()
        variants = [
            variant_to_dict(v, locations)
            for v in p.variants.filter(is_active=True).order_by("sort_order", "id")
        ]

    from logic.workshop_recipes import build_workset_from_product, recipe_summary

    frame = getattr(p, "frame", None)
    workset = getattr(p, "furniture_workset", None) or (getattr(frame, "workset", None) if frame else None)
    from logic.furniture_worksets import ARM_STYLE_LABELS, PIECE_KIND_LABELS, piece_label
    suite_config = list(getattr(p, "suite_config", None) or [])

    data = {
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "brand": p.brand,
        "product_model": p.product_model or "",
        "fabric": p.fabric or "",
        "description": p.description,
        "unit": p.unit,
        "attributes": p.attributes or {},
        "frame_id": p.frame_id,
        "frame": (
            {
                "id": frame.id,
                "name": frame.name,
                "piece_kind": frame.piece_kind or "",
                "piece_kind_display": PIECE_KIND_LABELS.get(frame.piece_kind, frame.piece_kind or ""),
                "arm_style": frame.arm_style or "",
                "arm_style_display": ARM_STYLE_LABELS.get(frame.arm_style, frame.arm_style or ""),
                "piece_label": piece_label(frame.piece_kind, frame.arm_style),
            }
            if frame
            else None
        ),
        "furniture_workset_id": workset.id if workset else None,
        "furniture_workset": {"id": workset.id, "name": workset.name, "seat_count": workset.seat_count} if workset else None,
        "suite_config": suite_config,
        "paint_recipe": recipe_summary(getattr(p, "paint_recipe", None)),
        "fabric_recipe": recipe_summary(getattr(p, "fabric_recipe", None)),
        "foam_recipe": recipe_summary(getattr(p, "foam_recipe", None)),
        "cushion_recipe": recipe_summary(getattr(p, "cushion_recipe", None)),
        "webbing_recipe": recipe_summary(getattr(p, "webbing_recipe", None)),
        "paint_recipe_id": p.paint_recipe_id,
        "fabric_recipe_id": p.fabric_recipe_id,
        "foam_recipe_id": p.foam_recipe_id,
        "cushion_recipe_id": p.cushion_recipe_id,
        "webbing_recipe_id": p.webbing_recipe_id,
        "build_model": getattr(p, "build_model", None) or "frame_line",
        "needs_paint": bool(getattr(p, "needs_paint", True)),
        "pipeline_end": getattr(p, "pipeline_end", None) or "upholstery",
        "workset": build_workset_from_product(p),
        "is_active": p.is_active,
        "category_id": p.category_id,
        "category": category_to_dict(p.category) if p.category_id else None,
        "variants": variants,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if getattr(p, "updated_at", None) else None,
    }

    show_sales_price = audience in {"sales", "full"}
    show_materials = audience in {"factory", "full"}

    if show_sales_price:
        data["default_price"] = int(p.default_price)
        data["display_price"] = int(p.display_price)

    if show_materials:
        materials = [
            product_material_to_dict(pm, include_cost=audience == "full")
            for pm in p.product_materials.select_related("material").filter(
                material__is_deleted=False,
                material__is_active=True,
                material__approval_status_ref_id=Material.APPROVAL_APPROVED,
            ).order_by("sort_order", "material_id")
        ]
        data["materials"] = materials
        if audience == "full":
            pricing = product_cost_pricing(p)
            material_cost = pricing["calculated_cost"]
            data["material_cost_total"] = int(material_cost)
            data["calculated_cost"] = int(pricing["calculated_cost"])
            data["cost_override"] = (
                int(p.cost_override) if p.cost_override is not None else None
            )
            data["effective_cost"] = int(pricing["effective_cost"])
            data["profit_mode"] = p.profit_mode
            data["target_margin_percent"] = (
                float(p.target_margin_percent) if p.target_margin_percent is not None else None
            )
            data["target_profit_amount"] = int(p.target_profit_amount or 0)
            data["profit_amount"] = int(pricing["profit"])
            data["suggested_sales_price"] = int(pricing["sales_price"])
        if audience == "full" and show_sales_price:
            sales_price = Decimal(p.default_price or 0)
            data["pricing_status"] = "priced" if sales_price > 0 else "pending"
            data["profit_margin"] = (
                int(sales_price - pricing["effective_cost"]) if sales_price > 0 else None
            )

    return data


def _parse_stock_quantity(value):
    if value is None or value == "":
        return None
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("موجودی واردشده نامعتبر است.")
    if quantity < 0:
        raise ValueError("موجودی هر مکان نمی‌تواند منفی باشد.")
    return quantity


def _parse_location_stocks(item):
    rows = item.get("stock_by_location")
    parsed = []
    if isinstance(rows, list):
        for row in rows:
            qty = _parse_stock_quantity(row.get("quantity") if isinstance(row, dict) else None)
            if qty is None:
                continue
            location = parse_location(row, required=True)
            parsed.append((location, qty))
        if parsed:
            return parsed
    legacy = _parse_stock_quantity(item.get("stock"))
    if legacy is None:
        return []
    warehouse = default_warehouse()
    location = parse_location(
        {"kind": LOCATION_WAREHOUSE, "warehouse_id": warehouse.id},
        required=True,
    )
    return [(location, legacy)]


def _parse_variants(raw_variants):
    if not raw_variants:
        return []
    parsed = []
    for idx, item in enumerate(raw_variants):
        color_name = (item.get("color_name") or "").strip()
        if not color_name:
            continue
        parsed.append(
            {
                "color_name": color_name,
                "color_hex": (item.get("color_hex") or "#cccccc").strip()[:7],
                "sku": (item.get("sku") or "").strip(),
                "stock_by_location": _parse_location_stocks(item),
                "is_active": bool(item.get("is_active", True)),
                "sort_order": int(item.get("sort_order") if item.get("sort_order") is not None else idx),
            }
        )
    return parsed


def _sync_variants(product, variants_data):
    from logic.inventory_settings import MANUAL_STOCK_LOCKED_MESSAGE, is_manual_stock_locked

    stock_locked = is_manual_stock_locked()
    keep_ids = []
    for item in variants_data:
        variant_id = item.get("id")
        if variant_id:
            try:
                variant = ProductVariant.objects.get(pk=variant_id, product=product)
            except ProductVariant.DoesNotExist:
                variant = ProductVariant(product=product)
        else:
            variant = ProductVariant(product=product)
        variant.color_name = item["color_name"]
        variant.color_hex = item["color_hex"]
        variant.sku = item.get("sku") or ""
        variant.price = Decimal(0)
        variant.is_active = item.get("is_active", True)
        variant.sort_order = item.get("sort_order", 0)
        variant.save()
        for location, requested_stock in item.get("stock_by_location") or []:
            locked = ProductVariant.objects.select_for_update().get(pk=variant.pk)
            current = stock_for_variant_at(locked, location)
            stock_delta = Decimal(requested_stock) - Decimal(current or 0)
            if not stock_delta:
                continue
            if stock_locked:
                raise ValueError(MANUAL_STOCK_LOCKED_MESSAGE)
            from logic.inventory_costing import adjust_stock

            adjust_stock(
                locked,
                stock_delta,
                unit_cost=0,
                location=location,
                reason="catalog_stock_adjustment",
                reference=f"product:{product.pk}",
            )
        keep_ids.append(variant.id)
    product.variants.exclude(pk__in=keep_ids).update(is_active=False)


@transaction.atomic
def create_category(data):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("نام دسته الزامی است.")
    if ProductCategory.objects.filter(name=name, is_deleted=False).exists():
        raise ValueError("دسته‌ای با این نام وجود دارد.")
    return ProductCategory.objects.create(
        name=name,
        description=(data.get("description") or "").strip(),
        color=(data.get("color") or "#6366f1").strip()[:7],
        icon=(data.get("icon") or "📦").strip()[:8],
        sort_order=int(data.get("sort_order") or 0),
        is_active=bool(data.get("is_active", True)),
    )


@transaction.atomic
def update_category(category, data):
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("نام دسته الزامی است.")
        if ProductCategory.objects.filter(name=name, is_deleted=False).exclude(pk=category.pk).exists():
            raise ValueError("دسته‌ای با این نام وجود دارد.")
        category.name = name
    if "description" in data:
        category.description = (data.get("description") or "").strip()
    if "color" in data:
        category.color = (data.get("color") or "#6366f1").strip()[:7]
    if "icon" in data:
        category.icon = (data.get("icon") or "📦").strip()[:8]
    if "sort_order" in data:
        category.sort_order = int(data.get("sort_order") or 0)
    if "is_active" in data:
        category.is_active = bool(data.get("is_active"))
    category.save()
    return category


@transaction.atomic
def _parse_target_margin(data):
    if "target_margin_percent" not in data:
        return None, False
    raw = data.get("target_margin_percent")
    if raw in (None, ""):
        return None, True
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError):
        raise ValueError("حاشیه سود هدف نامعتبر است.")
    if value < 0 or value > 100:
        raise ValueError("حاشیه سود هدف باید بین ۰ و ۱۰۰ باشد.")
    return value, True


def _parse_non_negative_money(data, key, label, *, nullable=False):
    if key not in data:
        return None, False
    raw = data.get(key)
    if nullable and raw in (None, ""):
        return None, True
    try:
        value = Decimal(str(raw or 0))
    except (InvalidOperation, TypeError):
        raise ValueError(f"{label} نامعتبر است.")
    if value < 0:
        raise ValueError(f"{label} نمی‌تواند منفی باشد.")
    return value, True


def product_cost_pricing(product):
    calculated_cost = compute_product_material_cost(product)
    effective_cost = (
        Decimal(product.cost_override)
        if getattr(product, "cost_override", None) is not None
        else calculated_cost
    )
    if getattr(product, "profit_mode", Product.PROFIT_PERCENT) == Product.PROFIT_FIXED:
        profit = Decimal(getattr(product, "target_profit_amount", 0) or 0)
    else:
        profit = (
            effective_cost
            * Decimal(getattr(product, "target_margin_percent", 0) or 0)
            / Decimal(100)
        )
    return {
        "calculated_cost": calculated_cost,
        "effective_cost": effective_cost,
        "profit": profit,
        "sales_price": (effective_cost + profit).quantize(Decimal("1")),
    }


def apply_admin_cost_pricing(product, data):
    pricing_keys = {
        "cost_override",
        "profit_mode",
        "target_margin_percent",
        "target_profit_amount",
    }
    if not pricing_keys.intersection(data):
        return product
    cost_override, has_override = _parse_non_negative_money(
        data, "cost_override", "بهای تمام‌شده اصلاحی", nullable=True
    )
    profit_amount, has_profit_amount = _parse_non_negative_money(
        data, "target_profit_amount", "مبلغ سود"
    )
    margin, has_margin = _parse_target_margin(data)
    mode = data.get("profit_mode", product.profit_mode or Product.PROFIT_PERCENT)
    if mode not in {Product.PROFIT_PERCENT, Product.PROFIT_FIXED}:
        raise ValueError("روش محاسبه سود نامعتبر است.")
    product.profit_mode = mode
    if has_override:
        product.cost_override = cost_override
    if has_profit_amount:
        product.target_profit_amount = profit_amount
    if has_margin:
        product.target_margin_percent = margin
    pricing = product_cost_pricing(product)
    product.default_price = pricing["sales_price"]
    return product


FACTORY_CATALOG_KEYS = frozenset({
    "frame_id",
    "furniture_workset_id",
    "suite_config",
    "pieces",
    "pipeline_end",
    "build_model",
    "needs_paint",
    "materials",
})

COST_PRICING_KEYS = frozenset({
    "cost_override",
    "profit_mode",
    "target_margin_percent",
    "target_profit_amount",
})

FACTORY_RECIPE_FIELDS = frozenset({
    "paint_recipe",
    "fabric_recipe",
    "foam_recipe",
    "cushion_recipe",
    "webbing_recipe",
})

OFFICE_SUITE_PIECE_KEYS = frozenset({
    "piece_kind",
    "arm_style",
    "quantity",
    "unit_price",
})

_FACTORY_PAYLOAD_DENIED = (
    "تعریف شکل محصول، دست، کلاف و دستور کار فقط در کارخانه مجاز است."
)


def _piece_identity(piece):
    if not isinstance(piece, dict):
        return None
    kind = (piece.get("piece_kind") or "").strip()
    style = (piece.get("arm_style") or "").strip()
    if not kind:
        return None
    return (kind, style)


def _is_pricing_only_suite_payload(product, raw_pieces):
    if not product or not (getattr(product, "suite_config", None) or []):
        return False
    if not isinstance(raw_pieces, list) or not raw_pieces:
        return False
    for item in raw_pieces:
        if not isinstance(item, dict):
            return False
        if set(item.keys()) - OFFICE_SUITE_PIECE_KEYS:
            return False
    existing_keys = {_piece_identity(p) for p in product.suite_config if _piece_identity(p)}
    incoming_keys = {_piece_identity(p) for p in raw_pieces if _piece_identity(p)}
    return incoming_keys and incoming_keys <= existing_keys


def _factory_fields_present(data, *, ignore_keys=None):
    ignore = ignore_keys or frozenset()
    for key, val in data.items():
        if key in ignore:
            continue
        if key in FACTORY_CATALOG_KEYS:
            if key == "materials":
                if val:
                    return True
            elif val not in (None, "", [], {}):
                return True
        if key.endswith("_recipe_id") and val not in (None, ""):
            return True
        if key in FACTORY_RECIPE_FIELDS and val not in (None, "", {}):
            return True
    return False


def _assert_factory_payload_allowed(data, allow_materials, *, product=None):
    if allow_materials:
        return
    ignore = frozenset()
    if product and ("suite_config" in data or "pieces" in data):
        raw = data.get("suite_config") if "suite_config" in data else data.get("pieces")
        if _is_pricing_only_suite_payload(product, raw):
            ignore = frozenset({"suite_config", "pieces"})
    if _factory_fields_present(data, ignore_keys=ignore):
        raise ValueError(_FACTORY_PAYLOAD_DENIED)


def apply_office_suite_pricing(product, data):
    """اداری فقط unit_price قطعات سرویس موجود را به‌روز می‌کند."""
    from logic.furniture_worksets import suite_price

    raw = data.get("suite_config") if "suite_config" in data else data.get("pieces")
    if raw is None:
        return product
    if not _is_pricing_only_suite_payload(product, raw):
        raise ValueError("به‌روزرسانی قیمت سرویس فقط برای قطعات تعریف‌شده در کارخانه مجاز است.")
    by_key = {}
    order = []
    for piece in product.suite_config or []:
        key = _piece_identity(piece)
        if not key:
            continue
        by_key[key] = dict(piece)
        order.append(key)
    for item in raw:
        key = _piece_identity(item)
        if key not in by_key:
            raise ValueError("قطعه سرویس با تعریف کارخانه مطابقت ندارد.")
        if "unit_price" in item:
            try:
                price = Decimal(str(item.get("unit_price") or 0))
            except (InvalidOperation, TypeError):
                raise ValueError("قیمت قطعه نامعتبر است.")
            if price < 0:
                raise ValueError("قیمت قطعه نمی‌تواند منفی باشد.")
            by_key[key]["unit_price"] = str(int(price))
    product.suite_config = [by_key[key] for key in order]
    product.default_price = suite_price(product.suite_config)
    return product


def create_product(
    data, *, allow_sales_price=True, allow_materials=False, allow_cost_pricing=False
):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("نام محصول الزامی است.")
    if COST_PRICING_KEYS.intersection(data) and not allow_cost_pricing:
        raise ValueError("ثبت بهای تمام‌شده و سود فقط در بخش اداری مجاز است.")
    _assert_factory_payload_allowed(data, allow_materials)
    default_price = Decimal(0)
    if allow_sales_price and "default_price" in data:
        try:
            default_price = Decimal(str(data.get("default_price") or 0))
        except (InvalidOperation, TypeError):
            raise ValueError("قیمت نامعتبر است.")
    elif allow_materials and "default_price" in data and not (data.get("suite_config") or data.get("pieces")):
        try:
            default_price = Decimal(str(data.get("default_price") or 0))
        except (InvalidOperation, TypeError):
            raise ValueError("قیمت نامعتبر است.")
    if allow_cost_pricing:
        target_margin, _has_margin = _parse_target_margin(data)
    else:
        target_margin = None

    category = None
    category_id = data.get("category_id")
    if category_id:
        category = ProductCategory.objects.filter(pk=category_id, is_deleted=False).first()
        if not category:
            raise ValueError("دسته انتخاب‌شده یافت نشد.")

    attrs = data.get("attributes")
    if attrs is not None and not isinstance(attrs, dict):
        raise ValueError("ویژگی‌های سفارشی باید شیء JSON باشد.")

    product = Product.objects.create(
        name=name,
        sku=(data.get("sku") or "").strip(),
        brand=(data.get("brand") or "").strip(),
        product_model=(data.get("product_model") or "").strip(),
        fabric=(data.get("fabric") or "").strip(),
        description=(data.get("description") or "").strip(),
        unit=(data.get("unit") or "عدد").strip() or "عدد",
        attributes=attrs or {},
        default_price=default_price,
        target_margin_percent=target_margin,
        is_active=bool(data.get("is_active", True)),
        category=category,
    )

    variants_data = _parse_variants(data.get("variants"))
    if variants_data:
        _sync_variants(product, variants_data)

    if allow_materials and "materials" in data:
        sync_product_materials(product, data.get("materials"))

    if allow_materials:
        from logic.workshop_recipes import apply_product_workset

        apply_product_workset(product, data)
    if allow_cost_pricing:
        apply_admin_cost_pricing(product, data)
    product.save()

    return product


@transaction.atomic
def update_product(
    product, data, *, allow_sales_price=True, allow_materials=False, allow_cost_pricing=False
):
    if COST_PRICING_KEYS.intersection(data) and not allow_cost_pricing:
        raise ValueError("ثبت بهای تمام‌شده و سود فقط در بخش اداری مجاز است.")
    factory_product = bool(
        getattr(product, "furniture_workset_id", None)
        or getattr(product, "frame_id", None)
        or (getattr(product, "suite_config", None) or [])
    )
    if factory_product and not allow_materials and not allow_cost_pricing and (
        "default_price" in data or "suite_config" in data or "pieces" in data
    ):
        raise ValueError("قیمت محصول کارخانه فقط توسط اداری و از بهای تمام‌شده ثبت می‌شود.")
    _assert_factory_payload_allowed(data, allow_materials, product=product)
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("نام محصول الزامی است.")
        product.name = name
    if "sku" in data:
        product.sku = (data.get("sku") or "").strip()
    if "brand" in data:
        product.brand = (data.get("brand") or "").strip()
    if "product_model" in data:
        product.product_model = (data.get("product_model") or "").strip()
    if "fabric" in data:
        product.fabric = (data.get("fabric") or "").strip()
    if "description" in data:
        product.description = (data.get("description") or "").strip()
    if "unit" in data:
        product.unit = (data.get("unit") or "عدد").strip() or "عدد"
    if "attributes" in data:
        attrs = data.get("attributes")
        if attrs is not None and not isinstance(attrs, dict):
            raise ValueError("ویژگی‌های سفارشی باید شیء JSON باشد.")
        product.attributes = attrs or {}
    if allow_sales_price and "default_price" in data:
        try:
            product.default_price = Decimal(str(data.get("default_price") or 0))
        except (InvalidOperation, TypeError):
            raise ValueError("قیمت نامعتبر است.")
    if "is_active" in data:
        product.is_active = bool(data.get("is_active"))
    if "category_id" in data:
        category_id = data.get("category_id")
        if category_id:
            category = ProductCategory.objects.filter(pk=category_id, is_deleted=False).first()
            if not category:
                raise ValueError("دسته انتخاب‌شده یافت نشد.")
            product.category = category
        else:
            product.category = None

    product.save()

    if "variants" in data:
        variants_data = _parse_variants(data.get("variants"))
        for item, raw in zip(variants_data, data.get("variants") or []):
            if raw.get("id"):
                item["id"] = raw["id"]
        _sync_variants(product, variants_data)

    if allow_materials and "materials" in data:
        sync_product_materials(product, data.get("materials"))

    if allow_sales_price and not allow_materials and ("suite_config" in data or "pieces" in data):
        apply_office_suite_pricing(product, data)
    elif allow_materials:
        from logic.workshop_recipes import apply_product_workset

        apply_product_workset(product, data)
    if allow_cost_pricing:
        apply_admin_cost_pricing(product, data)
    product.save()

    return product


def resolve_catalog_price(product, variant=None):
    """قیمت مؤثر فقط از فیلد قیمت محصول."""
    if product is None:
        return Decimal(0)
    return Decimal(product.default_price or 0)


def filter_products(queryset, *, search="", category_id=None, active_only=True, workset_id=None):
    if active_only:
        queryset = queryset.filter(is_active=True, is_deleted=False)
    if category_id:
        queryset = queryset.filter(category_id=category_id)
    if workset_id:
        queryset = queryset.filter(
            Q(furniture_workset_id=workset_id) | Q(frame__workset_id=workset_id, frame__is_deleted=False)
        )
    if search:
        q = Q(name__icontains=search) | Q(sku__icontains=search) | Q(brand__icontains=search)
        q |= Q(variants__color_name__icontains=search)
        q |= Q(frame__workset__name__icontains=search)
        queryset = queryset.filter(q).distinct()
    return queryset.select_related(
        "category",
        "frame",
        "frame__workset",
        "furniture_workset",
        "paint_recipe",
        "fabric_recipe",
        "foam_recipe",
        "cushion_recipe",
        "webbing_recipe",
    ).prefetch_related("variants", "product_materials__material")


def _resolve_line_workset(product, item):
    from logic.workshop_recipes import merge_workset_config

    incoming = item.get("workset_config") if isinstance(item.get("workset_config"), dict) else None
    return merge_workset_config(product, incoming)


def resolve_line_item_from_catalog(item):
    """نگاشت ردیف فروش از کاتالوگ — قیمت فقط از تعریف محصول."""
    from backend.models import Frame, FrameModel, FurnitureWorkset

    product_id = item.get("product_id")
    variant_id = item.get("variant_id")
    if not product_id and not variant_id:
        return None

    product = None
    variant = None
    name = ""
    color_name = ""
    color_hex = ""
    product_model = ""
    fabric = ""
    price = Decimal(0)
    frame = None
    frame_model = None
    frame_config = item.get("frame_config") if isinstance(item.get("frame_config"), dict) else {}

    if variant_id:
        variant = ProductVariant.objects.select_related(
            "product", "product__furniture_workset", "product__frame", "product__frame__workset"
        ).filter(pk=variant_id, is_active=True).first()
        if variant:
            product = variant.product
    elif product_id:
        product = Product.objects.select_related("furniture_workset", "frame", "frame__workset").filter(
            pk=product_id, is_active=True, is_deleted=False
        ).first()
        if product:
            variant = product.variants.filter(is_active=True).order_by("sort_order", "id").first()

    quoted = None
    if product:
        name = product.name
        product_model = product.product_model or ""
        fabric = product.fabric or ""
        if variant:
            color_name = variant.color_name
            color_hex = variant.color_hex
        from logic.workshop_recipes import sale_finish_quote

        quoted = sale_finish_quote(product, item)
        price = quoted["unit_price"] if quoted else resolve_catalog_price(product)
        if quoted:
            fabric = quoted["fabric_label"]
            if quoted["paint_label"]:
                color_name = quoted["paint_label"]

    if not product or not name:
        return None
    require_price = item.get("require_price", True)
    if require_price and price <= 0:
        if quoted:
            raise ValueError(f"قیمت «{name}» از متراژ پارچه حساب نشد.")
        raise ValueError(f"محصول «{name}» قیمت ندارد — ابتدا در بخش محصولات قیمت را تنظیم کنید.")

    frame_id = item.get("frame_id") or product.frame_id
    if frame_id:
        frame = Frame.objects.select_related("workset").filter(
            pk=frame_id, is_deleted=False, is_active=True
        ).first()
        if not frame:
            raise ValueError("کلاف انتخاب‌شده یافت نشد.")
        frame_model_id = item.get("frame_model_id")
        if frame_model_id:
            frame_model = FrameModel.objects.filter(
                pk=frame_model_id, frame=frame, is_active=True
            ).first()
            if not frame_model:
                raise ValueError("مدل کلاف انتخاب‌شده یافت نشد.")
        else:
            frame_model = frame.models.filter(is_active=True).order_by("sort_order", "id").first()
        if not frame_config:
            frame_config = {}

    furniture_workset = None
    workset_id = item.get("furniture_workset_id")
    if workset_id:
        furniture_workset = FurnitureWorkset.objects.filter(pk=workset_id, is_deleted=False).first()
        if not furniture_workset:
            raise ValueError("دست انتخاب‌شده یافت نشد.")
    elif getattr(product, "furniture_workset_id", None):
        furniture_workset = product.furniture_workset
    elif frame and frame.workset_id:
        furniture_workset = frame.workset

    return {
        "product": product,
        "variant": variant,
        "product_name": name,
        "product_model": product_model,
        "fabric": fabric,
        "color_name": color_name,
        "color_hex": color_hex,
        "unit_price": price,
        "quantity": int(item.get("quantity") or 1),
        "frame": frame,
        "frame_model": frame_model,
        "frame_config": frame_config or {},
        "workset_config": quoted["workset_config"] if quoted else _resolve_line_workset(product, item),
        "furniture_workset": furniture_workset,
    }


SALE_STOCK_REASON = "sale"
SALE_STOCK_ROLLBACK_REASON = "sale_rollback"


def _sale_line_stock_reference(sale, line):
    return f"sale:{sale.pk}:line:{line.pk}"


def _format_stock_qty(value):
    value = Decimal(value or 0)
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


def _lock_variants(variant_ids):
    ids = sorted({vid for vid in variant_ids if vid})
    if not ids:
        return {}
    rows = list(
        ProductVariant.objects.select_for_update()
        .select_related("product")
        .filter(pk__in=ids)
        .order_by("pk")
    )
    return {variant.pk: variant for variant in rows}


def _variant_label(variant):
    name = variant.product.name if variant.product_id else "محصول"
    if variant.color_name:
        return f"{name} ({variant.color_name})"
    return name


def deduct_variant_stock_for_sale(sale, *, recorded_by=None):
    """کسر موجودی رنگ محصول با قفل ردیف — جلوگیری از فروش همزمان بیش از موجودی."""
    from collections import defaultdict

    from backend.models import Sale

    Sale.objects.select_for_update().get(pk=sale.pk)
    location = location_from_sale(sale)
    if location is None:
        warehouse = default_warehouse()
        location = parse_location({"kind": LOCATION_WAREHOUSE, "warehouse_id": warehouse.id}, required=True)
    lines = [line for line in sale.line_items.all() if line.variant_id]
    if not lines:
        return

    pending_by_variant = defaultdict(list)
    for line in lines:
        reference = _sale_line_stock_reference(sale, line)
        if InventoryTransaction.objects.filter(reference=reference, reason=SALE_STOCK_REASON).exists():
            continue
        pending_by_variant[line.variant_id].append(line)

    if not pending_by_variant:
        return

    locked = _lock_variants(pending_by_variant)
    for variant_id, variant_lines in pending_by_variant.items():
        variant = locked.get(variant_id)
        if variant is None:
            continue
        if not variant_has_tracked_stock(variant):
            continue
        needed = sum((Decimal(line.quantity or 0) for line in variant_lines), Decimal(0))
        stock = Decimal(stock_for_variant_at(variant, location) or 0)
        if stock < needed:
            raise ValueError(
                f"موجودی «{_variant_label(variant)}» در {location['label']} کافی نیست — "
                f"موجود {_format_stock_qty(stock)}، درخواست {_format_stock_qty(needed)}."
            )
        for line in variant_lines:
            qty = Decimal(line.quantity or 0)
            if qty <= 0:
                continue
            from logic.inventory_costing import consume_stock

            consume_stock(
                variant,
                qty,
                location=location,
                reason=SALE_STOCK_REASON,
                reference=_sale_line_stock_reference(sale, line),
                user=recorded_by,
                sale=sale,
            )


def restore_variant_stock_for_sale(sale, *, recorded_by=None):
    """بازگشت موجودی کسرشدهٔ فروش — برای حذف، لغو یا ویرایش اقلام."""
    from backend.models import Sale

    Sale.objects.select_for_update().get(pk=sale.pk)
    deducted = list(
        InventoryTransaction.objects.filter(
            reference__startswith=f"sale:{sale.pk}:line:",
            reason=SALE_STOCK_REASON,
            variant_id__isnull=False,
        )
    )
    pending = []
    for tx in deducted:
        if InventoryTransaction.objects.filter(
            reference=tx.reference, reason=SALE_STOCK_ROLLBACK_REASON
        ).exists():
            continue
        pending.append(tx)
    if not pending:
        return

    locked = _lock_variants(tx.variant_id for tx in pending)
    for tx in pending:
        variant = locked.get(tx.variant_id)
        if variant is None:
            continue
        from logic.inventory_costing import adjust_stock

        location = {
            "kind": tx.location_kind,
            "warehouse": tx.warehouse,
            "warehouse_id": tx.warehouse_id,
            "branch": tx.branch,
            "branch_id": tx.branch_id,
        }
        adjust_stock(
            variant,
            -tx.quantity,
            unit_cost=tx.unit_cost,
            location=location,
            reason=SALE_STOCK_ROLLBACK_REASON,
            reference=tx.reference,
            user=recorded_by,
        )
