"""decoratorهای احراز هویت و کنترل نقش/مجوز برای viewهای JSON."""

from functools import wraps

from django.views.decorators.csrf import csrf_exempt

from api.helpers import fail
from auth.permissions import has_permission
from auth.roles import get_user_role, has_role, is_staff_user


def require_authenticated(view):
    """کاربر باید login باشد؛ در غیر این صورت 401."""

    @wraps(view)
    @csrf_exempt
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return fail("Authentication required", status=401)
        return view(request, *args, **kwargs)

    return wrapper


def require_role(allowed_roles):
    """فقط نقش‌های مشخص‌شده (مثلاً require_role(['admin', 'sales_manager']))."""

    def decorator(view):
        @wraps(view)
        @csrf_exempt
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return fail("Authentication required", status=401)
            if get_user_role(request.user) not in allowed_roles:
                return fail("Permission denied", status=403)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def require_permission(permission):
    """بررسی مجوز ریز بر اساس ماتریس auth.permissions."""

    def decorator(view):
        @wraps(view)
        @csrf_exempt
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return fail("Authentication required", status=401)
            if get_user_role(request.user) == "pending":
                return fail("Permission denied", status=403)
            if not has_permission(request.user, permission):
                return fail("Permission denied", status=403)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def check_staff_access(user):
    """بررسی دسترسی پایه staff (غیر از pending)."""
    if not user.is_authenticated:
        return fail("Authentication required", status=401)
    if not is_staff_user(user):
        return fail("Permission denied", status=403)
    return None


def check_role_access(user, allowed_roles):
    """بررسی دسترسی بر اساس لیست نقش."""
    denied = check_staff_access(user) if allowed_roles is None else None
    if denied:
        return denied
    if not user.is_authenticated:
        return fail("Authentication required", status=401)
    if allowed_roles is not None and allowed_roles and not has_role(user, *allowed_roles):
        return fail("Permission denied", status=403)
    if allowed_roles is not None and not allowed_roles:
        return None
    if allowed_roles is None and not is_staff_user(user):
        return fail("Permission denied", status=403)
    return None
