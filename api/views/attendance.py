"""CRUD حضور و غیاب — فقط مدیر؛ ثبت خودکار فروشنده با تایید."""

from django.utils import timezone
from django.utils.dateparse import parse_date as django_parse_date

from api.filters import apply_attendance_filters
from api.helpers import api_view, fail, parse_json, success
from api.serializers import attendance_to_dict
from auth.permissions import MANAGE_ATTENDANCE, SELF_CHECK_IN, VIEW_ATTENDANCE, has_permission
from logic.audit import log_action
from logic.attendance import (
    check_in,
    check_out,
    decide_attendance,
    get_active_seller,
    get_record,
    list_attendance_base_qs,
    request_branch_switch,
    soft_delete_attendance,
    today_status_for_seller,
    update_attendance_record,
    upsert_manager_attendance,
)
from logic.sale_attendance import evaluate_sale_attendance
from logic.sellers import get_seller_for_user


@api_view("GET", "POST")
def attendance_list(request):
    if request.method == "GET":
        if not has_permission(request.user, VIEW_ATTENDANCE):
            return fail("Permission denied", status=403)
        from logic.pagination import paginate

        qs = apply_attendance_filters(list_attendance_base_qs(), request.GET)
        page, meta = paginate(qs, request.GET)
        return success({"results": [attendance_to_dict(r) for r in page], **meta})

    if not has_permission(request.user, MANAGE_ATTENDANCE):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    branch = (data.get("branch") or "").strip() or None
    seller = get_active_seller(data.get("seller_id"), branch=branch)
    if seller is None:
        return fail("Seller not found for this branch", status=404)

    day = django_parse_date(data.get("date") or "")
    if not day:
        return fail("date is required", status=400)

    try:
        record, created = upsert_manager_attendance(
            seller,
            day,
            data.get("status") or "present",
            request.user,
            branch=branch,
            notes=data.get("notes") or "",
        )
    except ValueError as exc:
        return fail(str(exc), status=400)

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
    record = get_record(pk)
    if record is None:
        return fail("Record not found", status=404)

    if request.method == "GET":
        if not has_permission(request.user, VIEW_ATTENDANCE):
            return fail("Permission denied", status=403)
        return success(attendance_to_dict(record))

    if not has_permission(request.user, MANAGE_ATTENDANCE):
        return fail("Permission denied", status=403)

    if request.method == "DELETE":
        soft_delete_attendance(record)
        log_action(
            request.user,
            "delete",
            f"حذف حضور {record.seller.full_name}",
            entity_type="StaffAttendance",
            entity_id=record.id,
        )
        return success({"deleted": True})

    data = parse_json(request)
    try:
        record = update_attendance_record(record, data)
    except ValueError as exc:
        return fail(str(exc), status=404 if "Seller" in str(exc) else 400)

    log_action(
        request.user,
        "update",
        f"ویرایش حضور {record.seller.full_name}",
        entity_type="StaffAttendance",
        entity_id=record.id,
    )
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
    try:
        record, created = check_in(
            seller,
            request.user,
            day=day,
            status=data.get("status") or "present",
            work_branch=data.get("work_branch") or "",
            notes=data.get("notes") or "",
        )
    except ValueError as exc:
        return fail(str(exc), status=400)

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
    try:
        record = check_out(seller)
    except ValueError as exc:
        return fail(str(exc), status=400)

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

    return success(today_status_for_seller(seller))


@api_view("GET")
def attendance_sale_gate(request):
    if not request.user.is_authenticated:
        return fail("Unauthorized", status=401)
    return success(evaluate_sale_attendance(request.user, requested_branch=request.GET.get("branch") or ""))


@api_view("POST")
def attendance_request_branch_switch(request):
    if not has_permission(request.user, SELF_CHECK_IN):
        return fail("Permission denied", status=403)
    seller = get_seller_for_user(request.user)
    if seller is None:
        return fail("پروفایل فروشنده یافت نشد. از مدیر بخواهید شعبه و نقش شما را تنظیم کند.", status=404)
    data = parse_json(request)
    try:
        notification, record = request_branch_switch(seller, request.user, data.get("to_branch") or "")
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "update",
        f"درخواست تغییر شعبه {seller.full_name}",
        entity_type="StaffAttendance",
        entity_id=record.id,
    )
    return success({"notification_id": notification.id, "record": attendance_to_dict(record)})


@api_view("POST")
def attendance_approve(request, pk):
    if not has_permission(request.user, MANAGE_ATTENDANCE):
        return fail("Permission denied", status=403)

    record = get_record(pk)
    if record is None:
        return fail("Record not found", status=404)

    data = parse_json(request)
    decision = data.get("decision") or "approved"
    try:
        record = decide_attendance(record, request.user, decision=decision)
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "approve" if decision == "approved" else "reject",
        f"{'تایید' if decision == 'approved' else 'رد'} حضور {record.seller.full_name}",
        entity_type="StaffAttendance",
        entity_id=record.id,
        is_executive_only=decision == "rejected",
    )
    return success(attendance_to_dict(record))
