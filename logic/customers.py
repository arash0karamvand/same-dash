"""فیلتر و CRUD مشتریان."""

from django.db.models import Q
from django.utils.dateparse import parse_date

from backend.models import Customer
from logic.jalali import date_to_jalali
from logic.membership import generate_membership_code


def apply_customer_filters(qs, params):
    """اعمال فیلترهای لیست مشتریان روی queryset."""
    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(full_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(membership_code__icontains=search)
        )

    level_id = params.get("level_id") or params.get("level") or params.get("segment_id")
    if level_id not in (None, ""):
        qs = qs.filter(rfm_score__segment_id=level_id)

    active = params.get("is_active") if params.get("is_active") not in (None, "") else params.get("active")
    if active in ("1", "true", "True"):
        qs = qs.filter(is_active=True)
    elif active in ("0", "false", "False"):
        qs = qs.filter(is_active=False)

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


def parse_birthday(data):
    if "birthday" not in data:
        return None, False
    raw = data.get("birthday")
    if not raw:
        return None, True
    parsed = parse_date(str(raw).strip()[:10])
    if not parsed:
        raise ValueError("تاریخ تولد نامعتبر است.")
    return parsed, True


def list_customers(params):
    qs = Customer.objects.select_related("level", "rfm_score", "rfm_score__segment").all()
    return apply_customer_filters(qs, params)


def create_customer(data):
    full_name = (data.get("full_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not full_name or not phone:
        raise ValueError("Full name and phone are required")
    if Customer.objects.filter(phone=phone).exists():
        raise ValueError("Customer with this phone already exists")

    birthday, has_birthday = parse_birthday(data)
    credit_limit = _parse_credit_limit(data)
    customer = Customer.objects.create(
        full_name=full_name,
        phone=phone,
        email=(data.get("email") or "").strip(),
        address=(data.get("address") or "").strip(),
        notes=(data.get("notes") or "").strip(),
        membership_code=generate_membership_code(),
        credit_limit=credit_limit,
    )
    if has_birthday:
        customer.birthday = birthday
        customer.save(update_fields=["birthday"])
    return customer


def update_customer(customer, data):
    birthday, has_birthday = parse_birthday(data)
    for field in ("full_name", "email", "notes", "address"):
        if field in data:
            setattr(customer, field, (data.get(field) or "").strip())
    if "phone" in data:
        new_phone = (data.get("phone") or "").strip()
        if Customer.objects.filter(phone=new_phone).exclude(pk=customer.pk).exists():
            raise ValueError("Phone number already used by another customer")
        customer.phone = new_phone
    if "is_active" in data:
        customer.is_active = bool(data.get("is_active"))
    if has_birthday:
        customer.birthday = birthday
    if "credit_limit" in data:
        customer.credit_limit = _parse_credit_limit(data)
    customer.save()
    return customer


def _parse_credit_limit(data):
    if "credit_limit" not in data:
        return None
    raw = data.get("credit_limit")
    if raw in (None, ""):
        return None
    from decimal import Decimal, InvalidOperation

    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError):
        raise ValueError("سقف اعتبار نامعتبر است.")
    if value < 0:
        raise ValueError("سقف اعتبار نمی‌تواند منفی باشد.")
    return value


def get_customer(pk, with_level=False):
    qs = Customer.objects.select_related("level", "rfm_score", "rfm_score__segment") if with_level else Customer.objects
    try:
        return qs.get(pk=pk)
    except Customer.DoesNotExist:
        return None


def customer_history_payload(customer, sale_to_dict, level_history_to_dict):
    sales = customer.sales.prefetch_related("line_items").order_by("-sold_at")
    history = customer.level_history.select_related("previous_level", "new_level").all()
    items = [level_history_to_dict(h) for h in history]
    rfm_logs = customer.rfm_action_logs.filter(
        action_type="segment_change"
    ).select_related("segment", "previous_segment")
    for log in rfm_logs:
        items.append(
            {
                "id": f"rfm-{log.id}",
                "customer_id": log.customer_id,
                "previous_level": log.previous_segment.name if log.previous_segment_id else None,
                "new_level": log.segment.name if log.segment_id else None,
                "reason": "تغییر بخش RFM",
                "total_purchases_at_change": 0,
                "changed_at": log.sent_at.isoformat(),
            }
        )
    items.sort(key=lambda row: row.get("changed_at") or "", reverse=True)
    return {
        "sales": [sale_to_dict(s, include_lines=True) for s in sales],
        "level_history": items,
    }


def recalculate_all_customer_levels(update_fn):
    count = 0
    for customer in Customer.objects.all():
        update_fn(customer, reason="Bulk recalculation via API")
        count += 1
    return count
