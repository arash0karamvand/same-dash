"""چارت سازمانی پرسنل."""

from django.contrib.auth import get_user_model

from api.helpers import api_view, fail, success
from auth import roles
from auth.branches import BRANCH_LABELS
from auth.permissions import VIEW_ORG_CHART, has_permission
from backend.models import RoleDefinition, StaffProfile

User = get_user_model()


def _staff_node(user):
    role = roles.get_user_role(user)
    profile = getattr(user, "staff_profile", None)
    try:
        rd = RoleDefinition.objects.get(slug=role)
        role_label = rd.label
        role_color = rd.color
    except RoleDefinition.DoesNotExist:
        role_label = roles.ROLE_LABELS.get(role, role)
        role_color = "#6366f1"
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.get_full_name() or user.username,
        "role": role,
        "role_label": role_label,
        "role_color": role_color,
        "branch": profile.branch if profile else None,
        "branch_label": BRANCH_LABELS.get(profile.branch, "—") if profile else "—",
        "job_title": profile.job_title if profile else "",
        "org_rank": profile.org_rank.name if profile and profile.org_rank_id else None,
        "org_rank_color": profile.org_rank.color if profile and profile.org_rank_id else None,
        "manager_id": profile.manager_id if profile else None,
        "is_active": user.is_active,
        "children": [],
    }


def _build_tree(nodes_by_id, root_manager_id=None):
    roots = []
    for uid, node in nodes_by_id.items():
        mgr = node.get("manager_id")
        if mgr == root_manager_id or (root_manager_id is None and not mgr):
            roots.append(node)
        elif mgr in nodes_by_id:
            nodes_by_id[mgr]["children"].append(node)
        else:
            roots.append(node)
    return roots


@api_view("GET")
def org_chart(request):
    if not has_permission(request.user, VIEW_ORG_CHART):
        return fail("Permission denied", status=403)

    users = (
        User.objects.filter(is_active=True)
        .exclude(groups__name=roles.PENDING)
        .select_related("staff_profile", "staff_profile__org_rank", "staff_profile__manager")
        .prefetch_related("groups")
        .distinct()
    )

    nodes_by_id = {u.id: _staff_node(u) for u in users}
    tree = _build_tree(nodes_by_id)

    role_hierarchy = [
        {
            "slug": rd.slug,
            "label": rd.label,
            "color": rd.color,
            "parent_slug": rd.parent.slug if rd.parent_id else None,
        }
        for rd in RoleDefinition.objects.order_by("sort_order")
    ]

    by_branch = {}
    for node in nodes_by_id.values():
        key = node["branch"] or "other"
        by_branch.setdefault(key, {"branch": key, "label": node["branch_label"], "members": []})
        by_branch[key]["members"].append(node)

    stats = {
        "total_staff": len(nodes_by_id),
        "branches": len(by_branch),
        "managers": sum(1 for n in nodes_by_id.values() if n["children"]),
    }

    return success(
        {
            "tree": tree,
            "flat": list(nodes_by_id.values()),
            "by_branch": list(by_branch.values()),
            "role_hierarchy": role_hierarchy,
            "stats": stats,
        }
    )
