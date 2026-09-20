"""API کاتالوگ دستورهای دست‌کار."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import (
    MANAGE_FACTORY_PRODUCTS,
    MANAGE_MATERIALS,
    VIEW_FACTORY_PRODUCTS,
    VIEW_MATERIALS,
    has_permission,
)
from backend.models import WorkshopRecipe
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
def recipe_list(request):
    if not _can_view(request.user):
        return fail("Permission denied", status=403)
    if request.method == "GET":
        kind = (request.GET.get("kind") or "").strip()
        search = (request.GET.get("search") or "").strip()
        active_only = request.GET.get("include_inactive") != "1"
        qs = L.filter_recipes(WorkshopRecipe.objects.all(), kind=kind, search=search, active_only=active_only)
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
