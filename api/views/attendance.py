"""CRUD حضور و غیاب — فقط مدیر؛ ثبت خودکار فروشنده با تایید."""

from django.utils import timezone

from api.filters import apply_attendance_filters
from api.helpers import api_view, fail, parse_json, success
from api.serializers import attendance_to_dict
from auth.permissions import MANAGE_ATTENDANCE, SELF_CHECK_IN, VIEW_ATTENDANCE, has_permission
from backend.models import Seller, StaffAttendance
from django.utils.dateparse import parse_date as django_parse_date
from logic.audit import log_action
from logic.attendance import apply_auto_checkout, today_record_for_seller
from logic.sellers import get_seller_for_user


def _get_record(pk):
    try:
        return StaffAttendance.objects.select_related("seller", "recorded_by", "approved_by").get(pk=pk)
    except StaffAttendance.DoesNotExist:
        return None


def _get_seller(pk, branch=None):
    try:
        seller = Seller.objects.get(pk=pk, is_active=True)
    except Seller.DoesNotExist:
        return None
    if branch and seller.branch != branch:
        return None
    return seller


@api_view("GET", "POST")
def attendance_list(request):
    if request.method == "GET":
        if not has_permission(request.user, VIEW_ATTENDANCE):
            return fail("Permission denied", status=403)
        qs = StaffAttendance.objects.select_related("seller", "recorded_by", "approved_by").all()
        qs = apply_attendance_filters(qs, request.GET)
        return success({"results": [attendance_to_dict(r) for r in qs]})

    if not has_permission(request.user, MANAGE_ATTENDANCE):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    branch = (data.get("branch") or "").strip() or None
    seller = _get_seller(data.get("seller_id"), branch=branch)
    if seller is None:
        return fail("Seller not found for this branch", status=404)

    day = django_parse_date(data.get("date") or "")
    if not day:
        return fail("date is required", status=400)

    status = data.get("status") or "present"
    if status not in ("present", "absent"):
        return fail("Invalid status", status=400)

    record, created = StaffAttendance.objects.update_or_create(
        seller=seller,
        date=day,
        defaults={
            "status": status,
            "work_branch": branch or seller.branch,
            "approval_status": "approved",
            "notes": (data.get("notes") or "").strip(),
            "recorded_by": request.user,
            "approved_by": request.user,
            "approved_at": timezone.now(),
            "is_deleted": False,
            "deleted_at": None,
        },
    )
    log_action(
        request.user,
        "create" if created else "update",
        f"حضور {seller.full_name} — {day}",
        entity_type="StaffAttendance",
        entity_id=record.id,
    )
    return success(attendance_to_dict(record), status=201 if created else 200)


@api_view("GET", "PUT", "DELETE")
def attendance_detail(request, pk):
    record = _get_record(pk)
    if record is None:
        return fail("Record not found", status=404)

    if request.method == "GET":
        if not has_permission(request.user, VIEW_ATTENDANCE):
            return fail("Permission denied", status=403)
        return success(attendance_to_dict(record))

    if not has_permission(request.user, MANAGE_ATTENDANCE):
        return fail("Permission denied", status=403)

    if request.method == "DELETE":
        record.soft_delete()
        log_action(request.user, "delete", f"حذف حضور {record.seller.full_name}", entity_type="StaffAttendance", entity_id=record.id)
        return success({"deleted": True})

    data = parse_json(request)
    branch = (data.get("branch") or "").strip() or None
    if "seller_id" in data:
        seller = _get_seller(data.get("seller_id"), branch=branch)
        if seller is None:
            return fail("Seller not found for this branch", status=404)
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
    log_action(request.user, "update", f"ویرایش حضور {record.seller.full_name}", entity_type="StaffAttendance", entity_id=record.id)
    return success(attendance_to_dict(record))


