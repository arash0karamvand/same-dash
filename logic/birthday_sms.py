"""پیامک خودکار تبریک تولد مشتریان."""

from datetime import datetime, time as dt_time, timedelta

from django.utils import timezone

from backend.models import BirthdaySmsExclusion, BirthdaySmsSettings, Customer, SMSLog
from logic.sms import send_sms, _bulk_result

DEFAULT_TEMPLATE = "تولدت مبارک {name}! از طرف {shop_name} بهترین‌ها را برایت آرزومندیم."

TEMPLATE_VARS = ("name", "shop_name", "phone")


def get_settings():
    return BirthdaySmsSettings.get_solo()


def render_birthday_message(template, customer, shop_name):
    text = (template or DEFAULT_TEMPLATE).strip()
    return text.format(
        name=customer.full_name,
        shop_name=shop_name or "سام اکسون",
        phone=customer.phone,
    )


def _today():
    return timezone.localdate()


def _now_local():
    return timezone.localtime()


def customers_with_birthday_on(date=None):
    """مشتریان فعال با تولد در همان روز/ماه (سال مهم نیست)."""
    date = date or _today()
    return Customer.objects.filter(
        is_active=True,
        is_deleted=False,
        birthday__isnull=False,
        birthday__month=date.month,
        birthday__day=date.day,
    ).select_related("level")


def excluded_customer_ids(for_date=None):
    for_date = for_date or _today()
    return set(
        BirthdaySmsExclusion.objects.filter(exclude_date=for_date).values_list(
            "customer_id", flat=True
        )
    )


def already_sent_today(customer_id, for_date=None):
    """آیا امروز برای این مشتری پیامک تولد ارسال شده؟"""
    for_date = for_date or _today()
    start = timezone.make_aware(datetime.combine(for_date, dt_time.min))
    end = start + timedelta(days=1)
    return SMSLog.objects.filter(
        customer_id=customer_id,
        sms_type="birthday",
        created_at__gte=start,
        created_at__lt=end,
    ).exclude(status="failed").exists()


def build_preview(for_date=None, auto_run=False):
    """پیش‌نمایش لیست ارسال امروز + اجرای خودکار در صورت سررسید."""
    for_date = for_date or _today()
    settings = get_settings()
    excluded_ids = excluded_customer_ids(for_date)
    birthday_customers = list(customers_with_birthday_on(for_date))

    recipients = []
    excluded_list = []

    for customer in birthday_customers:
        preview_message = render_birthday_message(
            settings.message_template, customer, settings.shop_name
        )
        item = {
            "customer_id": customer.id,
            "full_name": customer.full_name,
            "phone": customer.phone,
            "birthday": customer.birthday.isoformat(),
            "preview_message": preview_message,
            "already_sent": already_sent_today(customer.id, for_date),
        }
        if customer.id in excluded_ids:
            item["excluded"] = True
            excluded_list.append(item)
        else:
            item["excluded"] = False
            recipients.append(item)

    now = _now_local()
    send_due = (
        settings.is_enabled
        and now.date() == for_date
        and now.time() >= settings.send_time
        and settings.last_run_date != for_date
    )

    auto_result = None
    if auto_run and send_due:
        auto_result = send_birthday_batch(for_date=for_date, user=None, scheduled=True)

    will_send = [
        r for r in recipients if not r["already_sent"] and not r.get("excluded")
    ]

    return {
        "date": for_date.isoformat(),
        "is_enabled": settings.is_enabled,
        "send_time": settings.send_time.strftime("%H:%M"),
        "shop_name": settings.shop_name,
        "message_template": settings.message_template,
        "last_run_date": settings.last_run_date.isoformat() if settings.last_run_date else None,
        "send_due": send_due,
        "total_birthdays": len(birthday_customers),
        "will_send_count": len(will_send),
        "excluded_count": len(excluded_list),
        "recipients": recipients,
        "excluded": excluded_list,
        "template_vars": list(TEMPLATE_VARS),
        "auto_result": auto_result,
    }


def exclude_customer(customer_id, for_date=None):
    for_date = for_date or _today()
    customer = Customer.objects.filter(pk=customer_id, is_active=True).first()
    if not customer:
        raise ValueError("مشتری یافت نشد.")
    BirthdaySmsExclusion.objects.get_or_create(customer=customer, exclude_date=for_date)
    return customer


def remove_exclusion(customer_id, for_date=None):
    for_date = for_date or _today()
    BirthdaySmsExclusion.objects.filter(customer_id=customer_id, exclude_date=for_date).delete()


def update_settings(data):
    settings = get_settings()
    if "is_enabled" in data:
        settings.is_enabled = bool(data.get("is_enabled"))
    if "message_template" in data:
        template = (data.get("message_template") or "").strip()
        if not template:
            raise ValueError("متن پیام نمی‌تواند خالی باشد.")
        settings.message_template = template
    if "shop_name" in data:
        settings.shop_name = (data.get("shop_name") or "سام اکسون").strip()[:100]
    if "send_time" in data:
        raw = (data.get("send_time") or "").strip()
        if raw:
            parts = raw.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            from datetime import time as dt_time

            settings.send_time = dt_time(hour, minute)
    settings.save()
    return settings


def settings_to_dict(settings=None):
    settings = settings or get_settings()
    return {
        "is_enabled": settings.is_enabled,
        "message_template": settings.message_template,
        "shop_name": settings.shop_name,
        "send_time": settings.send_time.strftime("%H:%M"),
        "last_run_date": settings.last_run_date.isoformat() if settings.last_run_date else None,
        "template_vars": list(TEMPLATE_VARS),
    }


def send_birthday_batch(for_date=None, user=None, scheduled=False, force=False):
    """ارسال پیامک تولد به مشتریان واجد شرایط."""
    for_date = for_date or _today()
    settings = get_settings()

    if not settings.is_enabled and not force:
        raise ValueError("ارسال خودکار تولد غیرفعال است.")

    if scheduled and settings.last_run_date == for_date and not force:
        return {"successful": 0, "failed": 0, "skipped": 0, "results": [], "already_ran": True}

    excluded_ids = excluded_customer_ids(for_date)
    customers = customers_with_birthday_on(for_date)
    logs = []

    for customer in customers:
        if customer.id in excluded_ids:
            continue
        if already_sent_today(customer.id, for_date) and not force:
            continue
        message = render_birthday_message(
            settings.message_template, customer, settings.shop_name
        )
        logs.append(
            send_sms(
                customer.phone,
                message,
                customer=customer,
                sms_type="birthday",
                user=user,
            )
        )

    if scheduled or logs:
        settings.last_run_date = for_date
        settings.save(update_fields=["last_run_date", "updated_at"])

    result = _bulk_result(logs)
    result["already_ran"] = False
    return result
