"""منطق کاتالوگ محصولات."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from backend.models import Product, ProductCategory, ProductVariant


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


def variant_to_dict(v):
    return {
        "id": v.id,
        "color_name": v.color_name,
        "color_hex": v.color_hex,
        "sku": v.sku,
        "price": int(v.price),
        "stock": v.stock,
        "is_active": v.is_active,
        "sort_order": v.sort_order,
    }


def product_to_dict(p, include_variants=True):
    variants = []
    if include_variants:
        variants = [variant_to_dict(v) for v in p.variants.filter(is_active=True).order_by("sort_order", "id")]
    return {
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "brand": p.brand,
        "description": p.description,
        "unit": p.unit,
        "attributes": p.attributes or {},
        "default_price": int(p.default_price),
        "display_price": int(p.display_price),
        "is_active": p.is_active,
        "category_id": p.category_id,
        "category": category_to_dict(p.category) if p.category_id else None,
        "variants": variants,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if getattr(p, "updated_at", None) else None,
    }


def _parse_variants(raw_variants):
    if not raw_variants:
        return []
    parsed = []
    for idx, item in enumerate(raw_variants):
        color_name = (item.get("color_name") or "").strip()
        if not color_name:
            continue
        try:
            price = Decimal(str(item.get("price") or 0))
        except (InvalidOperation, TypeError):
            price = Decimal(0)
        stock = item.get("stock")
        if stock is not None and stock != "":
            stock = int(stock)
        else:
            stock = None
        parsed.append(
            {
                "color_name": color_name,
                "color_hex": (item.get("color_hex") or "#cccccc").strip()[:7],
                "sku": (item.get("sku") or "").strip(),
                "price": price,
                "stock": stock,
                "is_active": bool(item.get("is_active", True)),
                "sort_order": int(item.get("sort_order") if item.get("sort_order") is not None else idx),
            }
        )
    return parsed


def _sync_variants(product, variants_data):
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
        variant.price = item["price"]
        variant.stock = item.get("stock")
        variant.is_active = item.get("is_active", True)
        variant.sort_order = item.get("sort_order", 0)
        variant.save()
        keep_ids.append(variant.id)
    product.variants.exclude(pk__in=keep_ids).delete()


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
def create_product(data):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("نام محصول الزامی است.")
    try:
        default_price = Decimal(str(data.get("default_price") or 0))
    except (InvalidOperation, TypeError):
        raise ValueError("قیمت نامعتبر است.")

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
        description=(data.get("description") or "").strip(),
        unit=(data.get("unit") or "عدد").strip() or "عدد",
        attributes=attrs or {},
        default_price=default_price,
        is_active=bool(data.get("is_active", True)),
        category=category,
    )

    variants_data = _parse_variants(data.get("variants"))
    if variants_data:
        _sync_variants(product, variants_data)
    elif default_price > 0:
        ProductVariant.objects.create(
            product=product,
            color_name="پیش‌فرض",
            color_hex="#94a3b8",
            price=default_price,
            sort_order=0,
        )
    return product


@transaction.atomic
def update_product(product, data):
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("نام محصول الزامی است.")
        product.name = name
    if "sku" in data:
        product.sku = (data.get("sku") or "").strip()
    if "brand" in data:
        product.brand = (data.get("brand") or "").strip()
    if "description" in data:
        product.description = (data.get("description") or "").strip()
    if "unit" in data:
        product.unit = (data.get("unit") or "عدد").strip() or "عدد"
    if "attributes" in data:
        attrs = data.get("attributes")
        if attrs is not None and not isinstance(attrs, dict):
            raise ValueError("ویژگی‌های سفارشی باید شیء JSON باشد.")
        product.attributes = attrs or {}
    if "default_price" in data:
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

    return product


def filter_products(queryset, *, search="", category_id=None, active_only=True):
    if active_only:
        queryset = queryset.filter(is_active=True, is_deleted=False)
    if category_id:
        queryset = queryset.filter(category_id=category_id)
    if search:
        q = Q(name__icontains=search) | Q(sku__icontains=search) | Q(brand__icontains=search)
        q |= Q(variants__color_name__icontains=search)
        queryset = queryset.filter(q).distinct()
    return queryset.select_related("category").prefetch_related("variants")


def resolve_line_item_from_catalog(item):
    """نگاشت ردیف فروش از کاتالوگ — variant_id یا product_id."""
    product_id = item.get("product_id")
    variant_id = item.get("variant_id")
    product = None
    variant = None
    name = (item.get("product_name") or "").strip()
    color_name = (item.get("color_name") or "").strip()
    color_hex = (item.get("color_hex") or "").strip()[:7]
    price = Decimal(str(item.get("unit_price") or 0))

    if variant_id:
        variant = ProductVariant.objects.select_related("product").filter(pk=variant_id, is_active=True).first()
        if variant:
            product = variant.product
            name = name or product.name
            color_name = color_name or variant.color_name
            color_hex = color_hex or variant.color_hex
            if not item.get("unit_price"):
                price = variant.price
    elif product_id:
        product = Product.objects.filter(pk=product_id, is_active=True, is_deleted=False).first()
        if product:
            name = name or product.name
            if not item.get("unit_price"):
                first_variant = product.variants.filter(is_active=True).order_by("sort_order", "id").first()
                price = first_variant.price if first_variant else product.default_price

    if not name:
        return None

    return {
        "product": product,
        "variant": variant,
        "product_name": name,
        "color_name": color_name,
        "color_hex": color_hex,
        "unit_price": price,
        "quantity": int(item.get("quantity") or 1),
    }
