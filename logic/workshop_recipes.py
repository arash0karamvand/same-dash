"""کاتالوگ دستور دست‌کار و اسنپ‌شات سفارش."""

from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q

from backend.models import (
    FabricCatalogNode,
    LookupOption,
    Material,
    Product,
    WorkshopRecipe,
    WorkshopRecipeMaterial,
)
from logic.dynamic_choices import choice_dict, fabric_countries, paint_units
from logic.lookups import create_lookup, get_lookup_choices

RECIPE_KINDS = choice_dict("workshop_recipe_kind") or dict(WorkshopRecipe.KIND_CHOICES)
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

PAINT_CATEGORIES = choice_dict("workshop_paint_category") or dict(WorkshopRecipe.PAINT_CATEGORY_CHOICES)
PAINT_UNITS = paint_units() or set(WorkshopRecipe.PAINT_UNITS)
PAINT_ITEM_CATEGORY = "paint_item"
STOCK_STATUS_ZERO = "zero"
STOCK_STATUS_LOW = "low"
STOCK_STATUS_OK = "ok"
PAINT_CODE_PREFIX = "PNT-"
FABRIC_ITEM_CATEGORY = "fabric_item"
FABRIC_COMPANY_CATEGORY = "fabric_company"
FABRIC_CODE_PREFIX = "KLT-"
FABRIC_COUNTRIES = fabric_countries() or set(WorkshopRecipe.FABRIC_COUNTRIES)
FABRIC_CATEGORIES = choice_dict("workshop_fabric_category") or dict(WorkshopRecipe.FABRIC_CATEGORY_CHOICES)
FABRIC_COMPANIES = choice_dict("workshop_fabric_company") or dict(WorkshopRecipe.FABRIC_COMPANY_CHOICES)
FABRIC_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp"}
FABRIC_IMAGE_MAX_BYTES = 1_200_000
FABRIC_GALLERY_LIMIT = 3
FABRIC_NODE_PARENT = {
    FabricCatalogNode.KIND_COUNTRY: None,
    FabricCatalogNode.KIND_BRAND: FabricCatalogNode.KIND_COUNTRY,
    FabricCatalogNode.KIND_COLOR: FabricCatalogNode.KIND_BRAND,
    FabricCatalogNode.KIND_TYPE: FabricCatalogNode.KIND_COLOR,
}


def _text(value, default=""):
    return str(value).strip() if value is not None else default


def _optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _non_negative(value, label, default="0"):
    try:
        number = Decimal(str(value if value not in (None, "") else default))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} نامعتبر است.")
    if number < 0:
        raise ValueError(f"{label} نمی‌تواند منفی باشد.")
    return number


def _as_number(value):
    number = Decimal(value or 0)
    if number == number.to_integral():
        return int(number)
    return float(number)


def _stock_status(stock, minimum):
    if stock <= 0:
        return STOCK_STATUS_ZERO
    if stock <= minimum:
        return STOCK_STATUS_LOW
    return STOCK_STATUS_OK


def _next_prefixed_code(prefix):
    numbers = []
    codes = WorkshopRecipe.all_objects.filter(item_code__startswith=prefix).values_list("item_code", flat=True)
    for code in codes:
        suffix = str(code)[len(prefix) :]
        if suffix.isdigit():
            numbers.append(int(suffix))
    return f"{prefix}{max(numbers, default=0) + 1:04d}"


def _next_paint_code():
    return _next_prefixed_code(PAINT_CODE_PREFIX)


def _ensure_unique_code(code, exclude_id=None):
    qs = WorkshopRecipe.all_objects.filter(item_code=code)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    if qs.exists():
        raise ValueError("کد رهگیری تکراری است.")


def _claim_item_code(recipe, requested, *, prefix=PAINT_CODE_PREFIX):
    code = _text(requested)
    if code:
        _ensure_unique_code(code, exclude_id=recipe.pk)
        recipe.item_code = code
        return
    for _ in range(5):
        candidate = _next_prefixed_code(prefix)
        if not WorkshopRecipe.all_objects.filter(item_code=candidate).exclude(pk=recipe.pk).exists():
            recipe.item_code = candidate
            return
    raise ValueError("ساخت کد رهگیری ناموفق بود.")


def paint_category_labels():
    labels = dict(PAINT_CATEGORIES)
    for item in get_lookup_choices(PAINT_ITEM_CATEGORY):
        labels[item["code"]] = item["label"]
    return labels


