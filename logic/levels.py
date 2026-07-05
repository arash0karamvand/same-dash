"""منطق سطح‌بندی داینامیک مشتریان بر اساس بازه‌های تعریف‌شده توسط مدیر.

هیچ آستانه‌ای در کد hard-code نشده است؛ سطح مناسب صرفاً از روی بازه‌های
[min_purchase, max_purchase) که مدیر در جدول LoyaltyLevel تعریف کرده انتخاب
می‌شود. هر تغییر سطح در CustomerLevelHistory ثبت می‌گردد.
"""

from django.db.models import Q

from backend.models import CustomerLevelHistory, LoyaltyLevel


def find_level_for_amount(total_amount):
    """سطح فعالی که مبلغ داده‌شده در بازه [min, max) آن قرار می‌گیرد را برمی‌گرداند.

    - شرط پایین: min_purchase <= total_amount
    - شرط بالا: max_purchase تهی باشد (بدون سقف) یا total_amount < max_purchase
    اگر چند سطح واجد شرایط باشند، سطحی با بزرگ‌ترین min_purchase انتخاب می‌شود.
    اگر هیچ سطحی واجد شرایط نباشد None برمی‌گردد.
    """
    return (
        LoyaltyLevel.objects.filter(is_active=True, min_purchase__lte=total_amount)
        .filter(Q(max_purchase__isnull=True) | Q(max_purchase__gt=total_amount))
        .order_by("-min_purchase")
        .first()
    )


def recalculate_customer_level(
    customer, reason="بازمحاسبه بر اساس مجموع خرید", save=True, user=None, send_level_up_sms=True
):
    """سطح مشتری را بر اساس مجموع خرید فعلی‌اش دوباره محاسبه می‌کند."""
    old_level_id = customer.level_id
    new_level = find_level_for_amount(customer.total_purchases)
    new_level_id = new_level.id if new_level else None

    if customer.level_id != new_level_id:
        CustomerLevelHistory.objects.create(
            customer=customer,
            previous_level=customer.level,
            new_level=new_level,
            reason=reason,
            total_purchases_at_change=customer.total_purchases,
        )
        customer.level = new_level
        if save:
            customer.save(update_fields=["level"])
        if send_level_up_sms and new_level and old_level_id != new_level_id:
            from logic.sms_club import maybe_send_level_up

            maybe_send_level_up(customer, new_level, user=user)

    return new_level


# نام مستعار برای استفاده در API و سایر ماژول‌ها (طبق قرارداد پروژه).
update_customer_level = recalculate_customer_level
