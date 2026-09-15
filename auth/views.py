"""Viewهای احراز هویت — session-based، بدون JWT."""

import logging

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.db.models import Q

from api.helpers import api_view, fail, parse_json, success
from auth import roles
from auth.branches import BRANCH_CHOICES, BRANCH_LABELS, DEFAULT_BRANCH, normalize_branch_code, refresh_branches
from auth.permissions import (
    ALL_PERMISSIONS,
    MANAGE_USERS,
    RESET_BUSINESS_DATA,
    SELF_CHECK_IN,
    get_effective_user_permissions,
    get_user_extra_permissions,
    has_full_access,
    has_permission,
    is_system_admin,
    sanitize_user_extra_permissions,
)
from logic.role_definitions import get_role_permissions
from logic.sellers import ensure_seller_for_user
from backend.models import OrgRank, Seller, StaffProfile, UserAccessProfile
from logic.audit import log_action

User = get_user_model()
logger = logging.getLogger(__name__)


def role_needs_branch(role):
    from backend.models import RoleDefinition

    try:
        return RoleDefinition.objects.get(slug=role).needs_branch
    except RoleDefinition.DoesNotExist:
        return role in roles.LEGACY_ROLES


def user_to_dict(user):
    """نگاشت امن کاربر برای JSON (بدون رمز یا token)."""
    role = roles.get_user_role(user)
    profile = None
    try:
        profile = user.staff_profile
    except StaffProfile.DoesNotExist:
        pass
    branch = profile.branch_id if profile else None
    if not branch:
        seller = Seller.objects.filter(user=user, is_active=True).first()
        branch = seller.branch_id if seller else None
    manager = profile.manager if profile and profile.manager_id else None
    from backend.models import RoleDefinition

    try:
        rd = RoleDefinition.objects.get(slug=role)
        role_label = rd.label
    except RoleDefinition.DoesNotExist:
        role_label = roles.ROLE_LABELS.get(role, "")

    if has_full_access(user):
        permissions = sorted(ALL_PERMISSIONS)
        role_permissions = sorted(ALL_PERMISSIONS)
        extra_permissions = []
    elif role == roles.PENDING:
        extra_permissions = sorted(get_user_extra_permissions(user))
        role_permissions = []
        permissions = extra_permissions
    else:
        role_permissions = sorted(get_role_permissions(role))
        extra_permissions = sorted(get_user_extra_permissions(user))
        permissions = sorted(set(role_permissions) | set(extra_permissions))

    cycle_payload = {
        "is_shop_crm_monitor": False,
        "is_fulfillment_supervisor": False,
        "can_watch_cycle": False,
        "can_manage_warehouse": False,
        "can_manage_pickup": False,
        "enabled_routes": ["factory", "warehouse", "customer_pickup", "merchant"],
    }
    try:
        from logic.order_cycle import cycle_flags_for_user, extra_permissions_from_cycle

        cycle_payload = cycle_flags_for_user(user)
        if not has_full_access(user):
            permissions = sorted(set(permissions) | extra_permissions_from_cycle(user))
    except Exception:
        pass

    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.get_full_name() or user.username,
        "email": user.email or "",
        "role": role,
        "role_label": role_label,
        "permissions": permissions,
        "role_permissions": role_permissions,
        "extra_permissions": extra_permissions,
        "grants_full_access": has_full_access(user),
        "branch": branch,
        "branch_label": BRANCH_LABELS.get(branch, "—"),
        "manager_id": profile.manager_id if profile else None,
        "manager_name": manager.get_full_name() or manager.username if manager else None,
        "job_title": profile.job_title if profile else "",
        "org_rank_id": profile.org_rank_id if profile else None,
        "org_rank_name": profile.org_rank.name if profile and profile.org_rank_id else None,
        "is_staff": user.is_staff,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "cycle": cycle_payload,
    }


def ensure_staff_profile(user, branch=None):
    profile, _ = StaffProfile.objects.get_or_create(
        user=user,
        defaults={"branch_id": branch or DEFAULT_BRANCH},
    )
    if branch and profile.branch_id != branch:
        profile.branch_id = branch
        profile.save(update_fields=["branch"])
    return profile


def ensure_user_access_profile(user):
    profile, _ = UserAccessProfile.objects.get_or_create(user=user)
    return profile


