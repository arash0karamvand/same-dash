"""گزارش و لیست فروش — queryset، مجوز، تجمیع و payload گزارش‌ها."""

from datetime import datetime

from django.db.models import Count, Sum
from django.utils import timezone

from auth.org_roles import is_branch_supervisor, is_executive_user, sales_expert_summary_only
from auth.permissions import (
    APPROVE_SALE_BRANCH,
    VIEW_OWN_SALES,
    VIEW_SALES,
    VIEW_SALES_SUMMARY,
    has_permission,
)
from backend.models import Sale
from logic.employee_ranking import build_employee_ranking
from logic.jalali import date_to_jalali
from logic.sale_workflow import STAGE_PENDING_BRANCH
from logic.sales_day import (
    filter_sales_for_gregorian_date,
    filter_sales_for_jalali_month,
    filter_sales_for_jalali_year,
    sold_at_jalali,
    today_jalali,
)
from logic.sellers import effective_sale_branch, get_user_branch


def can_list_sales(user):
    if sales_expert_summary_only(user):
        return False
    if is_executive_user(user):
        return True
    return has_permission(user, APPROVE_SALE_BRANCH) or is_branch_supervisor(user)


def can_view_sales_reports(user):
    return (
        is_executive_user(user)
        or is_branch_supervisor(user)
        or has_permission(user, VIEW_SALES)
        or has_permission(user, VIEW_OWN_SALES)
        or has_permission(user, VIEW_SALES_SUMMARY)
        or has_permission(user, APPROVE_SALE_BRANCH)
    )


def sales_queryset(user, params=None):
    """صف فروشگاه — فقط سفارش‌های معلق تا ارسال به اداری."""
    params = params or {}
    qs = Sale.objects.select_related("customer", "recorded_by", "seller").prefetch_related(
        "installments", "line_items"
    )
    pending_q = qs.filter(
        workflow_stage=STAGE_PENDING_BRANCH,
        transferred_to_office_at__isnull=True,
    )
    if is_executive_user(user):
        queue = (params.get("queue") or "").strip()
        if queue == "branch":
            return pending_q
        return qs
    if has_permission(user, APPROVE_SALE_BRANCH) or is_branch_supervisor(user):
        branch = get_user_branch(user) or effective_sale_branch(user)
        if branch:
            return pending_q.filter(branch=branch)
        return qs.none()
    return qs.none()


def sales_report_queryset(user, branch_param=None):
    """گزارش فروش شعبه — همه ثبت‌ها در بازه، حتی پس از ارسال به اداری."""
    qs = Sale.objects.select_related("customer", "recorded_by", "seller").prefetch_related(
        "installments", "line_items"
    ).exclude(order_status=Sale.ORDER_STATUS_CANCELLED)

    branch_param = (branch_param or "").strip() or None

    if sales_expert_summary_only(user):
        return qs.filter(recorded_by=user)

    if is_executive_user(user):
        if branch_param:
            return qs.filter(branch=branch_param)
        return qs

    if has_permission(user, APPROVE_SALE_BRANCH) or is_branch_supervisor(user):
        branch = branch_param or get_user_branch(user) or effective_sale_branch(user)
        if branch:
            return qs.filter(branch=branch)
        return qs.none()

    if has_permission(user, VIEW_OWN_SALES) and not has_permission(user, VIEW_SALES):
        branch = get_user_branch(user) or effective_sale_branch(user)
        if branch:
            return qs.filter(branch=branch)
        return qs.filter(recorded_by=user)

    if has_permission(user, VIEW_SALES):
        if branch_param:
            return qs.filter(branch=branch_param)
        return qs

    return qs.none()


def get_sale(pk, include_deleted=False):
    manager = Sale.all_objects if include_deleted else Sale.objects
    try:
        return manager.select_related("customer", "recorded_by", "seller").prefetch_related(
            "installments", "line_items"
        ).get(pk=pk)
    except Sale.DoesNotExist:
        return None


def aggregate_sales(qs):
    qs = qs.exclude(order_status=Sale.ORDER_STATUS_CANCELLED)
    agg = qs.aggregate(
        count=Count("id"),
        total_final=Sum("final_amount"),
        total_paid=Sum("paid_amount"),
    )
    return {
        "count": agg["count"] or 0,
        "total_final": int(agg["total_final"] or 0),
        "total_paid": int(agg["total_paid"] or 0),
    }