def list_paint_categories():
    rows = [
        {"code": code, "label": label, "builtin": True}
        for code, label in WorkshopRecipe.PAINT_CATEGORY_CHOICES
    ]
    known = set(PAINT_CATEGORIES)
    for item in get_lookup_choices(PAINT_ITEM_CATEGORY):
        if item["code"] in known:
            continue
        rows.append({"code": item["code"], "label": item["label"], "builtin": False})
    return rows


def _next_paint_category_code():
    number = LookupOption.objects.filter(category=PAINT_ITEM_CATEGORY).count() + 1
    while True:
        code = f"c{number}"
        if code not in PAINT_CATEGORIES and not LookupOption.objects.filter(
            category=PAINT_ITEM_CATEGORY, code=code
        ).exists():
            return code
        number += 1


def create_paint_category(label):
    name = _text(label)
    if not name:
        raise ValueError("نام دسته‌بندی را وارد کنید.")
    if len(name) > 80:
        raise ValueError("نام دسته‌بندی طولانی است.")
    taken = set(PAINT_CATEGORIES.values())
    taken.update(
        LookupOption.objects.filter(category=PAINT_ITEM_CATEGORY).values_list("label", flat=True)
    )
    if name in taken:
        raise ValueError("این دسته‌بندی قبلاً ثبت شده.")
    return create_lookup(
        category=PAINT_ITEM_CATEGORY,
        code=_next_paint_category_code(),
        label=name,
        sort_order=100 + LookupOption.objects.filter(category=PAINT_ITEM_CATEGORY).count(),
    )


def _paint_category_ok(code):
    if code in PAINT_CATEGORIES:
        return True
    return LookupOption.objects.filter(
        category=PAINT_ITEM_CATEGORY, code=code, is_active=True
    ).exists()


def _list_catalog_options(choices, lookup_category):
    rows = [{"code": code, "label": label, "builtin": True} for code, label in choices]
    known = {code for code, _label in choices}
    for item in get_lookup_choices(lookup_category):
        if item["code"] in known:
            continue
        rows.append({"code": item["code"], "label": item["label"], "builtin": False})
    return rows


def _labels_for(choices, lookup_category):
    labels = dict(choices)
    for item in get_lookup_choices(lookup_category):
        labels[item["code"]] = item["label"]
    return labels


def _option_ok(code, choices, lookup_category):
    if code in dict(choices):
        return True
    return LookupOption.objects.filter(
        category=lookup_category, code=code, is_active=True
    ).exists()


def _next_catalog_code(lookup_category, prefix, builtin_codes):
    number = LookupOption.objects.filter(category=lookup_category).count() + 1
    while True:
        code = f"{prefix}{number}"
        if code not in builtin_codes and not LookupOption.objects.filter(
            category=lookup_category, code=code
        ).exists():
            return code
        number += 1


def _create_catalog_option(label, *, choices, lookup_category, code_prefix, noun):
    name = _text(label)
    if not name:
        raise ValueError(f"نام {noun} را وارد کنید.")
    if len(name) > 80:
        raise ValueError(f"نام {noun} طولانی است.")
    taken = {item_label for _code, item_label in choices}
    taken.update(
        LookupOption.objects.filter(category=lookup_category).values_list("label", flat=True)
    )
    if name in taken:
        raise ValueError(f"این {noun} قبلاً ثبت شده.")
    return create_lookup(
        category=lookup_category,
        code=_next_catalog_code(lookup_category, code_prefix, {code for code, _label in choices}),
        label=name,
        sort_order=100 + LookupOption.objects.filter(category=lookup_category).count(),
    )


def list_fabric_categories():
    return _list_catalog_options(WorkshopRecipe.FABRIC_CATEGORY_CHOICES, FABRIC_ITEM_CATEGORY)


def list_fabric_companies():
    return _list_catalog_options(WorkshopRecipe.FABRIC_COMPANY_CHOICES, FABRIC_COMPANY_CATEGORY)


def fabric_category_labels():
    return _labels_for(WorkshopRecipe.FABRIC_CATEGORY_CHOICES, FABRIC_ITEM_CATEGORY)


def fabric_company_labels():
    return _labels_for(WorkshopRecipe.FABRIC_COMPANY_CHOICES, FABRIC_COMPANY_CATEGORY)