def set_user_extra_permissions(user, permissions):
    if has_full_access(user):
        return []
    profile = ensure_user_access_profile(user)
    cleaned = sanitize_user_extra_permissions(permissions)
    from backend.models import Permission

    permission_rows = [
        Permission.objects.get_or_create(code=code, defaults={"label": code})[0]
        for code in cleaned
    ]
    profile.permission_set.set(permission_rows)
    return cleaned


def apply_user_access(user, role, branch=None):
    """اعمال نقش، پروفایل شعبه و همگام‌سازی فروشنده متصل."""
    roles.assign_role(user, role)
    chosen = _normalize_branch(branch)

    if role_needs_branch(role):
        ensure_staff_profile(user, chosen)
        ensure_seller_for_user(user, branch=chosen)
    elif role == roles.ADMIN or has_permission(user, SELF_CHECK_IN):
        ensure_staff_profile(user, chosen)
        ensure_seller_for_user(user, branch=chosen)
    elif role != roles.ADMIN:
        StaffProfile.objects.filter(user=user).delete()


def _normalize_branch(branch):
    refresh_branches()
    return normalize_branch_code(branch)


def _set_full_name(user, full_name):
    full_name = (full_name or "").strip()
    if not full_name:
        return
    parts = full_name.split(" ", 1)
    user.first_name = parts[0]
    user.last_name = parts[1] if len(parts) > 1 else ""
    user.save(update_fields=["first_name", "last_name"])


def _users_queryset(request):
    qs = User.objects.select_related("staff_profile").prefetch_related("groups").order_by("username")
    search = (request.GET.get("search") or "").strip()
    role_filter = (request.GET.get("role") or "").strip()
    active = request.GET.get("active")

    if search:
        qs = qs.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
        )
    if role_filter:
        qs = qs.filter(groups__name=role_filter)
    if active == "1":
        qs = qs.filter(is_active=True)
    elif active == "0":
        qs = qs.filter(is_active=False)
    return qs.distinct()


@api_view("POST", auth=False)
def login(request):
    data = parse_json(request)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return fail("نام کاربری و رمز عبور الزامی است.", status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return fail("نام کاربری یا رمز عبور اشتباه است.", status=401)
    if not user.is_active:
        return fail("حساب کاربری غیرفعال است.", status=403)

    django_login(request, user)
    try:
        log_action(user, "login", f"ورود {user.get_full_name() or user.username}")
    except Exception:
        logger.exception("Failed to write login audit log")
    return success(user_to_dict(user))


@api_view("POST", allow_roles=[])
def logout(request):
    if request.user.is_authenticated:
        log_action(
            request.user,
            "logout",
            f"خروج {request.user.get_full_name() or request.user.username}",
        )
    django_logout(request)
    return success({"message": "Logged out"})


@api_view("GET", allow_roles=[])
def me(request):
    return success(user_to_dict(request.user))


@api_view("GET", "POST", permission=MANAGE_USERS)
def user_list(request):
    if request.method == "GET":
        from logic.pagination import paginate

        users = _users_queryset(request)
        page, meta = paginate(users, request.GET)
        results = [user_to_dict(u) for u in page]
        all_qs = User.objects.all()
        stats = {
            "total": all_qs.count(),
            "active": all_qs.filter(is_active=True).count(),
            "pending": all_qs.filter(groups__name=roles.PENDING).count(),
        }
        return success({"results": results, "stats": stats, **meta})
    return _create_user(request)


def _create_user(request):
    data = parse_json(request)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return fail("نام کاربری و رمز عبور الزامی است.", status=400)
    if User.objects.filter(username=username).exists():
        return fail("این نام کاربری قبلاً ثبت شده است.", status=400)
    if len(password) < 8:
        return fail("رمز عبور باید حداقل ۸ کاراکتر باشد.", status=400)

    user = User.objects.create_user(
        username=username,
        password=password,
        email=(data.get("email") or "").strip(),
    )
    _set_full_name(user, data.get("full_name"))

    role = data.get("role") or roles.DEFAULT_ROLE
    if role == roles.ADMIN and not is_system_admin(request.user):
        user.delete()
        return fail("فقط مدیر سیستم می‌تواند مدیر سیستم بسازد.", status=403)
    try:
        branch = _normalize_branch(data.get("branch")) if role_needs_branch(role) else None
        apply_user_access(user, role, branch)
    except ValueError as exc:
        user.delete()
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "create",
        f"ساخت کاربر {username} — نقش {roles.ROLE_LABELS.get(role, role)}",
        entity_type="User",
        entity_id=user.id,
    )
    return success({"user": user_to_dict(user)}, status=201)


