"""فیلترهای مشترک queryset."""

from datetime import datetime

from django.db.models import Q
from django.utils import timezone


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def apply_sales_filters(qs, params):
    customer_id = params.get("customer")
    if customer_id:
        qs = qs.filter(customer_id=customer_id)

    payment_status = params.get("payment_status")
    if payment_status:
        if payment_status == "partial":
            payment_status = "installment"
        qs = qs.filter(payment_status=payment_status)

    payment_method = params.get("payment_method")
    if payment_method:
        qs = qs.filter(payment_method=payment_method)

    date_from = parse_date(params.get("date_from"))
    date_to = parse_date(params.get("date_to"))
    if date_from or date_to:
        from logic.jalali import date_to_jalali
        from logic.sales_day import filter_sales_for_gregorian_date, filter_sales_for_jalali_range

        if date_from and date_to:
            if date_from == date_to:
                qs = filter_sales_for_gregorian_date(qs, date_from)
            else:
                jy1, jm1, jd1 = date_to_jalali(date_from)
                jy2, jm2, jd2 = date_to_jalali(date_to)
                qs = filter_sales_for_jalali_range(qs, jy1, jm1, jd1, jy2, jm2, jd2)
        elif date_from:
            qs = filter_sales_for_gregorian_date(qs, date_from)
        elif date_to:
            qs = filter_sales_for_gregorian_date(qs, date_to)

    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(invoice_number__icontains=search)
            | Q(customer__full_name__icontains=search)
            | Q(customer__phone__icontains=search)
        )

    branch = (params.get("branch") or "").strip()
    if branch:
        qs = qs.filter(branch=branch)

    include_deleted = params.get("include_deleted") == "1"
    if include_deleted and hasattr(qs.model, "all_objects"):
        qs = qs.model.all_objects.filter(pk__in=qs.values_list("pk", flat=True))
        if not params.get("deleted_only"):
            pass
    if params.get("deleted_only") == "1" and hasattr(qs.model, "all_objects"):
        qs = qs.model.all_objects.deleted()

    return qs


def apply_attendance_filters(qs, params):
    seller_id = params.get("seller") or params.get("seller_id")
    if seller_id:
        qs = qs.filter(seller_id=seller_id)
    branch = (params.get("branch") or "").strip()
    if branch:
        qs = qs.filter(seller__branch=branch)
    date_from = parse_date(params.get("date_from"))
    date_to = parse_date(params.get("date_to"))
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    approval = params.get("approval_status")
    if approval:
        qs = qs.filter(approval_status=approval)
    status = params.get("status")
    if status:
        qs = qs.filter(status=status)
    return qs
