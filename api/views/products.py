"""API کاتالوگ محصولات — دسته‌بندی، محصول و رنگ‌بندی."""

from decimal import Decimal, InvalidOperation

from django.db.models import Q

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import (
    MANAGE_FACTORY_PRODUCTS,
    MANAGE_MATERIALS,
    MANAGE_PRODUCTS,
    VIEW_FACTORY_PRODUCTS,
    VIEW_MATERIALS,
    VIEW_PRODUCTS,
    has_permission,
)
from backend.models import Product, ProductCategory, ProductVariant
from logic.audit import log_action
from logic.analytics import best_selling_products
from logic.products import (
    category_to_dict,
    create_category,
    create_product,
    filter_products,
    product_to_dict,
    update_category,
    update_product,
)
from logic.stock_locations import parse_location, transfer_variant_stock


def _can_view_sales(user):
    return has_permission(user, VIEW_PRODUCTS)


def _can_view_factory(user):
    return has_permission(user, VIEW_FACTORY_PRODUCTS)


def _can_view(user):
    return _can_view_sales(user) or _can_view_factory(user)


def _can_manage_sales(user):
    return has_permission(user, MANAGE_PRODUCTS)


def _can_manage_factory(user):
    return has_permission(user, MANAGE_FACTORY_PRODUCTS)


def _can_manage(user):
    return _can_manage_sales(user) or _can_manage_factory(user)


def _product_audience(user):
    if _can_view_sales(user) and has_permission(user, VIEW_MATERIALS):
        return "full"
    if _can_view_sales(user):
        return "sales"
    if _can_view_factory(user):
        return "factory"
    return "sales"


def _product_write_flags(user):
    allow_sales_price = _can_manage_sales(user)
    allow_materials = _can_manage_factory(user) or has_permission(user, MANAGE_MATERIALS)
    return allow_sales_price, allow_materials


def _serialize_product(user, product):
    return product_to_dict(product, audience=_product_audience(user))


