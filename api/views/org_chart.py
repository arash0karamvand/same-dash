"""چارت سازمانی پرسنل."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import MANAGE_ORG_RANKS, VIEW_ORG_CHART, has_permission
from logic.org_chart import build_org_chart, reassign_manager


@api_view("GET")
def org_chart(request):
    if not has_permission(request.user, VIEW_ORG_CHART):
        return fail("Permission denied", status=403)
    return success(build_org_chart(viewer=request.user))


@api_view("POST")
def org_chart_reassign(request):
    if not has_permission(request.user, MANAGE_ORG_RANKS):
        return fail("Permission denied", status=403)
    data = parse_json(request)
    try:
        reassign_manager(data.get("user_id"), data.get("manager_id"))
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(build_org_chart(viewer=request.user))
