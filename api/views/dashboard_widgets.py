"""API endpoints برای مدیریت ویجت‌های داشبورد."""

from api.helpers import api_view, success, fail, parse_json
from auth.permissions import VIEW_DASHBOARD, can_view_costs, has_permission
from backend.models import DashboardWidget
from logic.dashboard_metrics import calculate_metric

COST_METRICS = {"material_inventory_value", "production_cost_summary", "production_cost_trend"}


def _allowed(user, metric=None):
    if not has_permission(user, VIEW_DASHBOARD):
        return False
    return not (metric in COST_METRICS and not can_view_costs(user))


@api_view("GET", "POST")
def widgets_list(request):
    """
    GET: لیست ویجت‌های کاربر
    POST: ساخت ویجت جدید
    """
    if not _allowed(request.user):
        return fail("Permission denied", status=403)
    if request.method == "GET":
        widgets = list(DashboardWidget.objects.filter(user=request.user).order_by("position"))
        if not can_view_costs(request.user):
            widgets = [
                widget for widget in widgets
                if (widget.config or {}).get("metric") not in COST_METRICS
            ]
        
        results = [
            {
                "id": w.id,
                "widget_type": w.widget_type,
                "title": w.title,
                "config": w.config,
                "position": w.position,
                "size": w.size,
            }
            for w in widgets
        ]
        
        return success(results)
    
    # POST
    data = parse_json(request)
    metric = (data.get("config") or {}).get("metric")
    if not _allowed(request.user, metric):
        return fail("Permission denied", status=403)
    widget = DashboardWidget.objects.create(
        user=request.user,
        widget_type=data["widget_type"],
        title=data["title"],
        config=data.get("config", {}),
        size=data.get("size", "medium"),
        position=data.get("position", 0),
    )
    
    return success({"id": widget.id, "title": widget.title})


@api_view("PUT", "DELETE")
def widget_detail(request, widget_id):
    """
    PUT: ویرایش ویجت
    DELETE: حذف ویجت
    """
    if not _allowed(request.user):
        return fail("Permission denied", status=403)
    try:
        widget = DashboardWidget.objects.get(id=widget_id, user=request.user)
    except DashboardWidget.DoesNotExist:
        return fail("ویجت یافت نشد.", status=404)
    
    if request.method == "PUT":
        data = parse_json(request)
        metric = (data.get("config") or widget.config or {}).get("metric")
        if not _allowed(request.user, metric):
            return fail("Permission denied", status=403)
        
        if "title" in data:
            widget.title = data["title"]
        if "config" in data:
            widget.config = data["config"]
        if "size" in data:
            widget.size = data["size"]
        if "position" in data:
            widget.position = data["position"]
        
        widget.save()
        return success({"id": widget.id, "title": widget.title})
    
    # DELETE
    widget.delete()
    return success({})


@api_view("POST")
def widgets_reorder(request):
    """تغییر ترتیب ویجت‌ها"""
    if not _allowed(request.user):
        return fail("Permission denied", status=403)
    data = parse_json(request)
    order = data.get("order", [])  # [{id, position}, ...]
    
    for item in order:
        try:
            widget = DashboardWidget.objects.get(id=item["id"], user=request.user)
            widget.position = item["position"]
            widget.save(update_fields=["position"])
        except DashboardWidget.DoesNotExist:
            pass
    
    return success({})


@api_view("GET")
def metric_data(request, metric_name):
    """دریافت داده برای یک metric مشخص"""
    if not _allowed(request.user, metric_name):
        return fail("Permission denied", status=403)
    filters = {
        "time_range": request.GET.get("time_range", "month"),
        "branch": request.GET.get("branch"),
        "category": request.GET.get("category"),
    }
    
    try:
        data = calculate_metric(metric_name, request.user, filters)
        return success(data)
    except ValueError as e:
        return fail(str(e), status=400)
