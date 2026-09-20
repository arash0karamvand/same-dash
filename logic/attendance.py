"""منطق حضور و غیاب — ورود، خروج، خروج خودکار ۱۶ ساعته، CRUD مدیر."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date as django_parse_date

from auth.branches import BRANCH_LABELS
from backend.models import Seller, StaffAttendance

AUTO_CHECKOUT_HOURS = 16


def _decimal_or_none(value):
    if value is None:
        return None
    return float(value)


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
        "leave_pay_type": record.leave_pay_type or "",
        "leave_hours": _decimal_or_none(record.leave_hours),
        "mission_dest_kind": record.mission_dest_kind or "",
        "mission_dest_code": record.mission_dest_code or "",
        "mission_dest_label": record.mission_dest_label or "",
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


def today_records_for_seller(seller, day=None):
    day = day or timezone.localdate()
    rows = list(
        StaffAttendance.objects.filter(seller=seller, date=day, is_deleted=False)
        .select_related("seller", "approved_by", "work_branch")
        .order_by("check_in_at", "id")
    )
    for record in rows:
        if record.status == "present":
            apply_auto_checkout(record)
    return rows


def today_leave_record(seller, day=None):
    """مرخصی تمام‌روز — مرخصی ساعتی ورود و فروش را نمی‌بندد."""
    if seller is None:
        return None
    return (
        StaffAttendance.objects.filter(
            seller=seller,
            date=day or timezone.localdate(),
            status_ref_id="leave",
            leave_hours__isnull=True,
            is_deleted=False,
        )
        .order_by("-id")
        .first()
    )


def today_hourly_leave_record(seller, day=None):
    if seller is None:
        return None
    return (
        StaffAttendance.objects.filter(
            seller=seller,
            date=day or timezone.localdate(),
            status_ref_id="leave",
            leave_hours__isnull=False,
            is_deleted=False,
        )
        .order_by("-id")
        .first()
    )


def today_mission_record(seller, day=None):
    if seller is None:
        return None
    return (
        StaffAttendance.objects.filter(
            seller=seller,
            date=day or timezone.localdate(),
            status_ref_id="mission",
            is_deleted=False,
        )
        .order_by("-id")
        .first()
    )


def is_blocking_mission(record):
    if record is None:
        return False
    return (record.mission_dest_kind or "") != StaffAttendance.MISSION_DEST_BRANCH


def open_present_record_for_seller(seller, day=None):
    """Return the seller's open present session, if any. `day` is unused; at most one session can be open."""
    if seller is None:
        return None
    record = (
        StaffAttendance.objects.filter(
            seller=seller,
            status_ref_id="present",
            check_out_at__isnull=True,
            is_deleted=False,
        )
        .select_related("seller", "approved_by", "work_branch")
        .order_by("-check_in_at", "-id")
        .first()
    )
    if record:
        apply_auto_checkout(record)
        record.refresh_from_db()
        if record.check_out_at:
            return None
    return record


def today_record_for_seller(seller):
    open_record = open_present_record_for_seller(seller)
    if open_record:
        return open_record
    leave = today_leave_record(seller)
    if leave:
        return leave
    mission = today_mission_record(seller)
    if mission:
        return mission
    day = timezone.localdate()
    record = (
        StaffAttendance.objects.filter(seller=seller, date=day, is_deleted=False)
        .select_related("seller", "approved_by", "work_branch")
        .order_by("-check_in_at", "-id")
        .first()
    )
    if record and record.status == "present":
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


