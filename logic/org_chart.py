"""منطق چارت سازمانی پرسنل."""

from django.contrib.auth import get_user_model

from auth import roles
from auth.branches import BRANCH_LABELS, DEFAULT_BRANCH
from auth.permissions import MANAGE_ORG_RANKS, has_permission
from backend.models import RoleDefinition, StaffProfile
from logic.departments import department_label, get_user_primary_department

User = get_user_model()

REL_SELF = "self"
REL_DESCENDANT = "descendant"
REL_ANCESTOR = "ancestor"
REL_OTHER = "other"
_CHAIN_LIMIT = 50


def staff_node(user):
    role = roles.get_user_role(user)
    profile = getattr(user, "staff_profile", None)
    try:
        rd = RoleDefinition.objects.get(slug=role)
        role_label = rd.label
        role_color = rd.color
    except RoleDefinition.DoesNotExist:
        role_label = roles.ROLE_LABELS.get(role, role)
        role_color = "#6366f1"
    department = get_user_primary_department(user)
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.get_full_name() or user.username,
        "role": role,
        "role_label": role_label,
        "role_color": role_color,
        "department": department,
        "department_label": department_label(department),
        "branch": profile.branch_id if profile else None,
        "branch_label": BRANCH_LABELS.get(profile.branch_id, "—") if profile else "—",
        "job_title": profile.job_title if profile else "",
        "org_rank": profile.org_rank.name if profile and profile.org_rank_id else None,
        "org_rank_color": profile.org_rank.color if profile and profile.org_rank_id else None,
        "manager_id": profile.manager_id if profile else None,
        "is_active": user.is_active,
        "children": [],
    }


def build_tree(nodes_by_id, root_manager_id=None):
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


def _active_user(user_id):
    return (
        User.objects.filter(pk=user_id, is_active=True)
        .exclude(groups__name=roles.PENDING)
        .first()
    )


def ensure_profile(user):
    profile, _ = StaffProfile.objects.get_or_create(
        user=user,
        defaults={"branch_id": DEFAULT_BRANCH},
    )
    return profile


def manager_chain_ids(user_id):
    """شناسه مدیران از پایین به بالا، بدون حلقه."""
    seen = []
    visited = {int(user_id)}
    current_id = int(user_id)
    for _ in range(_CHAIN_LIMIT):
        profile = StaffProfile.objects.filter(user_id=current_id).first()
        if not profile or not profile.manager_id:
            break
        mgr_id = int(profile.manager_id)
        if mgr_id in visited:
            break
        seen.append(mgr_id)
        visited.add(mgr_id)
        current_id = mgr_id
    return seen


def relation_to(actor_id, target_id):
    actor_id = int(actor_id)
    target_id = int(target_id)
    if actor_id == target_id:
        return REL_SELF
    if actor_id in manager_chain_ids(target_id):
        return REL_DESCENDANT
    if target_id in manager_chain_ids(actor_id):
        return REL_ANCESTOR
    return REL_OTHER


def reassign_manager(user_id, manager_id):
    user = _active_user(user_id)
    if not user:
        raise ValueError("کاربر یافت نشد.")
    next_manager_id = int(manager_id) if manager_id not in (None, "", 0, "0") else None
    if next_manager_id == user.id:
        raise ValueError("کاربر نمی‌تواند مدیر خودش باشد.")
    if next_manager_id:
        manager = _active_user(next_manager_id)
        if not manager:
            raise ValueError("مدیر یافت نشد.")
        if user.id in manager_chain_ids(manager.id):
            raise ValueError("نمی‌توان کسی را زیرمجموعهٔ زیردست خودش قرار داد.")
    profile = ensure_profile(user)
    profile.manager_id = next_manager_id
    profile.save(update_fields=["manager"])
    return profile


def build_org_chart(viewer=None):
    """ساخت درخت، لیست تخت، گروه‌بندی شعبه و آمار چارت سازمانی."""
    users = (
        User.objects.filter(is_active=True)
        .exclude(groups__name=roles.PENDING)
        .select_related("staff_profile", "staff_profile__org_rank", "staff_profile__manager")
        .prefetch_related("groups")
        .distinct()
    )

    nodes_by_id = {u.id: staff_node(u) for u in users}
    tree = build_tree(nodes_by_id)

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

    return {
        "tree": tree,
        "flat": list(nodes_by_id.values()),
        "by_branch": list(by_branch.values()),
        "role_hierarchy": role_hierarchy,
        "stats": stats,
        "me_id": viewer.id if viewer is not None else None,
        "can_edit": bool(viewer is not None and has_permission(viewer, MANAGE_ORG_RANKS)),
    }