def create_fabric_category(label):
    return _create_catalog_option(
        label,
        choices=WorkshopRecipe.FABRIC_CATEGORY_CHOICES,
        lookup_category=FABRIC_ITEM_CATEGORY,
        code_prefix="f",
        noun="دسته‌بندی",
    )


def create_fabric_company(label):
    return _create_catalog_option(
        label,
        choices=WorkshopRecipe.FABRIC_COMPANY_CHOICES,
        lookup_category=FABRIC_COMPANY_CATEGORY,
        code_prefix="m",
        noun="شرکت",
    )


def _apply_paint_item(recipe, data, *, creating):
    if recipe.kind != WorkshopRecipe.KIND_PAINT:
        return
    category = _text(
        data.get("paint_category") if creating or "paint_category" in data else recipe.paint_category
    )
    unit = _text(data.get("stock_unit") if creating or "stock_unit" in data else recipe.stock_unit)
    if not category:
        raise ValueError("دسته‌بندی رنگ را انتخاب کنید.")
    if not _paint_category_ok(category):
        raise ValueError("دسته‌بندی رنگ نامعتبر است.")
    if not unit:
        raise ValueError("واحد شمارش را انتخاب کنید.")
    if unit not in PAINT_UNITS:
        raise ValueError("واحد شمارش نامعتبر است.")
    stock = _non_negative(
        data.get("current_stock") if creating or "current_stock" in data else recipe.current_stock,
        "موجودی",
    )
    minimum = _non_negative(
        data.get("min_stock") if creating or "min_stock" in data else recipe.min_stock,
        "نقطه سفارش",
    )
    cost = _non_negative(
        data.get("unit_cost") if creating or "unit_cost" in data else recipe.unit_cost,
        "نرخ واحد",
    )
    recipe.paint_category = category
    recipe.stock_unit = unit
    recipe.current_stock = stock
    recipe.min_stock = minimum
    recipe.unit_cost = cost
    if creating or "brand" in data:
        recipe.brand = _text(data.get("brand"))
    if creating or "storage_shelf" in data:
        recipe.storage_shelf = _text(data.get("storage_shelf"))
    if creating or "technical_specs" in data:
        recipe.technical_specs = _text(data.get("technical_specs"))
    requested = data.get("item_code") if creating or "item_code" in data else recipe.item_code
    _claim_item_code(recipe, requested)


def _fabric_image(value, label):
    text = _text(value)
    if not text:
        return ""
    lowered = text.lower()
    if lowered.startswith(("http://", "https://")):
        raise ValueError("لینک تصویر پذیرفته نمی‌شود. فایل را آپلود کنید.")
    if not lowered.startswith("data:image/"):
        raise ValueError(f"{label} نامعتبر است.")
    header, _, payload = text.partition(",")
    if not payload:
        raise ValueError(f"{label} خالی است.")
    mime = header[5:].split(";")[0].strip().lower()
    if mime not in FABRIC_IMAGE_MIMES:
        raise ValueError("فقط تصویر PNG، JPEG یا WebP پذیرفته می‌شود.")
    if len(text.encode("utf-8")) > FABRIC_IMAGE_MAX_BYTES:
        raise ValueError(f"{label} بزرگ‌تر از حدود ۱ مگابایت است.")
    return text


def _gallery_images(value):
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("گالری تصویر نامعتبر است.")
    images = []
    for item in value:
        image = _fabric_image(item, "تصویر گالری")
        if image and image not in images:
            images.append(image)
    if len(images) > FABRIC_GALLERY_LIMIT:
        raise ValueError("حداکثر سه تصویر اضافه مجاز است.")
    return images


def _catalog_node(node_id, kind, label):
    if not node_id:
        raise ValueError(f"{label} را انتخاب کنید.")
    node = FabricCatalogNode.objects.filter(pk=node_id, kind=kind).first()
    if not node:
        raise ValueError(f"{label} نامعتبر است.")
    return node


def fabric_named_ids(*, country="ایران", brand="بافندگی نورا", color="استخوانی", cloth="مخمل ساده"):
    country_node = FabricCatalogNode.objects.filter(
        kind=FabricCatalogNode.KIND_COUNTRY, name=country, parent__isnull=True
    ).first()
    brand_node = (
        FabricCatalogNode.objects.filter(
            kind=FabricCatalogNode.KIND_BRAND, name=brand, parent=country_node
        ).first()
        if country_node
        else None
    )
    color_node = (
        FabricCatalogNode.objects.filter(
            kind=FabricCatalogNode.KIND_COLOR, name=color, parent=brand_node
        ).first()
        if brand_node
        else None
    )
    cloth_node = (
        FabricCatalogNode.objects.filter(
            kind=FabricCatalogNode.KIND_TYPE, name=cloth, parent=color_node
        ).first()
        if color_node
        else None
    )
    if not all((country_node, brand_node, color_node, cloth_node)):
        raise ValueError("زنجیره نمونه کاتالوگ پارچه یافت نشد.")
    return {
        "fabric_country_id": country_node.id,
        "fabric_brand_id": brand_node.id,
        "fabric_color_id": color_node.id,
        "fabric_type_id": cloth_node.id,
    }


