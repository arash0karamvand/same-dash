"""محاسبه metrics برای ویجت‌های داشبورد."""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from backend.models import Customer, Material, ProductionRun, RfmSegment
from logic.sales_reports import sales_report_queryset


def calculate_metric(metric_name, user, filters=None):
    """محاسبه یک metric مشخص"""
    filters = filters or {}
    time_range = filters.get("time_range", "month")
    branch = (filters.get("branch") or "").strip() or None
    visible_sales = sales_report_queryset(user, branch)
    
    # Calculate date range
    now = timezone.now()
    if time_range == "week":
        start_date = now - timedelta(days=7)
    elif time_range == "month":
        start_date = now - timedelta(days=30)
    elif time_range == "year":
        start_date = now - timedelta(days=365)
    else:
        start_date = None
    
    # Sales metrics
    if metric_name == "sales_today":
        sales = visible_sales.filter(created_at__date=now.date())
        return {
            "total": sales.aggregate(total=Sum("final_amount"))["total"] or 0,
            "count": sales.count(),
        }
    
    elif metric_name == "sales_week":
        sales = visible_sales.filter(created_at__gte=now - timedelta(days=7))
        return {
            "total": sales.aggregate(total=Sum("final_amount"))["total"] or 0,
            "count": sales.count(),
        }
    
    elif metric_name == "sales_month":
        sales = visible_sales.filter(created_at__gte=now - timedelta(days=30))
        return {
            "total": sales.aggregate(total=Sum("final_amount"))["total"] or 0,
            "count": sales.count(),
        }
    
    elif metric_name == "revenue_trend":
        # Last 30 days revenue by day
        data = []
        for i in range(30):
            date = (now - timedelta(days=29 - i)).date()
            total = (
                visible_sales.filter(created_at__date=date).aggregate(
                    total=Sum("final_amount")
                )["total"]
                or 0
            )
            data.append({"date": date.isoformat(), "total": float(total)})
        return data
    
    elif metric_name == "top_customers":
        # Top 10 customers by revenue
        customers = (
            visible_sales.values("customer__full_name")
            .annotate(total=Sum("final_amount"), count=Count("id"))
            .order_by("-total")[:10]
        )
        return [
            {
                "name": c["customer__full_name"],
                "total": float(c["total"]),
                "count": c["count"],
            }
            for c in customers
        ]
    
    elif metric_name == "rfm_distribution":
        # RFM level distribution
        segments = RfmSegment.objects.all()
        data = []
        for segment in segments:
            count = Customer.objects.filter(current_segment=segment).count()
            data.append({
                "name": segment.name,
                "count": count,
                "color": segment.color or "#999",
            })
        return data
    
    elif metric_name == "inventory_status":
        # Material stock summary
        materials = list(Material.objects.filter(is_deleted=False, is_active=True))
        stocks = [material.stock or 0 for material in materials]
        low_stock = sum(1 for stock in stocks if 0 < stock < 10)
        out_of_stock = sum(1 for stock in stocks if stock <= 0)
        in_stock = sum(1 for stock in stocks if stock >= 10)
        
        return {
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "in_stock": in_stock,
            "total": len(materials),
        }
    
    elif metric_name == "pending_approvals":
        # This would depend on your workflow
        from backend.models import OfficeOrder
        
        pending = OfficeOrder.objects.filter(
            workflow_stage__slug="pending_branch"
        ).count()
        
        return {"count": pending}

    elif metric_name == "material_inventory_value":
        materials = Material.objects.filter(is_deleted=False, is_active=True)
        value = sum(
            (material.stock or 0) * (material.unit_cost or 0)
            for material in materials
        )
        return {"total": float(value), "count": materials.count()}

    elif metric_name in ("production_cost_summary", "production_cost_trend"):
        runs = ProductionRun.objects.filter(status=ProductionRun.STATUS_COMPLETED)
        if start_date:
            runs = runs.filter(completed_at__gte=start_date)
        if branch:
            runs = runs.filter(sale__branch_id=branch)
        if metric_name == "production_cost_summary":
            totals = runs.aggregate(
                total=Sum("total_cost"),
                materials=Sum("actual_material_cost"),
                overhead=Sum("overhead_cost"),
                count=Count("id"),
            )
            return {
                "total": float(totals["total"] or 0),
                "materials": float(totals["materials"] or 0),
                "overhead": float(totals["overhead"] or 0),
                "count": totals["count"] or 0,
            }
        days = 30 if time_range != "week" else 7
        data = []
        for i in range(days):
            day = (now - timedelta(days=days - 1 - i)).date()
            total = runs.filter(completed_at__date=day).aggregate(total=Sum("total_cost"))["total"] or 0
            data.append({"date": day.isoformat(), "total": float(total)})
        return data
    
    else:
        raise ValueError(f"Unknown metric: {metric_name}")
