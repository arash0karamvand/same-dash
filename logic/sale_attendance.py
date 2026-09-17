"""گیت حضور برای ثبت سفارش."""

from datetime import datetime

from django.utils import timezone

from auth.org_roles import is_branch_supervisor, is_executive_user, is_shop_staff_user
from logic.attendance import apply_auto_checkout, open_present_record_for_seller, today_leave_record
from logic.attendance_settings import is_attendance_enforced
from logic.sellers import get_seller_for_user


def attendance_optional_for_user(user):
    return is_executive_user(user) or is_branch_supervisor(user)


def _branch_hours_ok(branch):
    if branch is None:
        return True
    start = getattr(branch, "work_start", None)
    end = getattr(branch, "work_end", None)
    if start is None and end is None:
        return True
    now = timezone.localtime().time()
    if start and now < start:
        return False
    if end and now > end:
        return False
    return True


def evaluate_sale_attendance(user, *, requested_branch=""):
    """خروجی برای UI و سرور: آیا ثبت سفارش مجاز است و شعبه را چه کسی انتخاب می‌کند."""
    enforced = is_attendance_enforced()
    manager = attendance_optional_for_user(user)
    seller = get_seller_for_user(user)
    leave = today_leave_record(seller) if seller else None
    present = open_present_record_for_seller(seller) if seller else None
    if present:
        apply_auto_checkout(present)
        present.refresh_from_db()
        if present.check_out_at:
            present = None

    work_branch = ""
    if present and not present.check_out_at:
        work_branch = present.work_branch_id or (seller.branch_id if seller else "")

    blocked = False
    reason = ""
    if enforced and leave is not None:
        blocked = True
        reason = "شما امروز مرخصی هستید و نمی‌توانید سفارش ثبت کنید."
    elif enforced and not manager and is_shop_staff_user(user):
        if present is None:
            blocked = True
            reason = "برای ثبت سفارش ابتدا حضور خود را ثبت کنید."
        elif present.approval_status != "approved":
            blocked = True
            reason = "حضور شما هنوز توسط مدیر تأیید نشده است."
        elif present.check_out_at:
            blocked = True
            reason = "ساعت کاری شما به پایان رسیده است."
        elif present.work_branch and not _branch_hours_ok(present.work_branch):
            blocked = True
            reason = "ساعت کاری شعبه به پایان رسیده است."

    if not enforced:
        must_pick_branch = True
    elif present and not present.check_out_at:
        must_pick_branch = False
    else:
        must_pick_branch = manager

    return {
        "enforced": enforced,
        "manager_exempt": manager,
        "blocked": blocked,
        "reason": reason,
        "must_pick_branch": must_pick_branch and not blocked,
        "work_branch": work_branch or "",
        "present": bool(present and not present.check_out_at),
        "on_leave": leave is not None,
    }


def assert_user_can_record_sale(user):
    state = evaluate_sale_attendance(user)
    if state["blocked"]:
        raise ValueError(state["reason"])
    return state


def format_time(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.time()
    return value.strftime("%H:%M")