def _node_to_dict(node, children):
    return {
        "id": node.id,
        "kind": node.kind,
        "name": node.name,
        "parent_id": node.parent_id,
        "children": children,
    }


def list_fabric_catalog():
    nodes = list(FabricCatalogNode.objects.all())
    by_parent = {}
    for node in nodes:
        by_parent.setdefault(node.parent_id, []).append(node)

    def build(parent_id):
        rows = []
        for node in by_parent.get(parent_id, []):
            rows.append(_node_to_dict(node, build(node.id)))
        return rows

    brands = []
    colors = []
    types = []
    by_id = {node.id: node for node in nodes}
    for node in nodes:
        if node.kind == FabricCatalogNode.KIND_BRAND:
            country = by_id.get(node.parent_id)
            brands.append({
                "id": node.id,
                "name": node.name,
                "country_id": node.parent_id,
                "country_name": country.name if country else "",
            })
        elif node.kind == FabricCatalogNode.KIND_COLOR:
            brand = by_id.get(node.parent_id)
            colors.append({
                "id": node.id,
                "name": node.name,
                "brand_id": node.parent_id,
                "brand_name": brand.name if brand else "",
            })
        elif node.kind == FabricCatalogNode.KIND_TYPE:
            color = by_id.get(node.parent_id)
            brand = by_id.get(color.parent_id) if color else None
            types.append({
                "id": node.id,
                "name": node.name,
                "color_id": node.parent_id,
                "color_name": color.name if color else "",
                "brand_name": brand.name if brand else "",
            })
    return {"tree": build(None), "brands": brands, "colors": colors, "types": types}


def create_catalog_node(data):
    kind = _text(data.get("kind") if isinstance(data, dict) else "")
    name = _text(data.get("name") if isinstance(data, dict) else "")
    if kind not in FABRIC_NODE_PARENT:
        raise ValueError("نوع گره نامعتبر است.")
    if not name:
        raise ValueError("نام را وارد کنید.")
    if len(name) > 80:
        raise ValueError("نام طولانی است.")
    parent_kind = FABRIC_NODE_PARENT[kind]
    parent = None
    if parent_kind:
        parent = _catalog_node(
            _optional_int(data.get("parent_id")),
            parent_kind,
            "والد",
        )
    elif data.get("parent_id"):
        raise ValueError("کشور والد ندارد.")
    siblings = FabricCatalogNode.objects.filter(parent=parent, name=name)
    if siblings.exists():
        raise ValueError("این مورد قبلاً ثبت شده.")
    return FabricCatalogNode.objects.create(kind=kind, name=name, parent=parent)


def delete_catalog_node(node):
    if node.children.exists():
        raise ValueError("این مورد فرزند دارد و قابل حذف نیست.")
    linked = WorkshopRecipe.objects.filter(
        Q(fabric_country=node) | Q(fabric_brand=node) | Q(fabric_color=node) | Q(fabric_type=node)
    ).exists()
    if linked:
        raise ValueError("این مورد در کالیته استفاده شده و قابل حذف نیست.")
    try:
        node.delete()
    except ProtectedError as exc:
        raise ValueError("این مورد قابل حذف نیست.") from exc


def _roll_count(value, default=1):
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError("تعداد طاقه نامعتبر است.")
    if number < 0:
        raise ValueError("تعداد طاقه نمی‌تواند منفی باشد.")
    return number


def _picked_node_id(data, key, current_id, *, creating):
    if creating or key in data:
        return _optional_int(data.get(key))
    return current_id