@api_view("POST")
def attendance_check_in(request):
    if not has_permission(request.user, SELF_CHECK_IN):
        return fail("Permission denied", status=403)

    seller = get_seller_for_user(request.user)
    if seller is None:
        return fail("پروفایل فروشنده یافت نشد. از مدیر بخواهید شعبه و نقش شما را تنظیم کند.", status=404)

    data = parse_json(request)
    day = django_parse_date(data.get("date") or "") or timezone.localdate()
    status = data.get("status") or "present"
    work_branch = (data.get("work_branch") or seller.branch).strip()

    record = StaffAttendance.objects.filter(seller=seller, date=day).first()
    if record:
        apply_auto_checkout(record)
        record.refresh_from_db()
        if record.check_out_at:
            return fail("امروز کار شما به پایان رسیده است.", status=400)
        if record.check_in_at and record.approval_status != "rejected":
            return fail("حضور امروز قبلاً ثبت شده است.", status=400)

    now = timezone.now()
    record, created = StaffAttendance.objects.update_or_create(
        seller=seller,
        date=day,
        defaults={
            "status": status,
            "work_branch": work_branch,
            "approval_status": "pending",
            "notes": (data.get("notes") or "").strip(),
            "recorded_by": request.user,
            "approved_by": None,
            "approved_at": None,
            "check_in_at": now,
            "check_out_at": None,
            "is_deleted": False,
            "deleted_at": None,
        },
    )
    log_action(
        request.user,
        "check_in",
        f"درخواست حضور {seller.full_name} — {day}",
        entity_type="StaffAttendance",
        entity_id=record.id,
    )
    return success(attendance_to_dict(record), status=201 if created else 200)


@api_view("POST")
def attendance_check_out(request):
    if not has_permission(request.user, SELF_CHECK_IN):
        return fail("Permission denied", status=403)

    seller = get_seller_for_user(request.user)
    if seller is None:
        return fail("پروفایل فروشنده یافت نشد. از مدیر بخواهید شعبه و نقش شما را تنظیم کند.", status=404)

    day = timezone.localdate()
    record = today_record_for_seller(seller)
    if record is None or not record.check_in_at:
        return fail("ابتدا حضور خود را ثبت کنید.", status=400)
    if record.check_out_at:
        return fail("پایان کار قبلاً ثبت شده است.", status=400)
    if record.approval_status != "approved":
        return fail("حضور شما هنوز توسط مدیر تایید نشده است.", status=400)

    record.check_out_at = timezone.now()
    record.save(update_fields=["check_out_at"])
    log_action(
        request.user,
        "check_out",
        f"پایان کار {seller.full_name} — {day}",
        entity_type="StaffAttendance",
        entity_id=record.id,
    )
    return success(attendance_to_dict(record))


@api_view("GET")
def attendance_today(request):
    if not has_permission(request.user, SELF_CHECK_IN):
        return fail("Permission denied", status=403)

    seller = get_seller_for_user(request.user)
    if seller is None:
        return fail("پروفایل فروشنده یافت نشد. از مدیر بخواهید شعبه و نقش شما را تنظیم کند.", status=404)

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
    return success(
        {
            "record": attendance_to_dict(record) if record else None,
            "can_check_in": can_check_in,
            "can_check_out": can_check_out,
        }
    )


@api_view("POST")
def attendance_approve(request, pk):
    if not has_permission(request.user, MANAGE_ATTENDANCE):
        return fail("Permission denied", status=403)

    record = _get_record(pk)
    if record is None:
        return fail("Record not found", status=404)

    data = parse_json(request)
    decision = data.get("decision") or "approved"
    if decision not in ("approved", "rejected"):
        return fail("Invalid decision", status=400)

    record.approval_status = decision
    record.approved_by = request.user
    record.approved_at = timezone.now()
    record.save()
    log_action(
        request.user,
        "approve" if decision == "approved" else "reject",
        f"{'تایید' if decision == 'approved' else 'رد'} حضور {record.seller.full_name}",
        entity_type="StaffAttendance",
        entity_id=record.id,
        is_executive_only=decision == "rejected",
    )
    return success(attendance_to_dict(record))