@api_view("GET", permission=MANAGE_USERS)
def role_list(request):
    from backend.models import RoleDefinition
    from logic.role_definitions import seed_builtin_roles

    seed_builtin_roles()
    qs = RoleDefinition.objects.order_by("sort_order")
    if not is_system_admin(request.user):
        qs = qs.exclude(slug=roles.ADMIN)
    results = [
        {
            "value": r.slug,
            "label": r.label,
            "description": r.description,
            "needs_branch": r.needs_branch,
            "color": r.color,
            "permissions": r.permissions or [],
        }
        for r in qs
    ]
    if not any(item["value"] == roles.PENDING for item in results):
        results.append(
            {
                "value": roles.PENDING,
                "label": roles.ROLE_LABELS[roles.PENDING],
                "description": roles.ROLE_DESCRIPTIONS[roles.PENDING],
                "needs_branch": False,
                "color": "#94a3b8",
                "permissions": [],
            }
        )
    from logic.branches import get_active_branches
    from auth.permissions import permission_groups_for_matrix
    from logic.module_catalog import portal_modules_for_matrix

    refresh_branches()
    return success(
        {
            "results": results,
            "branches": [
                {"value": b["code"], "label": b["label"], "color": b.get("color")}
                for b in get_active_branches()
            ],
            "assignable_portal_modules": portal_modules_for_matrix(assignable_only=True),
            "assignable_permission_groups": permission_groups_for_matrix(assignable_only=True),
        }
    )


@api_view("GET", "PUT", permission=MANAGE_USERS)
def user_detail(request, pk):
    try:
        target = User.objects.select_related("staff_profile").get(pk=pk)
    except User.DoesNotExist:
        return fail("کاربر یافت نشد.", status=404)

    if request.method == "GET":
        return success(user_to_dict(target))

    data = parse_json(request)
    is_self = target == request.user

    if "full_name" in data:
        _set_full_name(target, data.get("full_name"))
    if "email" in data:
        target.email = (data.get("email") or "").strip()
        target.save(update_fields=["email"])

    if "is_active" in data and not is_self:
        target.is_active = bool(data.get("is_active"))
        target.save(update_fields=["is_active"])

    role = data.get("role")
    branch = data.get("branch")
    if role is not None and not is_self:
        if role == roles.ADMIN and not is_system_admin(request.user):
            return fail("فقط مدیر سیستم می‌تواند نقش مدیر سیستم بدهد.", status=403)
        if role_needs_branch(role) and not branch:
            profile = getattr(target, "staff_profile", None)
            branch = profile.branch_id if profile else DEFAULT_BRANCH
        try:
            apply_user_access(
                target,
                role,
                _normalize_branch(branch) if role_needs_branch(role) else None,
            )
        except ValueError as exc:
            return fail(str(exc), status=400)
    elif branch is not None and not is_self:
        current_role = roles.get_user_role(target)
        if role_needs_branch(current_role):
            apply_user_access(target, current_role, _normalize_branch(branch))

    if not is_self and any(k in data for k in ("manager_id", "job_title", "org_rank_id")):
        current_role = roles.get_user_role(target)
        if role_needs_branch(current_role) or current_role == roles.ADMIN:
            profile = ensure_staff_profile(
                target,
                getattr(getattr(target, "staff_profile", None), "branch_id", None) or DEFAULT_BRANCH,
            )
            if "job_title" in data:
                profile.job_title = (data.get("job_title") or "").strip()[:100]
            if "org_rank_id" in data:
                raw = data.get("org_rank_id")
                profile.org_rank = OrgRank.objects.filter(pk=raw, is_active=True).first() if raw else None
            if "manager_id" in data:
                mgr_id = data.get("manager_id")
                if mgr_id and int(mgr_id) == target.id:
                    return fail("کاربر نمی‌تواند مدیر خودش باشد.", status=400)
                profile.manager = User.objects.filter(pk=mgr_id, is_active=True).first() if mgr_id else None
            profile.save()

    if "extra_permissions" in data and not is_self and not has_full_access(target):
        set_user_extra_permissions(target, data.get("extra_permissions"))

    target.refresh_from_db()
    log_action(
        request.user,
        "update",
        f"ویرایش کاربر {target.username}",
        entity_type="User",
        entity_id=target.id,
    )
    return success(user_to_dict(target))