def _apply_fabric_item(recipe, data, *, creating):
    if recipe.kind != WorkshopRecipe.KIND_FABRIC:
        return
    country = _catalog_node(
        _picked_node_id(data, "fabric_country_id", recipe.fabric_country_id, creating=creating),
        FabricCatalogNode.KIND_COUNTRY,
        "کشور",
    )
    brand = _catalog_node(
        _picked_node_id(data, "fabric_brand_id", recipe.fabric_brand_id, creating=creating),
        FabricCatalogNode.KIND_BRAND,
        "برند",
    )
    color = _catalog_node(
        _picked_node_id(data, "fabric_color_id", recipe.fabric_color_id, creating=creating),
        FabricCatalogNode.KIND_COLOR,
        "رنگ",
    )
    cloth = _catalog_node(
        _picked_node_id(data, "fabric_type_id", recipe.fabric_type_id, creating=creating),
        FabricCatalogNode.KIND_TYPE,
        "جنس پارچه",
    )
    if brand.parent_id != country.id:
        raise ValueError("برند با کشور انتخاب‌شده هم‌خوان نیست.")
    if color.parent_id != brand.id:
        raise ValueError("رنگ با برند انتخاب‌شده هم‌خوان نیست.")
    if cloth.parent_id != color.id:
        raise ValueError("جنس با رنگ انتخاب‌شده هم‌خوان نیست.")
    stock = _non_negative(
        data.get("current_stock") if creating or "current_stock" in data else recipe.current_stock,
        "متراژ",
    )
    minimum = _non_negative(
        data.get("min_stock") if creating or "min_stock" in data else recipe.min_stock,
        "حداقل هشدار",
    )
    cost = _non_negative(
        data.get("unit_cost") if creating or "unit_cost" in data else recipe.unit_cost,
        "قیمت هر متر",
    )
    rolls = _roll_count(
        data.get("roll_count") if creating or "roll_count" in data else recipe.roll_count,
        default=1,
    )
    recipe.fabric_country = country
    recipe.fabric_brand = brand
    recipe.fabric_color = color
    recipe.fabric_type = cloth
    recipe.color_name = color.name
    recipe.origin_country = country.name
    recipe.stock_unit = WorkshopRecipe.FABRIC_STOCK_UNIT
    recipe.current_stock = stock
    recipe.min_stock = minimum
    recipe.unit_cost = cost
    recipe.roll_count = rolls
    if creating or "image_url" in data:
        recipe.image_url = _fabric_image(data.get("image_url"), "تصویر کالیته")
    if creating or "gallery_urls" in data:
        recipe.gallery_urls = _gallery_images(data.get("gallery_urls"))
    if creating or "technical_specs" in data:
        recipe.technical_specs = _text(data.get("technical_specs"))
    requested = data.get("item_code") if creating or "item_code" in data else recipe.item_code
    _claim_item_code(recipe, requested, prefix=FABRIC_CODE_PREFIX)


def _save_recipe(recipe):
    try:
        recipe.save()
    except IntegrityError as exc:
        if "item_code" in str(exc):
            raise ValueError("کد رهگیری تکراری است.") from exc
        raise


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
        "normal_spoilage_rate": float(row.normal_spoilage_rate or 0),
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
        "item_code": recipe.item_code or "",
        "paint_category": recipe.paint_category or "",
        "paint_category_display": paint_category_labels().get(recipe.paint_category, ""),
        "brand": recipe.brand or "",
        "stock_unit": recipe.stock_unit or "",
        "current_stock": _as_number(recipe.current_stock),
        "min_stock": _as_number(recipe.min_stock),
        "storage_shelf": recipe.storage_shelf or "",
        "unit_cost": _as_number(recipe.unit_cost),
        "technical_specs": recipe.technical_specs or "",
        "fabric_category": recipe.fabric_category or "",
        "fabric_category_display": (
            recipe.fabric_type.name
            if getattr(recipe, "fabric_type_id", None) and getattr(recipe, "fabric_type", None)
            else fabric_category_labels().get(recipe.fabric_category, "")
        ),
        "company_code": recipe.company_code or "",
        "company_display": (
            recipe.fabric_brand.name
            if getattr(recipe, "fabric_brand_id", None) and getattr(recipe, "fabric_brand", None)
            else fabric_company_labels().get(recipe.company_code, "")
        ),
        "origin_country": (
            recipe.fabric_country.name
            if getattr(recipe, "fabric_country_id", None) and getattr(recipe, "fabric_country", None)
            else recipe.origin_country or ""
        ),
        "fabric_country_id": recipe.fabric_country_id,
        "fabric_brand_id": recipe.fabric_brand_id,
        "fabric_color_id": recipe.fabric_color_id,
        "fabric_type_id": recipe.fabric_type_id,
        "fabric_type_name": recipe.fabric_type.name if getattr(recipe, "fabric_type_id", None) and recipe.fabric_type else "",
        "roll_count": int(recipe.roll_count or 0),
        "image_url": recipe.image_url or "",
        "gallery_urls": list(recipe.gallery_urls or []),
        "stock_value": _as_number((recipe.current_stock or 0) * (recipe.unit_cost or 0)),
        "stock_status": _stock_status(recipe.current_stock or 0, recipe.min_stock or 0),
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


