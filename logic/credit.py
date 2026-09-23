"""سقف اعتبار فروش چکی."""

from decimal import Decimal

from django.db.models import Sum

from backend.models import Sale
from auth.permissions import APPROVE_ACCOUNTING, has_permission


def open_receivable(customer):
    total = (
        Sale.objects.filter(customer=customer)
        .exclude(order_status_ref_id="cancelled")
        .aggregate(final=Sum("final_amount"), paid=Sum("paid_amount"))
    )
    due = Decimal(total["final"] or 0) - Decimal(total["paid"] or 0)
    return due if due > 0 else Decimal(0)


def assert_customer_credit(customer, additional, payment_method, override_reason="", user=None):
    """اگر فروش چکی از سقف بگذرد، بدون دلیل و مجوز تایید رد می‌شود."""
    if (payment_method or "") != "check":
        return ""
    limit = customer.credit_limit
    if limit is None:
        return ""
    extra = Decimal(additional or 0)
    if extra <= 0:
        return ""
    if open_receivable(customer) + extra <= Decimal(limit):
        return ""
    reason = (override_reason or "").strip()
    if not reason:
        raise ValueError("سقف اعتبار مشتری برای این فروش چکی کافی نیست. برای عبور، دلیل الزامی است.")
    if not has_permission(user, APPROVE_ACCOUNTING):
        raise ValueError("عبور از سقف اعتبار فقط با مجوز تایید حسابداری ممکن است.")
    return reason
