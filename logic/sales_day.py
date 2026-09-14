"""فیلتر فروش بر اساس روز شمسی — ۱۲ تیر فقط ۱۲ تیر، بدون قاطی با روز دیگر."""

from datetime import timedelta

from django.utils import timezone

from logic.jalali import date_to_jalali


def _jalali_ordinal(jy, jm, jd):
    return jy * 10000 + jm * 100 + jd


def sold_at_jalali(sold_at):
    """(سال، ماه، روز) شمسی زمان فروش — همیشه بر اساس Asia/Tehran."""
    local = timezone.localtime(sold_at)
    return date_to_jalali(local.date())


def sale_jalali_date(sale):
    return sold_at_jalali(sale.sold_at)


def _sold_at_rows(qs):
    """pk و sold_at بدون تداخل select_related با only()."""
    return qs.model.objects.filter(pk__in=qs.values("pk")).values_list("pk", "sold_at")


def today_jalali():
    return date_to_jalali(timezone.localdate())


def jalali_week_bounds(day=None):
    """شروع و پایان هفته شمسی (شنبه تا جمعه) به‌صورت دو تاپل (سال، ماه، روز)."""
    day = day or timezone.localdate()
    start = day - timedelta(days=(day.weekday() + 2) % 7)
    end = start + timedelta(days=6)
    return date_to_jalali(start), date_to_jalali(end)


def filter_sales_for_jalali_day(qs, jy, jm, jd):
    """فقط فروش‌های همان روز شمسی."""
    target = (jy, jm, jd)
    ids = [pk for pk, sold_at in _sold_at_rows(qs) if sold_at_jalali(sold_at) == target]
    if not ids:
        return qs.none()
    return qs.filter(pk__in=ids)


def filter_sales_for_jalali_range(qs, jy1, jm1, jd1, jy2, jm2, jd2):
    """فروش‌های بین دو روز شمسی (شامل هر دو)."""
    lo = _jalali_ordinal(jy1, jm1, jd1)
    hi = _jalali_ordinal(jy2, jm2, jd2)
    if lo > hi:
        lo, hi = hi, lo
    ids = []
    for pk, sold_at in _sold_at_rows(qs):
        jy, jm, jd = sold_at_jalali(sold_at)
        o = _jalali_ordinal(jy, jm, jd)
        if lo <= o <= hi:
            ids.append(pk)
    if not ids:
        return qs.none()
    return qs.filter(pk__in=ids)


def filter_sales_for_gregorian_date(qs, day):
    """تاریخ میلادی انتخاب‌شده از تقویم = یک روز شمسی مشخص."""
    jy, jm, jd = date_to_jalali(day)
    return filter_sales_for_jalali_day(qs, jy, jm, jd)


def filter_sales_for_jalali_year(qs, jy):
    """فروش‌های یک سال شمسی."""
    ids = []
    for pk, sold_at in _sold_at_rows(qs):
        sy, _, _ = sold_at_jalali(sold_at)
        if sy == jy:
            ids.append(pk)
    if not ids:
        return qs.none()
    return qs.filter(pk__in=ids)


def filter_sales_for_jalali_month(qs, jy, jm):
    """فروش‌های یک ماه شمسی."""
    ids = []
    for pk, sold_at in _sold_at_rows(qs):
        sy, sm, _ = sold_at_jalali(sold_at)
        if sy == jy and sm == jm:
            ids.append(pk)
    if not ids:
        return qs.none()
    return qs.filter(pk__in=ids)


def apply_jalali_period(qs, period, jy, jm=None, jd=None):
    """فیلتر فروش بر اساس روز / ماه / سال شمسی."""
    if period == "day":
        if jm is None or jd is None:
            raise ValueError("برای فیلتر روز، ماه و روز الزامی است.")
        return filter_sales_for_jalali_day(qs, jy, jm, jd)
    if period == "month":
        if jm is None:
            raise ValueError("برای فیلتر ماه، سال و ماه الزامی است.")
        return filter_sales_for_jalali_month(qs, jy, jm)
    if period == "year":
        return filter_sales_for_jalali_year(qs, jy)
    raise ValueError("بازه نامعتبر است.")
