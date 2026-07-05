"""فیلتر و جستجوی مشتریان."""

from django.db.models import Q

from logic.jalali import date_to_jalali


def apply_customer_filters(qs, params):
    """اعمال فیلترهای لیست مشتریان روی queryset."""
    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(Q(full_name__icontains=search) | Q(phone__icontains=search))

    jmonth = params.get("birthday_jmonth")
    jday = params.get("birthday_jday")
    if jmonth not in (None, "") and jday not in (None, ""):
        try:
            qs = filter_by_jalali_birthday(qs, int(jmonth), int(jday))
        except (TypeError, ValueError):
            pass

    return qs


def filter_by_jalali_birthday(qs, jmonth, jday):
    """مشتریانی که تولدشان در همان روز/ماه شمسی است (سال مهم نیست)."""
    if not (1 <= jmonth <= 12 and 1 <= jday <= 31):
        return qs.none()

    matching_ids = []
    base = qs.model.objects.filter(pk__in=qs.values_list("pk", flat=True), birthday__isnull=False)
    for row in base.values("id", "birthday"):
        _, cjm, cjd = date_to_jalali(row["birthday"])
        if cjm == jmonth and cjd == jday:
            matching_ids.append(row["id"])

    if not matching_ids:
        return qs.none()
    return qs.filter(id__in=matching_ids)
