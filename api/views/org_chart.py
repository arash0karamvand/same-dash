"""چارت سازمانی پرسنل."""

from api.helpers import api_view, fail, success
from auth.permissions import VIEW_ORG_CHART, has_permission
from logic.org_chart import build_org_chart


@api_view("GET")
def org_chart(request):
    if not has_permission(request.user, VIEW_ORG_CHART):
        return fail("Permission denied", status=403)
    return success(build_org_chart())
