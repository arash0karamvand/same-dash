"""مدیریت نقش‌ها و مجوزها — فقط مدیر سیستم."""

import re

from django.contrib.auth.models import Group

from api.helpers import api_view, fail, parse_json, success
from auth import roles
from auth.permissions import (
    ALL_PERMISSIONS,
    ASSIGNABLE_PERMISSIONS,
    PERMISSION_LABELS,
    is_system_admin,
    sanitize_role_permissions,
)
from backend.models import OrgRank, RoleDefinition
from logic.audit import log_action
from logic.role_definitions import role_definition_to_dict, seed_builtin_roles, sync_group_for_role


def _require_system_admin(user):
    if not is_system_admin(user):
        return fail("فقط مدیر سیستم مجاز است.", status=403)
    return None


def _slugify(text):
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    return text.strip("_")[:40] or "role"


def org_rank_to_dict(rank):
    return {
        "id": rank.id,
        "name": rank.name,
        "branch": rank.branch,
        "color": rank.color,
        "sort_order": rank.sort_order,
        "is_active": rank.is_active,
    }


@api_view("GET")
def permission_matrix(request):
    denied = _require_system_admin(request.user)
    if denied:
        return denied
    seed_builtin_roles()
    role_defs = [role_definition_to_dict(r) for r in RoleDefinition.objects.order_by("sort_order")]
    return success(
        {
            "permissions": [
                {"code": code, "label": PERMISSION_LABELS.get(code, code)}
                for code in sorted(ALL_PERMISSIONS)
            ],
            "assignable_permissions": [
                {"code": code, "label": PERMISSION_LABELS.get(code, code)}
                for code in sorted(ASSIGNABLE_PERMISSIONS)
            ],
            "roles": role_defs,
        }
    )


@api_view("GET", "POST")
def role_definition_list(request):
    denied = _require_system_admin(request.user)
    if denied:
        return denied
    seed_builtin_roles()

    if request.method == "GET":
        return success(
            {
                "results": [
                    role_definition_to_dict(r)
                    for r in RoleDefinition.objects.select_related("parent").order_by("sort_order")
                ]
            }
        )

    data = parse_json(request)
    label = (data.get("label") or "").strip()
    if not label:
        return fail("عنوان نقش الزامی است.", status=400)
    slug = (data.get("slug") or _slugify(label)).strip()
    if RoleDefinition.objects.filter(slug=slug).exists():
        return fail("این شناسه نقش قبلاً ثبت شده.", status=400)
    if slug == roles.ADMIN:
        return fail("نقش مدیر سیستم از این مسیر قابل ساخت نیست.", status=403)

    perms = sanitize_role_permissions(slug, data.get("permissions") or [])
    invalid = set(perms) - ALL_PERMISSIONS
    if invalid:
        return fail(f"مجوز نامعتبر: {', '.join(sorted(invalid))}", status=400)

    parent = None
    parent_slug = (data.get("parent_slug") or "").strip()
    if parent_slug:
        parent = RoleDefinition.objects.filter(slug=parent_slug).first()

    rd = RoleDefinition.objects.create(
        slug=slug,
        label=label,
        description=(data.get("description") or "").strip(),
        permissions=perms,
        is_builtin=False,
        needs_branch=bool(data.get("needs_branch")),
        color=(data.get("color") or "#6366f1").strip()[:20],
        sort_order=int(data.get("sort_order") or 50),
        parent=parent,
    )
    sync_group_for_role(slug)
    log_action(request.user, "create", f"نقش جدید: {label}", entity_type="RoleDefinition", entity_id=rd.id)
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
        if rd.is_builtin:
            return fail("نقش پیش‌فرض قابل حذف نیست.", status=400)
        if rd.slug == roles.ADMIN:
            return fail("نقش مدیر سیستم قابل حذف نیست.", status=400)
        Group.objects.filter(name=rd.slug).delete()
        rd.delete()
        log_action(request.user, "delete", f"حذف نقش {slug}", entity_type="RoleDefinition")
        return success({"deleted": True})

    data = parse_json(request)
    if slug == roles.ADMIN:
        return fail("مجوزهای نقش مدیر سیستم قابل تغییر نیست.", status=400)

    if "label" in data:
        rd.label = (data.get("label") or rd.label).strip()
    if "description" in data:
        rd.description = (data.get("description") or "").strip()
    if "permissions" in data:
        perms = sanitize_role_permissions(slug, data.get("permissions") or [])
        invalid = set(perms) - ALL_PERMISSIONS
        if invalid:
            return fail(f"مجوز نامعتبر: {', '.join(sorted(invalid))}", status=400)
        rd.permissions = perms
    if "needs_branch" in data:
        rd.needs_branch = bool(data.get("needs_branch"))
    if "color" in data:
        rd.color = (data.get("color") or rd.color).strip()[:20]
    if "sort_order" in data:
        rd.sort_order = int(data.get("sort_order") or rd.sort_order)
    if "parent_slug" in data:
        ps = (data.get("parent_slug") or "").strip()
        rd.parent = RoleDefinition.objects.filter(slug=ps).first() if ps else None
    rd.save()
    sync_group_for_role(slug)
    log_action(request.user, "update", f"ویرایش نقش {rd.label}", entity_type="RoleDefinition", entity_id=rd.id)
    return success(role_definition_to_dict(rd))


@api_view("GET", "POST")
def org_rank_list(request):
    denied = _require_system_admin(request.user)
    if denied:
        return denied

    if request.method == "GET":
        qs = OrgRank.objects.filter(is_active=True).order_by("sort_order", "name")
        return success({"results": [org_rank_to_dict(r) for r in qs]})

    data = parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return fail("نام رتبه الزامی است.", status=400)
    rank = OrgRank.objects.create(
        name=name,
        branch=(data.get("branch") or "").strip(),
        color=(data.get("color") or "#6366f1").strip()[:20],
        sort_order=int(data.get("sort_order") or 0),
    )
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
        rank.is_active = False
        rank.save(update_fields=["is_active"])
        return success({"deleted": True})

    data = parse_json(request)
    if "name" in data:
        rank.name = (data.get("name") or rank.name).strip()
    if "branch" in data:
        rank.branch = (data.get("branch") or "").strip()
    if "color" in data:
        rank.color = (data.get("color") or rank.color).strip()[:20]
    if "sort_order" in data:
        rank.sort_order = int(data.get("sort_order") or rank.sort_order)
    rank.save()
    return success(org_rank_to_dict(rank))
