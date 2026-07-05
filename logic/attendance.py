"""منطق حضور و غیاب — ورود، خروج، خروج خودکار ۱۶ ساعته."""

from datetime import timedelta

from django.utils import timezone

from backend.models import StaffAttendance

AUTO_CHECKOUT_HOURS = 16


def apply_auto_checkout(record):
    """اگر بیش از ۱۶ ساعت از ورود گذشته و خروج ثبت نشده، خودکار پایان کار."""
    if not record.check_in_at or record.check_out_at:
        return record
    limit = record.check_in_at + timedelta(hours=AUTO_CHECKOUT_HOURS)
    if timezone.now() >= limit:
        record.check_out_at = limit
        record.save(update_fields=["check_out_at"])
    return record


def today_record_for_seller(seller):
    day = timezone.localdate()
    record = (
        StaffAttendance.objects.filter(seller=seller, date=day)
        .select_related("seller", "approved_by")
        .first()
    )
    if record:
        apply_auto_checkout(record)
        record.refresh_from_db()
    return record