@api_view("POST", permission=MANAGE_USERS)
def user_reset_password(request, pk):
    try:
        target = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return fail("کاربر یافت نشد.", status=404)

    data = parse_json(request)
    new_pass = data.get("new_password") or ""
    if len(new_pass) < 8:
        return fail("رمز عبور باید حداقل ۸ کاراکتر باشد.", status=400)

    target.set_password(new_pass)
    target.save(update_fields=["password"])
    log_action(
        request.user,
        "update",
        f"بازنشانی رمز {target.username}",
        entity_type="User",
        entity_id=target.id,
    )
    return success({"message": "رمز عبور به‌روز شد."})


@api_view("POST", permission=MANAGE_USERS)
def assign_role(request):
    """سازگاری با کلاینت قدیمی — ترجیحاً از user_detail استفاده شود."""
    data = parse_json(request)
    user_id = data.get("user_id")
    role = data.get("role")
    if not user_id or not role:
        return fail("user_id و role الزامی است.", status=400)

    try:
        target = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return fail("کاربر یافت نشد.", status=404)
    if target == request.user:
        return fail("نمی‌توانید نقش خودتان را تغییر دهید.", status=400)
    if role == roles.ADMIN and not is_system_admin(request.user):
        return fail("فقط مدیر سیستم می‌تواند نقش مدیر سیستم بدهد.", status=403)

    branch = _normalize_branch(data.get("branch")) if role_needs_branch(role) else None
    try:
        apply_user_access(target, role, branch)
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "update",
        f"تخصیص نقش {target.username} → {roles.ROLE_LABELS.get(role, role)}",
        entity_type="User",
        entity_id=target.id,
    )
    return success(user_to_dict(target))


@api_view("DELETE", permission=MANAGE_USERS)
def user_deactivate(request, pk):
    try:
        target = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return fail("کاربر یافت نشد.", status=404)
    if target == request.user:
        return fail("نمی‌توانید حساب خودتان را غیرفعال کنید.", status=400)
    if target.is_superuser:
        return fail("غیرفعال‌سازی superuser مجاز نیست.", status=400)

    target.is_active = False
    target.save(update_fields=["is_active"])
    Seller.objects.filter(user=target, is_active=True).update(is_active=False)
    log_action(
        request.user,
        "delete",
        f"غیرفعال‌سازی کاربر {target.username}",
        entity_type="User",
        entity_id=target.id,
    )
    return success({"deactivated": True})


@api_view("POST", permission=RESET_BUSINESS_DATA)
def reset_business_data(request):
    data = parse_json(request)
    confirm = (data.get("confirm") or "").strip()
    if confirm != "پاکسازی":
        return fail('برای تأیید، عبارت «پاکسازی» را وارد کنید.', status=400)

    from logic.reset_data import reset_business_data as do_reset

    counts = do_reset()
    return success(
        {
            "message": "همه داده‌ها به‌صورت دائمی حذف شدند. فقط مدیر سیستم باقی ماند.",
            "counts": counts,
        }
    )


@api_view("POST", allow_roles=[])
def change_password(request):
    data = parse_json(request)
    current = data.get("current_password") or ""
    new_pass = data.get("new_password") or ""
    if not current or not new_pass:
        return fail("رمز فعلی و جدید الزامی است.", status=400)
    if len(new_pass) < 8:
        return fail("رمز جدید باید حداقل ۸ کاراکتر باشد.", status=400)
    if current == new_pass:
        return fail("رمز جدید باید با رمز فعلی متفاوت باشد.", status=400)
    if not request.user.check_password(current):
        return fail("رمز فعلی اشتباه است.", status=403)

    request.user.set_password(new_pass)
    request.user.save(update_fields=["password"])
    django_login(request, request.user)
    log_action(request.user, "update", "تغییر رمز عبور")
    return success({"message": "Password changed successfully"})
