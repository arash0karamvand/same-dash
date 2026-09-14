"""منطق حضور و غیاب — ورود، خروج، خروج خودکار ۱۶ ساعته، CRUD مدیر."""

from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date as django_parse_date

from auth.branches import BRANCH_LABELS
from backend.models import Seller, StaffAttendance

AUTO_CHECKOUT_HOURS = 16


def attendance_to_dict(record):
    seller = record.seller
    return {
        "id": record.id,
        "seller_id": seller.id,
        "seller_name": seller.full_name,
        "branch": seller.branch_id,
        "branch_label": BRANCH_LABELS.get(seller.branch_id, "—"),
        "work_branch": record.work_branch_id or seller.branch_id,
        "work_branch_label": BRANCH_LABELS.get(record.work_branch_id or seller.branch_id, "—"),
        "date": record.date.isoformat(),
        "status": record.status,
        "status_display": record.get_status_display(),
        "approval_status": record.approval_status,
        "approval_status_display": record.get_approval_status_display(),
        "notes": record.notes,
        "recorded_by": record.recorded_by.username if record.recorded_by else None,
        "approved_by": record.approved_by.username if record.approved_by else None,
        "approved_at": record.approved_at.isoformat() if record.approved_at else None,
        "check_in_at": record.check_in_at.isoformat() if record.check_in_at else None,
        "check_out_at": record.check_out_at.isoformat() if record.check_out_at else None,
        "is_complete": bool(record.check_out_at),
        "created_at": record.created_at.isoformat(),
        "is_deleted": getattr(record, "is_deleted", False),
    }


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


def get_record(pk):
    try:
        return StaffAttendance.objects.select_related("seller", "recorded_by", "approved_by").get(pk=pk)
    except StaffAttendance.DoesNotExist:
        return None


def get_active_seller(pk, branch=None):
    try:
        seller = Seller.objects.get(pk=pk, is_active=True)
    except Seller.DoesNotExist:
        return None
    if branch and seller.branch_id != branch:
        return None
    return seller


def list_attendance_base_qs():
    return StaffAttendance.objects.select_related("seller", "recorded_by", "approved_by").all()


def upsert_manager_attendance(seller, day, status, user, branch=None, notes=""):
    if status not in ("present", "absent"):
        raise ValueError("Invalid status")
    record, created = StaffAttendance.objects.update_or_create(
        seller=seller,
        date=day,
        defaults={
            "status": status,
            "work_branch_id": branch or seller.branch_id,
            "approval_status": "approved",
            "notes": (notes or "").strip(),
            "recorded_by": user,
            "approved_by": user,
            "approved_at": timezone.now(),
            "is_deleted": False,
            "deleted_at": None,
        },
    )
    return record, created


def update_attendance_record(record, data):
    branch = (data.get("branch") or "").strip() or None
    if "seller_id" in data:
        seller = get_active_seller(data.get("seller_id"), branch=branch)
        if seller is None:
            raise ValueError("Seller not found for this branch")
        record.seller = seller
    if "status" in data:
        record.status = data["status"]
    if "notes" in data:
        record.notes = (data.get("notes") or "").strip()
    if "date" in data:
        day = django_parse_date(data["date"])
        if day:
            record.date = day
    record.save()
    return record


def soft_delete_attendance(record):
    record.soft_delete()
    return record


def check_in(seller, user, day=None, status="present", work_branch="", notes=""):
    day = day or timezone.localdate()
    work_branch = (work_branch or seller.branch_id).strip()

    record = StaffAttendance.objects.filter(seller=seller, date=day).first()
    if record:
        apply_auto_checkout(record)
        record.refresh_from_db()
        if record.check_out_at:
            raise ValueError("امروز کار شما به پایان رسیده است.")
        if record.check_in_at and record.approval_status != "rejected":
            raise ValueError("حضور امروز قبلاً ثبت شده است.")

    now = timezone.now()
    record, created = StaffAttendance.objects.update_or_create(
        seller=seller,
        date=day,
        defaults={
            "status": status or "present",
            "work_branch_id": work_branch,
            "approval_status": "pending",
            "notes": (notes or "").strip(),
            "recorded_by": user,
            "approved_by": None,
            "approved_at": None,
            "check_in_at": now,
            "check_out_at": None,
            "is_deleted": False,
            "deleted_at": None,
        },
    )
    return record, created


def check_out(seller):
    record = today_record_for_seller(seller)
    if record is None or not record.check_in_at:
        raise ValueError("ابتدا حضور خود را ثبت کنید.")
    if record.check_out_at:
        raise ValueError("پایان کار قبلاً ثبت شده است.")
    if record.approval_status != "approved":
        raise ValueError("حضور شما هنوز توسط مدیر تایید نشده است.")

    record.check_out_at = timezone.now()
    record.save(update_fields=["check_out_at"])
    return record


def today_status_for_seller(seller):
    record = today_record_for_seller(seller)
    can_check_in = record is None or (
        not record.check_out_at and record.approval_status == "rejected"
    )
    can_check_out = bool(
        record
        and record.check_in_at
        and not record.check_out_at
        and record.approval_status == "approved"
    )
    return {
        "record": attendance_to_dict(record) if record else None,
        "can_check_in": can_check_in,
        "can_check_out": can_check_out,
    }


def decide_attendance(record, user, decision="approved"):
    if decision not in ("approved", "rejected"):
        raise ValueError("Invalid decision")
    record.approval_status = decision
    record.approved_by = user
    record.approved_at = timezone.now()
    record.save()
    return record
