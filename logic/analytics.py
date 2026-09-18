"""گزارش‌های تحلیلی — پرفروش‌ترین کالا و مشتریان وفادار."""

from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from backend.models import Customer, Sale, SaleLineItem
from logic.rfm import customer_segment_name


def _countable_sales_qs():
    """فروش‌های معتبر برای آمار (بدون لغوشده و پیش‌فاکتور در انتظار)."""
    return (
        Sale.objects.filter(is_deleted=False)
        .exclude(order_status=Sale.ORDER_STATUS_CANCELLED)
        .exclude(
            order_kind=Sale.ORDER_KIND_PRE_INVOICE,
            order_status=Sale.ORDER_STATUS_PENDING,
        )
    )


def best_selling_products(limit=20):
    """پرفروش‌ترین محصولات بر اساس تعداد فروخته‌شده."""
    limit = min(max(int(limit or 20), 1), 50)
    sale_ids = _countable_sales_qs().values_list("pk", flat=True)
    rows = (
        SaleLineItem.objects.filter(sale_id__in=sale_ids)
        .values("product_id", "product_name", "product_model", "fabric")
        .annotate(
            total_quantity=Sum("quantity"),
            total_revenue=Sum("line_total"),
            sales_count=Count("sale_id", distinct=True),
        )
        .order_by("-total_quantity", "-total_revenue")[:limit]
    )
    return [
        {
            "product_id": row["product_id"],
            "product_name": row["product_name"],
            "product_model": row["product_model"] or "",
            "fabric": row["fabric"] or "",
            "total_quantity": int(row["total_quantity"] or 0),
            "total_revenue": int(row["total_revenue"] or 0),
            "sales_count": row["sales_count"] or 0,
        }
        for row in rows
        if int(row["total_quantity"] or 0) > 0
    ]


def top_repeat_buyers_year(limit=20, min_purchases=2, days=365):
    """مشتریان با حداقل دو خرید در یک سال اخیر — مرتب بر اساس مجموع مبلغ."""
    limit = min(max(int(limit or 20), 1), 50)
    min_purchases = max(int(min_purchases or 2), 2)
    days = max(int(days or 365), 1)
    since = timezone.now() - timedelta(days=days)

    stats = (
        _countable_sales_qs()
        .filter(sold_at__gte=since)
        .values("customer_id")
        .annotate(
            purchase_count=Count("id"),
            year_total=Sum("final_amount"),
        )
        .filter(purchase_count__gte=min_purchases)
        .order_by("-year_total", "-purchase_count")[:limit]
    )

    customer_ids = [row["customer_id"] for row in stats]
    customers = {
        c.id: c
        for c in Customer.objects.filter(id__in=customer_ids, is_active=True).select_related(
            "rfm_score", "rfm_score__segment"
        )
    }

    results = []
    for row in stats:
        customer = customers.get(row["customer_id"])
        if not customer:
            continue
        results.append(
            {
                "customer_id": customer.id,
                "full_name": customer.full_name,
                "phone": customer.phone,
                "level": customer_segment_name(customer, empty=None),
                "purchase_count_year": row["purchase_count"],
                "year_purchases_total": int(row["year_total"] or 0),
            }
        )
    return results