def _codes_for_label_search(choices, lookup_category, search):
    needle = search.casefold()
    codes = [code for code, label in choices if needle in str(label).casefold()]
    codes.extend(
        LookupOption.objects.filter(category=lookup_category, label__icontains=search).values_list(
            "code", flat=True
        )
    )
    return codes


def filter_recipes(
    qs,
    *,
    kind="",
    search="",
    active_only=True,
    company="",
    category="",
    country="",
    brand_id="",
    color_id="",
    type_id="",
):
    if kind:
        qs = qs.filter(kind=kind)
    if active_only:
        qs = qs.filter(is_active=True)
    if company:
        qs = qs.filter(company_code=company)
    if category:
        qs = qs.filter(fabric_category=category)
    if country:
        qs = qs.filter(origin_country=country)
    if brand_id:
        qs = qs.filter(fabric_brand_id=_optional_int(brand_id) or 0)
    if color_id:
        qs = qs.filter(fabric_color_id=_optional_int(color_id) or 0)
    if type_id:
        qs = qs.filter(fabric_type_id=_optional_int(type_id) or 0)
    if search:
        company_codes = _codes_for_label_search(
            WorkshopRecipe.FABRIC_COMPANY_CHOICES, FABRIC_COMPANY_CATEGORY, search
        )
        category_codes = _codes_for_label_search(
            WorkshopRecipe.FABRIC_CATEGORY_CHOICES, FABRIC_ITEM_CATEGORY, search
        )
        query = (
            Q(name__icontains=search)
            | Q(color_name__icontains=search)
            | Q(item_code__icontains=search)
            | Q(brand__icontains=search)
            | Q(origin_country__icontains=search)
            | Q(company_code__icontains=search)
            | Q(fabric_category__icontains=search)
            | Q(fabric_brand__name__icontains=search)
            | Q(fabric_color__name__icontains=search)
            | Q(fabric_type__name__icontains=search)
            | Q(fabric_country__name__icontains=search)
        )
        if company_codes:
            query |= Q(company_code__in=list(company_codes))
        if category_codes:
            query |= Q(fabric_category__in=list(category_codes))
        qs = qs.filter(query)
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
        try:
            spoilage = Decimal(str(raw.get("normal_spoilage_rate") or 0)) if isinstance(raw, dict) else Decimal(0)
        except (InvalidOperation, TypeError):
            raise ValueError("نرخ ضایعات عادی نامعتبر است.")
        if spoilage < 0 or spoilage > 100:
            raise ValueError("نرخ ضایعات عادی باید بین ۰ و ۱۰۰ باشد.")
        link, _ = WorkshopRecipeMaterial.objects.update_or_create(
            recipe=recipe,
            material=material,
            defaults={"quantity": qty, "unit": unit, "sort_order": index, "normal_spoilage_rate": spoilage},
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
        raise ValueError(
            "نام کالیته را وارد کنید." if kind == WorkshopRecipe.KIND_FABRIC else "نام دستور را وارد کنید."
        )
    recipe = WorkshopRecipe(
        kind=kind,
        name=name,
        color_name=_text(data.get("color_name")),
        note=_text(data.get("note")),
        is_active=bool(data.get("is_active", True)),
    )
    _apply_paint_item(recipe, data, creating=True)
    _apply_fabric_item(recipe, data, creating=True)
    _save_recipe(recipe)
    _sync_recipe_materials(recipe, data.get("materials") or [])
    return recipe


@transaction.atomic
def update_recipe(recipe, data):
    if "name" in data:
        name = _text(data.get("name"))
        if not name:
            label = "نام کالیته" if recipe.kind == WorkshopRecipe.KIND_FABRIC else "نام دستور"
            raise ValueError(f"{label} را وارد کنید.")
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
    _apply_paint_item(recipe, data, creating=False)
    _apply_fabric_item(recipe, data, creating=False)
    _save_recipe(recipe)
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
