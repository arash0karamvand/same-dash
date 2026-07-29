"""endpoint داشبورد — /api/dashboard/summary/."""

from api.helpers import api_view, success
from auth.permissions import VIEW_DASHBOARD
from logic.dashboard import build_dashboard_summary


@api_view("GET", permission=VIEW_DASHBOARD)
def dashboard_summary(request):
    return success(build_dashboard_summary(request.user))
