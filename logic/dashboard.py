"""منطق خلاصه داشبورد."""

from django.db.models import Count, Sum
from django.utils import timezone

from auth.permissions import MANAGE_ATTENDANCE, has_permission, is_system_admin
from backend.models import Customer, LoyaltyLevel, Sale, SMSLog, StaffAttendance
from logic.attendance import attendance_to_dict
from logic.sales_day import (
    filter_sales_for_jalali_day,
    filter_sales_for_jalali_month,
    filter_sales_for_jalali_range,
    jalali_week_bounds,
    today_jalali,
)


def build_dashboard_summary(user):
    """ساخت payload خلاصه داشبورد برای کاربر فعلی."""
    total_sales_amount = Sale.objects.aggregate(total=Sum("final_amount"))["total"] or 0

    level_distribution = [
        {
            "name": level.name,
            "color": level.color,
            "count": level.customers.count(),
        }
        for level in LoyaltyLevel.objects.all()
    ]

    recent_sales = Sale.objects.select_related("customer", "seller").order_by("-sold_at")[:5]
    all_sales = Sale.objects.all()

    jy, jm, jd = today_jalali()
    sales_today = filter_sales_for_jalali_day(all_sales, jy, jm, jd).aggregate(
        total=Sum("final_amount"), count=Count("id")
    )

    week_start, week_end = jalali_week_bounds()
    sales_this_week = filter_sales_for_jalali_range(
        all_sales, *week_start, *week_end
    ).aggregate(total=Sum("final_amount"), count=Count("id"))

    sales_this_month = filter_sales_for_jalali_month(all_sales, jy, jm).aggregate(
        total=Sum("final_amount"), count=Count("id")
    )

    today = timezone.localdate()

    payload = {
        "customers_count": Customer.objects.count(),
        "active_customers": Customer.objects.filter(is_active=True).count(),
        "sales_today": {
            "count": sales_today["count"] or 0,
            "total": int(sales_today["total"] or 0),
            "jalali_year": jy,
            "jalali_month": jm,
            "jalali_day": jd,
        },
        "sales_this_week": {
            "count": sales_this_week["count"] or 0,
            "total": int(sales_this_week["total"] or 0),
            "start_jalali_year": week_start[0],
            "start_jalali_month": week_start[1],
            "start_jalali_day": week_start[2],
            "end_jalali_year": week_end[0],
            "end_jalali_month": week_end[1],
            "end_jalali_day": week_end[2],
        },
        "total_sales_amount": int(total_sales_amount),
        "sms_sent": SMSLog.objects.filter(status="sent").count(),
        "sales_this_month": {
            "count": sales_this_month["count"] or 0,
            "total": int(sales_this_month["total"] or 0),
            "jalali_year": jy,
            "jalali_month": jm,
        },
        "level_distribution": level_distribution,
        "recent_sales": [
            {
                "id": s.id,
                "customer_name": s.customer.full_name,
                "amount": int(s.final_amount),
                "seller_name": s.seller.full_name if s.seller_id else None,
                "branch": s.branch_id,
                "created_at": s.sold_at.isoformat(),
            }
            for s in recent_sales
        ],
    }

    if is_system_admin(user):
        today_attendance = (
            StaffAttendance.objects.filter(date=today)
            .select_related("seller", "recorded_by", "approved_by")
            .order_by("-check_in_at", "-created_at")
        )
        payload["attendance_today"] = {
            "count": today_attendance.count(),
            "results": [attendance_to_dict(r) for r in today_attendance[:30]],
        }

    if has_permission(user, MANAGE_ATTENDANCE):
        pending = StaffAttendance.objects.filter(approval_status="pending").select_related("seller")[:20]
        payload["pending_attendance"] = [attendance_to_dict(r) for r in pending]

    return payload