@api_view("GET", "POST")
def category_list(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)

    if request.method == "GET":
        qs = ProductCategory.objects.filter(is_deleted=False).order_by("sort_order", "name")
        active = request.GET.get("active")
        if active == "1":
            qs = qs.filter(is_active=True)
        return success({"results": [category_to_dict(c) for c in qs]})

    if not _can_manage(request.user):
        return fail("Permission denied", status=403)

    try:
        category = create_category(parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(request.user, "create", f"دسته محصول: {category.name}", entity_type="ProductCategory", entity_id=category.id)
    return success(category_to_dict(category), status=201)


@api_view("GET", "PUT", "DELETE")
def category_detail(request, pk):
    try:
        category = ProductCategory.objects.get(pk=pk, is_deleted=False)
    except ProductCategory.DoesNotExist:
        return fail("Category not found", status=404)

    if not _can_view(request.user):
        return fail("Permission denied", status=403)

    if request.method == "GET":
        return success(category_to_dict(category))

    if not _can_manage(request.user):
        return fail("Permission denied", status=403)

    if request.method == "DELETE":
        if category.products.filter(is_deleted=False).exists():
            return fail("این دسته محصول دارد و قابل حذف نیست. ابتدا محصولات را جابجا یا حذف کنید.", status=400)
        category.soft_delete()
        log_action(request.user, "delete", f"حذف دسته: {category.name}", entity_type="ProductCategory", entity_id=category.id)
        return success({"deleted": True})

    try:
        category = update_category(category, parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(request.user, "update", f"ویرایش دسته: {category.name}", entity_type="ProductCategory", entity_id=category.id)
    return success(category_to_dict(category))


@api_view("GET", "POST")
def product_list(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)

    if request.method == "GET":
        search = (request.GET.get("search") or "").strip()
        category_id = request.GET.get("category_id")
        active_only = request.GET.get("include_inactive") != "1" or not _can_manage(request.user)
        if request.GET.get("include_inactive") == "1" and _can_manage(request.user):
            qs = Product.objects.filter(is_deleted=False).select_related("category").prefetch_related(
                "variants", "product_materials__material"
            )
            if search:
                q = Q(name__icontains=search) | Q(sku__icontains=search) | Q(brand__icontains=search)
                qs = qs.filter(q).distinct()
            if category_id:
                qs = qs.filter(category_id=category_id)
        else:
            qs = filter_products(Product.objects.all(), search=search, category_id=category_id, active_only=active_only)
        from logic.pagination import paginate

        is_active = (request.GET.get("is_active") or "").strip()
        if is_active == "1":
            qs = qs.filter(is_active=True)
        elif is_active == "0":
            qs = qs.filter(is_active=False)
        page, meta = paginate(qs, request.GET)
        audience = _product_audience(request.user)
        return success({"results": [product_to_dict(p, audience=audience) for p in page], **meta})

    if not _can_manage(request.user):
        return fail("Permission denied", status=403)

    allow_sales_price, allow_materials = _product_write_flags(request.user)
    try:
        product = create_product(
            parse_json(request),
            allow_sales_price=allow_sales_price,
            allow_materials=allow_materials,
        )
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(request.user, "create", f"محصول: {product.name}", entity_type="Product", entity_id=product.id)
    return success(_serialize_product(request.user, product), status=201)


@api_view("GET", "PUT", "DELETE")
def product_detail(request, pk):
    try:
        product = Product.objects.select_related("category").prefetch_related(
            "variants", "product_materials__material"
        ).get(pk=pk, is_deleted=False)
    except Product.DoesNotExist:
        return fail("Product not found", status=404)

    if not _can_view(request.user):
        return fail("Permission denied", status=403)

    if request.method == "GET":
        return success(_serialize_product(request.user, product))

    if not _can_manage(request.user):
        return fail("Permission denied", status=403)

    if request.method == "DELETE":
        if not _can_manage_sales(request.user):
            return fail("Permission denied", status=403)
        product.soft_delete()
        log_action(request.user, "delete", f"حذف محصول: {product.name}", entity_type="Product", entity_id=product.id)
        return success({"deleted": True})

    allow_sales_price, allow_materials = _product_write_flags(request.user)
    try:
        product = update_product(
            product,
            parse_json(request),
            allow_sales_price=allow_sales_price,
            allow_materials=allow_materials,
        )
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(request.user, "update", f"ویرایش محصول: {product.name}", entity_type="Product", entity_id=product.id)
    return success(_serialize_product(request.user, product))


# سازگاری با endpoint قبلی — POST سریع از فروش
@api_view("POST")
def product_quick_create(request):
    if not _can_manage_sales(request.user) and not _can_view_sales(request.user):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return fail("name is required", status=400)
    try:
        price = Decimal(str(data.get("default_price") or 0))
    except (InvalidOperation, TypeError):
        return fail("Invalid price", status=400)

    product, created = Product.objects.get_or_create(
        name=name,
        defaults={"default_price": price, "is_active": True},
    )
    if not created and price:
        product.default_price = price
        product.is_active = True
        product.save()
    log_action(request.user, "create", f"محصول: {name}", entity_type="Product", entity_id=product.id)
    return success(_serialize_product(request.user, product), status=201 if created else 200)


@api_view("GET")
def product_top_selling(request):
    if not _can_view_sales(request.user):
        return fail("Permission denied", status=403)
    try:
        limit = min(max(int(request.GET.get("limit") or 20), 1), 50)
    except (TypeError, ValueError):
        limit = 20
    results = best_selling_products(limit=limit)
    return success({"results": results, "count": len(results)})


@api_view("POST")
def product_stock_transfer(request):
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    from logic.inventory_settings import assert_manual_stock_unlocked

    try:
        assert_manual_stock_unlocked()
    except ValueError as exc:
        return fail(str(exc), status=400)
    data = parse_json(request)
    variant_id = data.get("variant_id")
    try:
        variant = ProductVariant.objects.select_related("product").get(pk=variant_id, is_active=True)
    except ProductVariant.DoesNotExist:
        return fail("رنگ محصول یافت نشد.", status=404)
    try:
        from django.db import transaction

        source = parse_location(data.get("source") or {}, required=True)
        destination = parse_location(data.get("destination") or {}, required=True)
        with transaction.atomic():
            transfer_variant_stock(
                variant,
                source,
                destination,
                data.get("quantity"),
                recorded_by=request.user,
                product_id=variant.product_id,
            )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(product_to_dict(variant.product, audience=_product_audience(request.user)))