def upsert_manager_attendance(
    seller,
    day,
    status,
    user,
    branch=None,
    notes="",
    *,
    leave_pay_type="",
    leave_hours=None,
    mission_dest_kind="",
    mission_dest_code="",
    mission_dest_label="",
):
    if status not in ("present", "absent", "leave", "mission"):
        raise ValueError("Invalid status")
    work_branch = branch or seller.branch_id
    extras = {
        "leave_pay_type": (leave_pay_type or "") if status == "leave" else "",
        "leave_hours": leave_hours if status == "leave" else None,
        "mission_dest_kind": (mission_dest_kind or "") if status == "mission" else "",
        "mission_dest_code": (mission_dest_code or "") if status == "mission" else "",
        "mission_dest_label": (mission_dest_label or "") if status == "mission" else "",
    }
    hourly_leave = status == "leave" and leave_hours is not None
    if status in ("absent", "leave", "mission") and not hourly_leave:
        open_record = open_present_record_for_seller(seller, day=day)
        if open_record:
            open_record.check_out_at = timezone.now()
            open_record.save(update_fields=["check_out_at"])
        record = (
            StaffAttendance.objects.filter(
                seller=seller, date=day, status_ref_id=status, is_deleted=False
            )
            .order_by("-id")
            .first()
        )
        if record:
            record.work_branch_id = work_branch
            record.notes = (notes or "").strip()
            record.approval_status = "approved"
            record.recorded_by = user
            record.approved_by = user
            record.approved_at = timezone.now()
            for key, value in extras.items():
                setattr(record, key, value)
            record.save()
            return record, False
        record = StaffAttendance.objects.create(
            seller=seller,
            date=day,
            status=status,
            work_branch_id=work_branch,
            approval_status="approved",
            notes=(notes or "").strip(),
            recorded_by=user,
            approved_by=user,
            approved_at=timezone.now(),
            **extras,
        )
        return record, True

    if hourly_leave:
        record = (
            StaffAttendance.objects.filter(
                seller=seller, date=day, status_ref_id="leave", is_deleted=False
            )
            .order_by("-id")
            .first()
        )
        if record:
            record.work_branch_id = work_branch
            record.notes = (notes or "").strip()
            record.approval_status = "approved"
            record.recorded_by = user
            record.approved_by = user
            record.approved_at = timezone.now()
            for key, value in extras.items():
                setattr(record, key, value)
            record.save()
            return record, False
        record = StaffAttendance.objects.create(
            seller=seller,
            date=day,
            status=status,
            work_branch_id=work_branch,
            approval_status="approved",
            notes=(notes or "").strip(),
            recorded_by=user,
            approved_by=user,
            approved_at=timezone.now(),
            **extras,
        )
        return record, True

    record = open_present_record_for_seller(seller, day=day)
    defaults = {
        "status": status,
        "work_branch_id": work_branch,
        "approval_status": "approved",
        "notes": (notes or "").strip(),
        "recorded_by": user,
        "approved_by": user,
        "approved_at": timezone.now(),
        "is_deleted": False,
        "deleted_at": None,
    }
    if record:
        for key, value in defaults.items():
            setattr(record, key, value)
        record.save()
        return record, False
    record = StaffAttendance.objects.create(
        seller=seller,
        date=day,
        check_in_at=timezone.now(),
        **{k: v for k, v in defaults.items() if k not in ("is_deleted", "deleted_at")},
    )
    return record, True


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
    status = status or "present"
    if today_leave_record(seller, day=day):
        raise ValueError("شما امروز مرخصی هستید.")
    mission = today_mission_record(seller, day=day)
    if is_blocking_mission(mission):
        dest = (mission.mission_dest_label or "").strip()
        suffix = f" — {dest}" if dest else ""
        raise ValueError(f"شما امروز در ماموریت هستید{suffix}.")

    open_record = open_present_record_for_seller(seller, day=day)
    if open_record:
        if open_record.approval_status == "rejected":
            now = timezone.now()
            open_record.status = status
            open_record.work_branch_id = work_branch
            open_record.approval_status = "pending"
            open_record.notes = (notes or "").strip()
            open_record.recorded_by = user
            open_record.approved_by = None
            open_record.approved_at = None
            open_record.check_in_at = now
            open_record.check_out_at = None
            open_record.save()
            return open_record, False
        raise ValueError("حضور امروز قبلاً ثبت شده است.")

    now = timezone.now()
    record = StaffAttendance.objects.create(
        seller=seller,
        date=day,
        status=status,
        work_branch_id=work_branch,
        approval_status="pending",
        notes=(notes or "").strip(),
        recorded_by=user,
        check_in_at=now,
        check_out_at=None,
    )
    return record, True


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
    from logic.branches import get_active_branches

    record = today_record_for_seller(seller)
    open_record = open_present_record_for_seller(seller)
    leave = today_leave_record(seller)
    hourly = today_hourly_leave_record(seller)
    mission = today_mission_record(seller)
    blocking_mission = is_blocking_mission(mission)
    can_check_in = leave is None and not blocking_mission and (
        open_record is None or open_record.approval_status == "rejected"
    )
    can_check_out = bool(
        open_record
        and open_record.check_in_at
        and not open_record.check_out_at
        and open_record.approval_status == "approved"
    )
    current_branch = (open_record.work_branch_id if open_record else "") or seller.branch_id
    switch_options = [
        {"value": b["code"], "label": b["label"]}
        for b in get_active_branches()
        if b["code"] != current_branch
    ]
    display = record
    if leave:
        display = leave
    elif mission and not open_record:
        display = mission
    return {
        "record": attendance_to_dict(display) if display else None,
        "can_check_in": can_check_in,
        "can_check_out": can_check_out,
        "can_request_branch_switch": bool(can_check_out and switch_options),
        "switch_branch_options": switch_options,
        "on_leave": leave is not None,
        "on_hourly_leave": hourly is not None,
        "hourly_leave_hours": _decimal_or_none(hourly.leave_hours) if hourly else None,
        "on_mission": mission is not None,
        "mission_dest_kind": (mission.mission_dest_kind if mission else "") or "",
        "mission_dest_label": (mission.mission_dest_label if mission else "") or "",
    }


