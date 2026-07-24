"""تبدیل تاریخ میلادی به شمسی — همان الگوریتم فرانت‌اند."""


def gregorian_to_jalali(gy, gm, gd):
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    jy = 0 if gy <= 1600 else 979
    gy -= 621 if gy <= 1600 else 1600
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        - 80
        + gd
    )
    for i in range(gm - 1):
        days += g_days_in_month[i]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    jy += (days - 1) // 365
    if days > 365:
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def date_to_jalali(date):
    """تبدیل datetime.date به (سال، ماه، روز) شمسی."""
    return gregorian_to_jalali(date.year, date.month, date.day)


def jalali_to_gregorian(jy, jm, jd):
    """تبدیل (سال، ماه، روز) شمسی به datetime.date میلادی."""
    from datetime import date

    gy = 621 if jy <= 979 else 1600
    jy -= 0 if jy <= 979 else 979
    days = (
        365 * jy
        + (jy // 33) * 8
        + ((jy % 33) + 3) // 4
        + 78
        + jd
        + (31 * (jm - 1) if jm < 7 else 186 + 30 * (jm - 7))
    )
    gy += 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        gy += 100 * ((days - 1) // 36524)
        days = (days - 1) % 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    gy += (days - 1) // 365
    if days > 0:
        days = (days - 1) % 365
    gd = days + 1
    sal_a = [0, 31, 29 if (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    v = gd
    while gm <= 12 and v > sal_a[gm]:
        v -= sal_a[gm]
        gm += 1
    return date(gy, gm, v)


def parse_jalali_date(text):
    """پارس تاریخ شمسی مثل 1405/01/01."""
    from datetime import datetime, time

    from django.utils import timezone

    raw = str(text or "").strip().replace("-", "/")
    parts = raw.split("/")
    if len(parts) != 3:
        raise ValueError(f"تاریخ شمسی نامعتبر: {text}")
    jy, jm, jd = (int(p) for p in parts)
    gdate = jalali_to_gregorian(jy, jm, jd)
    dt = datetime.combine(gdate, time.min)
    return timezone.make_aware(dt)
