"""مدیریت نقش‌ها و مجوزها — فقط مدیر سیستم."""

from api.helpers import api_view, fail, parse_json, success
from auth import roles
from auth.permissions import is_system_admin
from backend.models import OrgRank, RoleDefinition
from logic.audit import log_action
from logic.role_definitions import (
    build_permission_matrix_payload,
    create_org_rank,
    create_role_definition,
    deactivate_org_rank,
    delete_role_definition,
    list_active_org_ranks,
    list_role_definitions,
    org_rank_to_dict,
    role_definition_to_dict,
    seed_builtin_roles,
    update_org_rank,
    update_role_definition,
)


def _require_system_admin(user):
    if not is_system_admin(user):
        return fail("فقط مدیر سیستم مجاز است.", status=403)
    return None


@api_view("GET")
def permission_matrix(request):
    denied = _require_system_admin(request.user)
    if denied:
        return denied
    return success(build_permission_matrix_payload())


@api_view("GET", "POST")
def role_definition_list(request):
    denied = _require_system_admin(request.user)
    if denied:
        return denied
    seed_builtin_roles()

    if request.method == "GET":
        return success({"results": [role_definition_to_dict(r) for r in list_role_definitions()]})

    try:
        rd = create_role_definition(parse_json(request))
    except PermissionError as exc:
        return fail(str(exc), status=403)
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(request.user, "create", f"نقش جدید: {rd.label}", entity_type="RoleDefinition", entity_id=rd.id)
    return success(role_definition_to_dict(rd), status=201)


@api_view("GET", "PUT", "DELETE")
def role_definition_detail(request, slug):
    denied = _require_system_admin(request.user)
    if denied:
        return denied
    try:
        rd = RoleDefinition.objects.select_related("parent").get(slug=slug)
    except RoleDefinition.DoesNotExist:
        return fail("نقش یافت نشد.", status=404)

    if request.method == "GET":
        return success(role_definition_to_dict(rd))

    if request.method == "DELETE":
        if rd.slug == roles.ADMIN:
            return fail("نقش مدیر سیستم قابل حذف نیست.", status=400)
        moved = delete_role_definition(rd)
        log_action(
            request.user,
            "delete",
            f"حذف نقش {slug}" + (f" — {moved} کاربر به pending" if moved else ""),
            entity_type="RoleDefinition",
        )
        return success({"deleted": True, "users_moved_to_pending": moved})

    try:
        update_role_definition(rd, parse_json(request))
    except PermissionError as exc:
        return fail(str(exc), status=400)
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(request.user, "update", f"ویرایش نقش {rd.label}", entity_type="RoleDefinition", entity_id=rd.id)
    return success(role_definition_to_dict(rd))


@api_view("GET", "POST")
def org_rank_list(request):
    denied = _require_system_admin(request.user)
    if denied:
        return denied

    if request.method == "GET":
        return success({"results": [org_rank_to_dict(r) for r in list_active_org_ranks()]})

    try:
        rank = create_org_rank(parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(org_rank_to_dict(rank), status=201)


@api_view("PUT", "DELETE")
def org_rank_detail(request, pk):
    denied = _require_system_admin(request.user)
    if denied:
        return denied
    try:
        rank = OrgRank.objects.get(pk=pk)
    except OrgRank.DoesNotExist:
        return fail("رتبه یافت نشد.", status=404)

    if request.method == "DELETE":
        deactivate_org_rank(rank)
        return success({"deleted": True})

    update_org_rank(rank, parse_json(request))
    return success(org_rank_to_dict(rank))