@transaction.atomic
def request_branch_switch(seller, user, to_branch):
    from backend.models import Notification
    from logic.notifications import notify_branch_switch_request

    to_branch = (to_branch or "").strip()
    record = open_present_record_for_seller(seller)
    if record is None or not record.check_in_at or record.check_out_at:
        raise ValueError("ابتدا حضور فعال خود را ثبت کنید.")
    record = StaffAttendance.objects.select_for_update().get(pk=record.pk)
    if record.approval_status != "approved":
        raise ValueError("حضور شما هنوز توسط مدیر تایید نشده است.")
    current = record.work_branch_id or seller.branch_id
    if not to_branch or to_branch == current:
        raise ValueError("شعبه مقصد را متفاوت از شعبه فعلی انتخاب کنید.")
    from logic.branches import branch_labels

    if to_branch not in branch_labels():
        raise ValueError("شعبه مقصد نامعتبر است.")
    if Notification.objects.filter(
        action_type=Notification.ACTION_BRANCH_SWITCH,
        resolved_at__isnull=True,
        payload__attendance_id=record.pk,
    ).exists():
        raise ValueError("برای این نشست، درخواست تغییر شعبه در انتظار تأیید است.")
    notification = notify_branch_switch_request(seller, current, to_branch, record, user)
    return notification, record


@transaction.atomic
def approve_branch_switch(notification, user):
    notification = notification.__class__.objects.select_for_update().get(pk=notification.pk)
    payload = dict(notification.payload or {})
    if notification.action_type != notification.ACTION_BRANCH_SWITCH:
        raise ValueError("این اعلان تغییر شعبه نیست.")
    if notification.resolved_at or payload.get("status") == "approved":
        raise ValueError("این درخواست قبلاً انجام شده است.")
    seller = get_active_seller(payload.get("seller_id"))
    if seller is None:
        raise ValueError("فروشنده یافت نشد.")
    to_branch = (payload.get("to_branch") or "").strip()
    attendance_id = payload.get("attendance_id")
    record = StaffAttendance.objects.select_for_update().filter(
        pk=attendance_id, seller=seller
    ).first()
    if record is None:
        record = open_present_record_for_seller(seller)
    if record is None:
        raise ValueError("نشست حضور فعال یافت نشد.")
    if record.check_out_at:
        raise ValueError("نشست مبدأ قبلاً بسته شده است.")
    if not record.check_out_at:
        record.check_out_at = timezone.now()
        record.save(update_fields=["check_out_at"])
    now = timezone.now()
    new_record = StaffAttendance.objects.create(
        seller=seller,
        date=record.date,
        status="present",
        work_branch_id=to_branch,
        approval_status="approved",
        notes=f"ادامه ساعت کاری از شعبه {record.work_branch_id or seller.branch_id}",
        recorded_by=user,
        approved_by=user,
        approved_at=now,
        check_in_at=now,
        check_out_at=None,
    )
    payload["status"] = "approved"
    payload["new_attendance_id"] = new_record.id
    notification.payload = payload
    notification.resolved_at = now
    notification.resolved_by = user
    notification.save(update_fields=["payload", "resolved_at", "resolved_by"])
    return new_record


def decide_attendance(record, user, decision="approved"):
    if decision not in ("approved", "rejected"):
        raise ValueError("Invalid decision")
    record.approval_status = decision
    record.approved_by = user
    record.approved_at = timezone.now()
    record.save()
    return record
