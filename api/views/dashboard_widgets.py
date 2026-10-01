"""API endpoints برای مدیریت ویجت‌های داشبورد."""

from api.helpers import api_view, success, fail, parse_json
from backend.models import DashboardWidget
from logic.dashboard_metrics import calculate_metric


@api_view(["GET", "POST"])
def widgets_list(request):
    """
    GET: لیست ویجت‌های کاربر
    POST: ساخت ویجت جدید
    """
    if request.method == "GET":
        widgets = DashboardWidget.objects.filter(user=request.user).order_by("position")
        
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
    widget = DashboardWidget.objects.create(
        user=request.user,
        widget_type=data["widget_type"],
        title=data["title"],
        config=data.get("config", {}),
        size=data.get("size", "medium"),
        position=data.get("position", 0),
    )
    
    return success({"id": widget.id, "title": widget.title})


@api_view(["PUT", "DELETE"])
def widget_detail(request, widget_id):
    """
    PUT: ویرایش ویجت
    DELETE: حذف ویجت
    """
    try:
        widget = DashboardWidget.objects.get(id=widget_id, user=request.user)
    except DashboardWidget.DoesNotExist:
        return fail("ویجت یافت نشد.", status=404)
    
    if request.method == "PUT":
        data = parse_json(request)
        
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


@api_view(["POST"])
def widgets_reorder(request):
    """تغییر ترتیب ویجت‌ها"""
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


@api_view(["GET"])
def metric_data(request, metric_name):
    """دریافت داده برای یک metric مشخص"""
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
