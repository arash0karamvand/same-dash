"""مشاهده لاگ فعالیت‌ها — فقط مدیر سیستم."""

from api.helpers import api_view, fail, success
from auth.executives import can_view_executive_logs
from auth.permissions import VIEW_AUDIT_LOGS, has_permission
from logic.audit import list_audit_logs


@api_view("GET")
def audit_log_list(request):
    if not has_permission(request.user, VIEW_AUDIT_LOGS):
        return fail("Permission denied", status=403)
    return success(
        list_audit_logs(
            request.GET,
            include_executive=can_view_executive_logs(request.user),
        )
    )
