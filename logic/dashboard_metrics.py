"""محاسبه metrics برای ویجت‌های داشبورد."""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from backend.models import Sale, Customer, Material, RfmSegment


def calculate_metric(metric_name, user, filters=None):
    """محاسبه یک metric مشخص"""
    filters = filters or {}
    time_range = filters.get("time_range", "month")
    
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
        sales = Sale.objects.filter(created_at__date=now.date())
        return {
            "total": sales.aggregate(total=Sum("final_amount"))["total"] or 0,
            "count": sales.count(),
        }
    
    elif metric_name == "sales_week":
        sales = Sale.objects.filter(created_at__gte=now - timedelta(days=7))
        return {
            "total": sales.aggregate(total=Sum("final_amount"))["total"] or 0,
            "count": sales.count(),
        }
    
    elif metric_name == "sales_month":
        sales = Sale.objects.filter(created_at__gte=now - timedelta(days=30))
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
                Sale.objects.filter(created_at__date=date).aggregate(
                    total=Sum("final_amount")
                )["total"]
                or 0
            )
            data.append({"date": date.isoformat(), "total": float(total)})
        return data
    
    elif metric_name == "top_customers":
        # Top 10 customers by revenue
        customers = (
            Sale.objects.values("customer__name")
            .annotate(total=Sum("final_amount"), count=Count("id"))
            .order_by("-total")[:10]
        )
        return [
            {
                "name": c["customer__name"],
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
        materials = Material.objects.all()
        low_stock = materials.filter(quantity__lt=10).count()
        out_of_stock = materials.filter(quantity=0).count()
        in_stock = materials.filter(quantity__gte=10).count()
        
        return {
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "in_stock": in_stock,
            "total": materials.count(),
        }
    
    elif metric_name == "pending_approvals":
        # This would depend on your workflow
        from backend.models import OfficeOrder
        
        pending = OfficeOrder.objects.filter(
            workflow_stage__slug="pending_branch"
        ).count()
        
        return {"count": pending}
    
    else:
        raise ValueError(f"Unknown metric: {metric_name}")
