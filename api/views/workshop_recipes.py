"""API کاتالوگ دستورهای دست‌کار."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import (
    MANAGE_FACTORY_PRODUCTS,
    MANAGE_MATERIALS,
    VIEW_FACTORY_PRODUCTS,
    VIEW_MATERIALS,
    has_permission,
)
from backend.models import FabricCatalogNode, WorkshopRecipe
from logic.audit import log_action
from logic.pagination import paginate
from logic import workshop_recipes as L


def _can_view(user):
    return (
        has_permission(user, VIEW_FACTORY_PRODUCTS)
        or has_permission(user, VIEW_MATERIALS)
        or has_permission(user, MANAGE_FACTORY_PRODUCTS)
        or has_permission(user, MANAGE_MATERIALS)
    )


def _can_manage(user):
    return has_permission(user, MANAGE_FACTORY_PRODUCTS) or has_permission(user, MANAGE_MATERIALS)


@api_view("GET", "POST")
def paint_category_list(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    if request.method == "GET":
        return success({"results": L.list_paint_categories()})
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    try:
        option = L.create_paint_category((parse_json(request).get("label")))
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "create",
        f"دسته‌بندی رنگ: {option.label}",
        entity_type="LookupOption",
        entity_id=option.id,
    )
    return success({"id": option.id, "code": option.code, "label": option.label}, status=201)


def _option_collection(request, *, list_fn, create_fn, audit_label):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    if request.method == "GET":
        return success({"results": list_fn()})
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    try:
        option = create_fn(parse_json(request).get("label"))
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "create",
        f"{audit_label}: {option.label}",
        entity_type="LookupOption",
        entity_id=option.id,
    )
    return success({"id": option.id, "code": option.code, "label": option.label}, status=201)


@api_view("GET", "POST")
def fabric_category_list(request):
    return _option_collection(
        request,
        list_fn=L.list_fabric_categories,
        create_fn=L.create_fabric_category,
        audit_label="دسته‌بندی پارچه",
    )


@api_view("GET", "POST")
def fabric_company_list(request):
    return _option_collection(
        request,
        list_fn=L.list_fabric_companies,
        create_fn=L.create_fabric_company,
        audit_label="شرکت پارچه",
    )


@api_view("GET", "POST")
def fabric_catalog_list(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    if request.method == "GET":
        return success(L.list_fabric_catalog())
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    try:
        node = L.create_catalog_node(parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "create",
        f"گره کاتالوگ پارچه: {node.name}",
        entity_type="FabricCatalogNode",
        entity_id=node.id,
    )
    return success({"id": node.id, "kind": node.kind, "name": node.name, "parent_id": node.parent_id}, status=201)


@api_view("DELETE")
def fabric_catalog_detail(request, pk):
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    node = FabricCatalogNode.objects.filter(pk=pk).first()
    if not node:
        return fail("مورد کاتالوگ یافت نشد.", status=404)
    try:
        L.delete_catalog_node(node)
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "delete",
        f"گره کاتالوگ پارچه: {node.name}",
        entity_type="FabricCatalogNode",
        entity_id=pk,
    )
    return success({"id": pk})


@api_view("GET", "POST")
def recipe_list(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    if request.method == "GET":
        kind = (request.GET.get("kind") or "").strip()
        search = (request.GET.get("search") or "").strip()
        company = (request.GET.get("company") or "").strip()
        category = (request.GET.get("category") or "").strip()
        country = (request.GET.get("country") or "").strip()
        brand_id = (request.GET.get("brand_id") or "").strip()
        color_id = (request.GET.get("color_id") or "").strip()
        type_id = (request.GET.get("type_id") or "").strip()
        active_only = request.GET.get("include_inactive") != "1"
        qs = L.filter_recipes(
            WorkshopRecipe.objects.select_related(
                "fabric_country", "fabric_brand", "fabric_color", "fabric_type"
            ),
            kind=kind,
            search=search,
            active_only=active_only,
            company=company,
            category=category,
            country=country,
            brand_id=brand_id,
            color_id=color_id,
            type_id=type_id,
        )
        page, meta = paginate(qs, request.GET, default_limit=200)
        return success({"results": [L.recipe_to_dict(r) for r in page], **meta})
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    try:
        recipe = L.create_recipe(parse_json(request))
        log_action(request.user, "create", f"دستور دست‌کار: {recipe.name}", entity_type="WorkshopRecipe", entity_id=recipe.id)
        return success(L.recipe_to_dict(recipe), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def recipe_detail(request, pk):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    recipe = WorkshopRecipe.objects.filter(pk=pk, is_deleted=False).first()
    if not recipe:
        return fail("دستور دست‌کار یافت نشد.", status=404)
    if request.method == "GET":
        return success(L.recipe_to_dict(recipe))
    if not _can_manage(request.user):
        return fail("Permission denied", status=403)
    if request.method == "DELETE":
        L.delete_recipe(recipe)
        log_action(request.user, "delete", f"دستور دست‌کار: {recipe.name}", entity_type="WorkshopRecipe", entity_id=pk)
        return success({"id": pk})
    try:
        L.update_recipe(recipe, parse_json(request))
        log_action(request.user, "update", f"دستور دست‌کار: {recipe.name}", entity_type="WorkshopRecipe", entity_id=recipe.id)
        return success(L.recipe_to_dict(recipe))
    except ValueError as exc:
        return fail(str(exc), status=400)
