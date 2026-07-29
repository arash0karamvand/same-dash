"""API فیلتر رکوردها — مدیران / ایجنت."""

from api.helpers import api_view, fail, success
from auth.executives import can_view_executive_logs
from auth.org_roles import is_executive_user
from auth.permissions import (
    APPROVE_SALE_ACCOUNTING,
    VIEW_ACCOUNTING,
    VIEW_AUDIT_LOGS,
    VIEW_CUSTOMERS,
    VIEW_DASHBOARD,
    VIEW_INSTALLMENTS,
    VIEW_SALES,
    has_permission,
)
from logic.record_filter import filter_catalog, query_filtered_records


def _can_use_record_filter(user):
    if is_executive_user(user):
        return True
    office_perms = (
        VIEW_ACCOUNTING,
        APPROVE_SALE_ACCOUNTING,
        VIEW_SALES,
        VIEW_CUSTOMERS,
        VIEW_INSTALLMENTS,
    )
    return (
        has_permission(user, VIEW_DASHBOARD)
        or has_permission(user, VIEW_AUDIT_LOGS)
        or any(has_permission(user, p) for p in office_perms)
    )


@api_view("GET")
def record_filter_catalog(request):
    if not _can_use_record_filter(request.user):
        return fail("Permission denied", status=403)
    scope = (request.GET.get("scope") or "").strip()
    return success(filter_catalog(scope or None))


@api_view("GET")
def record_filter_query(request):
    if not _can_use_record_filter(request.user):
        return fail("Permission denied", status=403)
    try:
        data = query_filtered_records(
            request.GET,
            include_executive_logs=can_view_executive_logs(request.user),
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(data)