def parse_period_params(params):
    period = (params.get("period") or "month").strip().lower()
    if period not in {"day", "month", "year"}:
        raise ValueError("بازه باید day، month یا year باشد.")
    jy, jm, jd = today_jalali()
    year = int(params.get("year") or jy)
    month = int(params.get("month") or jm)
    day = int(params.get("day") or jd)
    return period, year, month, day


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _expert_or_report_qs(user, branch):
    if sales_expert_summary_only(user):
        return Sale.objects.filter(recorded_by=user).exclude(
            order_status=Sale.ORDER_STATUS_CANCELLED
        )
    return sales_report_queryset(user, branch)


def _params_dict(params):
    """QueryDict یا dict را به dict ساده تبدیل می‌کند (آخرین مقدار هر کلید)."""
    if params is None:
        return {}
    if hasattr(params, "lists"):
        return {k: params.get(k) for k in params.keys()}
    return dict(params)


def build_daily_sales_report(user, params):
    """گزارش روزانه — کلید sales برای serialization در view."""
    params = _params_dict(params)
    day = _parse_date(params.get("date")) or timezone.localdate()
    jy, jm, jd = date_to_jalali(day)
    branch = (params.get("branch") or "").strip() or None
    qs = filter_sales_for_gregorian_date(sales_report_queryset(user, branch), day)
    return {
        "date": day.isoformat(),
        "jalali_year": jy,
        "jalali_month": jm,
        "jalali_day": jd,
        **aggregate_sales(qs),
        "sales": qs,
    }


def prepare_monthly_sales_queryset(user, params):
    """queryset ماهانه قبل از apply_sales_filters — (qs, year, month)."""
    params = _params_dict(params)
    jy, jm, _ = today_jalali()
    year = int(params.get("year") or jy)
    month = int(params.get("month") or jm)
    branch = (params.get("branch") or "").strip() or None
    qs = _expert_or_report_qs(user, branch)
    qs = filter_sales_for_jalali_month(qs, year, month)
    return qs, year, month


def build_monthly_sales_payload(user, qs, year, month):
    summary_only = sales_expert_summary_only(user)
    return {
        "jalali_year": year,
        "jalali_month": month,
        "year": year,
        "month": month,
        **aggregate_sales(qs),
        "sales": [] if summary_only else qs,
    }


def build_yearly_sales_report(user, params):
    params = _params_dict(params)
    jy, _, _ = today_jalali()
    year = int(params.get("year") or jy)
    branch = (params.get("branch") or "").strip() or None
    qs = _expert_or_report_qs(user, branch)
    qs = filter_sales_for_jalali_year(qs, year)
    summary_only = sales_expert_summary_only(user)
    return {
        "jalali_year": year,
        "year": year,
        **aggregate_sales(qs),
        "sales": [] if summary_only else qs,
    }


def build_daily_breakdown(user, params):
    """خلاصه فروش روزانه — فقط تاریخ و مبلغ، بدون جزئیات سفارش."""
    params = _params_dict(params)
    jy, jm, _ = today_jalali()
    year = int(params.get("year") or jy)
    month = int(params.get("month") or jm)
    branch = (params.get("branch") or "").strip() or None

    qs = _expert_or_report_qs(user, branch)
    qs = filter_sales_for_jalali_month(qs, year, month)

    buckets = {}
    for sold_at, final_amount in qs.values_list("sold_at", "final_amount"):
        dj_y, dj_m, dj_d = sold_at_jalali(sold_at)
        key = (dj_y, dj_m, dj_d)
        if key not in buckets:
            buckets[key] = {"count": 0, "total_final": 0}
        buckets[key]["count"] += 1
        buckets[key]["total_final"] += int(final_amount or 0)

    days = []
    for (dj_y, dj_m, dj_d) in sorted(buckets.keys(), reverse=True):
        agg = buckets[(dj_y, dj_m, dj_d)]
        days.append(
            {
                "jalali_year": dj_y,
                "jalali_month": dj_m,
                "jalali_day": dj_d,
                "count": agg["count"],
                "total_final": agg["total_final"],
            }
        )

    return {
        "jalali_year": year,
        "jalali_month": month,
        "year": year,
        "month": month,
        **aggregate_sales(qs),
        "days": days,
    }


def build_employee_ranking_report(params):
    params = _params_dict(params)
    period, year, month, day = parse_period_params(params)
    branch = (params.get("branch") or "").strip() or None
    qs = Sale.objects.select_related("recorded_by")
    results = build_employee_ranking(
        qs,
        period,
        year,
        jm=month if period in ("day", "month") else None,
        jd=day if period == "day" else None,
        branch=branch,
    )
    total = sum(item["total_final"] for item in results)
    return {
        "period": period,
        "jalali_year": year,
        "jalali_month": month if period in ("day", "month") else None,
        "jalali_day": day if period == "day" else None,
        "branch": branch,
        "total_final": total,
        "results": results,
    }
