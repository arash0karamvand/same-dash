"""ابزارهای مشترک لایه API (بدون DRF).

قرارداد پاسخ:
    موفق:  {"ok": true,  "data": ...}
    خطا:   {"ok": false, "error": "..."}
"""

import json
import logging
from functools import wraps

from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from auth.permissions import has_permission
from auth.roles import get_user_role, is_staff_user

logger = logging.getLogger(__name__)


def success(data=None, status=200):
    return JsonResponse({"ok": True, "data": data}, status=status)


def fail(error, status=400):
    return JsonResponse({"ok": False, "error": error}, status=status)


def parse_json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}


def api_view(*methods, auth=True, allow_roles=None, permission=None):
    """decorator: csrf_exempt + متد + login + نقش/مجوز."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return fail("Method not allowed", status=405)
            if auth:
                if not request.user.is_authenticated:
                    return fail("Authentication required", status=401)
                if allow_roles is not None and not allow_roles:
                    pass
                elif permission is not None:
                    if not has_permission(request.user, permission):
                        return fail("Permission denied", status=403)
                elif allow_roles is not None:
                    if get_user_role(request.user) not in allow_roles:
                        return fail("Permission denied", status=403)
                elif not is_staff_user(request.user):
                    return fail("Permission denied", status=403)
            try:
                return view(request, *args, **kwargs)
            except (OperationalError, ProgrammingError) as exc:
                logger.exception("Database error in %s", view.__name__)
                detail = f" ({exc})" if settings.DEBUG else ""
                return fail(
                    "خطا در اتصال به پایگاه داده. دیتابیس را بسازید و migrate را اجرا کنید."
                    + detail,
                    status=500,
                )
            except Exception as exc:
                logger.exception("Unhandled API error in %s", view.__name__)
                if settings.DEBUG:
                    return fail(f"{type(exc).__name__}: {exc}", status=500)
                return fail("خطای داخلی سرور.", status=500)

        return csrf_exempt(wrapper)

    return decorator
