"""اعلان‌های درون‌برنامه‌ای — ایجاد، فیلتر بر اساس دسترسی، خواندن و اقدام."""

from datetime import date as date_cls, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import FieldError
from django.db import transaction
from django.utils import timezone

from auth import roles
from auth.permissions import MANAGE_ATTENDANCE, can_view_sale, has_permission, is_system_admin
from backend.models import Notification, NotificationReceipt, Sale, TicketMessage
from logic.departments import DEPARTMENT_LABELS, DEPARTMENTS, department_label, normalize_department, users_in_department
from logic.module_catalog import PORTAL_MODULE_SPECS
from logic.ticket_grades import get_ticket_grades, grade_color

SECTION_LABELS = dict(Notification.SECTION_CHOICES)

ORG_ACTION_TYPES = (
    Notification.ACTION_ORG_TICKET,
    Notification.ACTION_ORG_RESPONSIBILITY,
)

DISPATCH_ACTION_TYPES = (
    Notification.ACTION_ORG_LEAVE,
    Notification.ACTION_ORG_MISSION,
)

SENT_ACTION_TYPES = ORG_ACTION_TYPES + DISPATCH_ACTION_TYPES

MAX_DISPATCH_DAYS = 90
LEAVE_PAY_LABELS = {"paid": "با حقوق", "unpaid": "بدون حقوق"}
MISSION_DEST_LABELS = {
    "branch": "شعبه",
    "warehouse": "انبار",
    "factory": "کارخانه",
    "outside": "خارج از شرکت",
}

SECTION_PAGE_KEYS = {
    Notification.SECTION_ATTENDANCE: {"attendance"},
    Notification.SECTION_SALES: {"shop", "orders", "office", "office-orders"},
    Notification.SECTION_PRODUCTS: {"products"},
    Notification.SECTION_WAREHOUSE: {"warehouse"},
}

INVOICE_PICKER_LIMIT = 10
INVOICE_SCAN_CAP = 200


def notification_sections_for_user(user):
    """بخش‌هایی که کاربر در منو به آن‌ها دسترسی دارد."""
    allowed_pages = set()
    for portal in PORTAL_MODULE_SPECS:
        for mod in portal.get("modules") or []:
            codes = mod.get("menu_permissions") or []
            if not codes or any(has_permission(user, code) for code in codes):
                allowed_pages.add(mod.get("page_key"))
    sections = []
    for section, pages in SECTION_PAGE_KEYS.items():
        if pages & allowed_pages:
            sections.append({"id": section, "label": SECTION_LABELS.get(section, section)})
    if has_permission(user, MANAGE_ATTENDANCE) and not any(s["id"] == Notification.SECTION_ATTENDANCE for s in sections):
        sections.insert(0, {"id": Notification.SECTION_ATTENDANCE, "label": SECTION_LABELS[Notification.SECTION_ATTENDANCE]})
    if user and getattr(user, "is_authenticated", False) and getattr(user, "is_active", False):
        if roles.get_user_role(user) != roles.PENDING:
            if not any(s["id"] == Notification.SECTION_ORG for s in sections):
                sections.append(
                    {"id": Notification.SECTION_ORG, "label": SECTION_LABELS[Notification.SECTION_ORG]}
                )
    return sections


def users_with_permission(code):
    User = get_user_model()
    return [user for user in User.objects.filter(is_active=True) if has_permission(user, code)]


@transaction.atomic
def create_notification(
    *,
    section,
    title,
    body="",
    action_type="",
    payload=None,
    target_permission="",
    created_by=None,
    recipients=None,
):
    notification = Notification.objects.create(
        section=section,
        title=title,
        body=body or "",
        action_type=action_type or "",
        payload=payload or {},
        target_permission=target_permission or "",
        created_by=created_by,
    )
    users = recipients
    if users is None and target_permission:
        users = users_with_permission(target_permission)
    receipts = []
    for user in users or []:
        receipts.append(NotificationReceipt(notification=notification, user=user))
    if receipts:
        NotificationReceipt.objects.bulk_create(receipts, ignore_conflicts=True)
    return notification


def receipt_queryset(user):
    allowed = {item["id"] for item in notification_sections_for_user(user)}
    qs = NotificationReceipt.objects.filter(user=user).select_related("notification", "notification__created_by")
    if allowed:
        qs = qs.filter(notification__section__in=allowed)
    else:
        qs = qs.none()
    return qs.order_by("-notification__created_at", "-id")


def sent_queryset(user):
    return (
        Notification.objects.filter(
            created_by=user,
            action_type__in=SENT_ACTION_TYPES,
        )
        .select_related("created_by")
        .order_by("-created_at", "-id")
    )


def all_threads_queryset(user):
    if not is_system_admin(user):
        return Notification.objects.none()
    return (
        Notification.objects.filter(action_type__in=SENT_ACTION_TYPES)
        .select_related("created_by")
        .order_by("-created_at", "-id")
    )


def unread_count(user):
    return receipt_queryset(user).filter(is_read=False).count()


def mark_read(receipt, *, read=True):
    receipt.is_read = bool(read)
    receipt.read_at = timezone.now() if read else None
    receipt.save(update_fields=["is_read", "read_at"])
    return receipt


def _user_display(user):
    if not user:
        return ""
    return user.get_full_name() or user.username


def _sale_amount(sale):
    value = sale.final_amount if sale.final_amount is not None else sale.amount
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    return int(value)


def _payload_user_id(payload, *keys):
    payload = payload or {}
    for key in keys:
        raw = payload.get(key)
        if raw in (None, ""):
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def _holder_name(payload):
    payload = payload or {}
    name = (payload.get("claimed_by_name") or payload.get("to_name") or "").strip()
    if name:
        return name
    department = payload.get("to_department") or ""
    if department:
        return DEPARTMENT_LABELS.get(department, department)
    return ""


def thread_parties_label(note):
    payload = note.payload or {}
    sender = payload.get("from_name") or _user_display(note.created_by)
    holder = _holder_name(payload)
    if sender and holder:
        return f"{sender} ↔ {holder}"
    return sender or holder


def _ticket_flags(note, user):
    payload = note.payload or {}
    is_ticket = note.action_type == Notification.ACTION_ORG_TICKET
    is_sender = bool(note.created_by_id and note.created_by_id == user.id)
    holder_id = _payload_user_id(payload, "claimed_by_id", "to_user_id")
    is_holder = holder_id == user.id
    status = (payload.get("status") or "open").strip() or "open"
    party = is_sender or is_holder
    return {
        "status": status,
        "can_close": is_ticket and party and status != "closed",
        "can_reopen": is_ticket and party and status == "closed",
        "can_reply": is_ticket and party and status != "closed",
        "can_set_early_ship_date": bool(
            is_ticket
            and payload.get("purpose") == "early_ship_disposition"
            and status != "closed"
            and is_holder
        ),
        "is_party": party,
        "is_admin_view": is_system_admin(user) and not party,
    }


def receipt_to_dict(receipt, user=None):
    note = receipt.notification
    actor = user or receipt.user
    flags = _ticket_flags(note, actor) if note.action_type in ORG_ACTION_TYPES else {}
    payload = note.payload or {}
    return {
        "id": receipt.id,
        "notification_id": note.id,
        "section": note.section,
        "section_label": SECTION_LABELS.get(note.section, note.section),
        "title": note.title,
        "body": note.body,
        "action_type": note.action_type,
        "payload": payload,
        "is_read": receipt.is_read,
        "read_at": receipt.read_at.isoformat() if receipt.read_at else None,
        "resolved": bool(note.resolved_at),
        "resolved_at": note.resolved_at.isoformat() if note.resolved_at else None,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "created_by": _user_display(note.created_by),
        "box": "inbox",
        "parties": thread_parties_label(note) if note.action_type in ORG_ACTION_TYPES else "",
        "sale_id": payload.get("sale_id"),
        "invoice_number": payload.get("invoice_number") or "",
        "customer_name": payload.get("customer_name") or "",
        **flags,
    }


def notification_to_dict(note, user, *, box="sent", include_messages=False):
    payload = note.payload or {}
    flags = _ticket_flags(note, user) if note.action_type in ORG_ACTION_TYPES else {}
    data = {
        "id": note.id,
        "notification_id": note.id,
        "section": note.section,
        "section_label": SECTION_LABELS.get(note.section, note.section),
        "title": note.title,
        "body": note.body,
        "action_type": note.action_type,
        "payload": payload,
        "is_read": True,
        "read_at": None,
        "resolved": bool(note.resolved_at),
        "resolved_at": note.resolved_at.isoformat() if note.resolved_at else None,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "created_by": _user_display(note.created_by),
        "box": box,
        "parties": thread_parties_label(note),
        "sale_id": payload.get("sale_id"),
        "invoice_number": payload.get("invoice_number") or "",
        "customer_name": payload.get("customer_name") or "",
        **flags,
    }
    if include_messages:
        data["messages"] = thread_messages(note)
    return data


def thread_messages(note):
    sender_name = (note.payload or {}).get("from_name") or _user_display(note.created_by)
    rows = [
        {
            "id": None,
            "author_name": sender_name,
            "author_id": note.created_by_id,
            "body": note.body or "",
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "is_initial": True,
        }
    ]
    for message in note.ticket_messages.select_related("author").all():
        rows.append(
            {
                "id": message.id,
                "author_name": _user_display(message.author),
                "author_id": message.author_id,
                "body": message.body,
                "created_at": message.created_at.isoformat() if message.created_at else None,
                "is_initial": False,
            }
        )
    return rows


def notify_branch_switch_request(seller, from_branch, to_branch, attendance, requested_by):
    from logic.branches import branch_labels

    labels = branch_labels()
    from_label = labels.get(from_branch, from_branch)
    to_label = labels.get(to_branch, to_branch)
    return create_notification(
        section=Notification.SECTION_ATTENDANCE,
        title=f"تغییر شعبه کاری — {seller.full_name}",
        body=(
            f"{seller.full_name} درخواست کرده ادامه ساعت کاری امروز "
            f"از «{from_label}» به «{to_label}» منتقل شود."
        ),
        action_type=Notification.ACTION_BRANCH_SWITCH,
        payload={
            "seller_id": seller.id,
            "seller_name": seller.full_name,
            "from_branch": from_branch,
            "to_branch": to_branch,
            "attendance_id": attendance.id,
            "status": "pending",
        },
        target_permission=MANAGE_ATTENDANCE,
        created_by=requested_by,
    )


def list_message_recipients(sender):
    """کاربران فعال غیرpending به‌جز خود فرستنده."""
    from logic.departments import recipient_fields

    User = get_user_model()
    users = (
        User.objects.filter(is_active=True)
        .select_related("access_profile")
        .prefetch_related("groups")
        .exclude(pk=sender.id)
        .exclude(groups__name=roles.PENDING)
        .order_by("first_name", "last_name", "username")
    )
    results = []
    for user in users:
        fields = recipient_fields(user)
        results.append(
            {
                "id": user.id,
                "full_name": user.get_full_name() or user.username,
                **fields,
            }
        )
    return results


def list_recipient_departments():
    return [{"id": item["id"], "label": item["label"]} for item in DEPARTMENTS]


def _candidate_ticket_sales(user):
    """محدود کردن کاندیداها قبل از can_view_sale تا لود سنگین نشود."""
    from auth.org_roles import (
        is_accounting_finance,
        is_branch_supervisor,
        is_executive_user,
        is_factory_supervisor,
        is_freight_supervisor,
        sales_expert_summary_only,
    )
    from auth.permissions import (
        APPROVE_SALE_ACCOUNTING,
        APPROVE_SALE_BRANCH,
        VIEW_FACTORY_ORDERS,
        VIEW_FREIGHT_ORDERS,
    )
    from logic.sale_workflow import (
        STAGE_ACCOUNTING_APPROVED,
        STAGE_BRANCH_APPROVED,
        STAGE_IN_FREIGHT,
        STAGE_IN_PRODUCTION,
        STAGE_IN_WAREHOUSE,
        STAGE_MERCHANT_ASSIGNED,
        STAGE_PENDING_BRANCH,
        STAGE_PRODUCTION_DONE,
        STAGE_READY_FOR_PICKUP,
    )
    from logic.sellers import effective_sale_branch, get_user_branch

    qs = Sale.objects.select_related("customer").order_by("-sold_at")
    if is_executive_user(user):
        return qs
    if sales_expert_summary_only(user):
        return qs.none()
    if is_accounting_finance(user) or (
        has_permission(user, APPROVE_SALE_ACCOUNTING) and not is_executive_user(user)
    ):
        return qs.filter(
            workflow_stage_id__in=[
                STAGE_BRANCH_APPROVED,
                STAGE_ACCOUNTING_APPROVED,
                STAGE_IN_PRODUCTION,
                STAGE_PRODUCTION_DONE,
                STAGE_IN_FREIGHT,
                STAGE_IN_WAREHOUSE,
                STAGE_READY_FOR_PICKUP,
                STAGE_MERCHANT_ASSIGNED,
            ]
        )
    if is_factory_supervisor(user) or (
        has_permission(user, VIEW_FACTORY_ORDERS) and not has_permission(user, APPROVE_SALE_ACCOUNTING)
    ):
        return qs.filter(workflow_stage_id__in=[STAGE_ACCOUNTING_APPROVED, STAGE_IN_PRODUCTION])
    if is_freight_supervisor(user) or has_permission(user, VIEW_FREIGHT_ORDERS):
        return qs.filter(
            delivery_date=timezone.localdate(),
            workflow_stage_id__in=[STAGE_PRODUCTION_DONE, STAGE_IN_FREIGHT],
        )
    if is_branch_supervisor(user) or has_permission(user, APPROVE_SALE_BRANCH):
        branch = get_user_branch(user) or effective_sale_branch(user)
        if not branch:
            return qs.none()
        return qs.filter(workflow_stage_id=STAGE_PENDING_BRANCH, branch_id=branch)
    return qs.none()


def list_ticket_invoices(user, *, search="", date="", limit=INVOICE_PICKER_LIMIT):
    """فاکتورهای قابل‌مشاهده برای انتخاب روی تیکت — حداکثر ۱۰ مورد."""
    try:
        limit = int(limit or INVOICE_PICKER_LIMIT)
    except (TypeError, ValueError):
        limit = INVOICE_PICKER_LIMIT
    limit = min(max(limit, 1), INVOICE_PICKER_LIMIT)

    qs = _candidate_ticket_sales(user)
    search = (search or "").strip()
    if search:
        qs = qs.filter(invoice_number__icontains=search)
    date = (date or "").strip()
    if date:
        try:
            day = date_cls.fromisoformat(date[:10])
        except ValueError:
            return []
        from logic.sales_day import filter_sales_for_gregorian_date

        qs = filter_sales_for_gregorian_date(qs, day)

    results = []
    for sale in qs[:INVOICE_SCAN_CAP]:
        if not user_can_pick_invoice(user, sale):
            continue
        results.append(
            {
                "id": sale.id,
                "invoice_number": sale.invoice_number or str(sale.id),
                "customer_name": sale.customer.full_name if sale.customer_id else "",
                "sold_at": sale.sold_at.isoformat() if sale.sold_at else None,
                "amount": _sale_amount(sale),
            }
        )
        if len(results) >= limit:
            break
    return results


def user_can_pick_invoice(user, sale):
    """can_view_sale؛ اگر فیلتر پروکسی خطا داد، کاندیدای صف همان کاربر ملاک است."""
    try:
        return can_view_sale(user, sale)
    except (FieldError, TypeError):
        return _candidate_ticket_sales(user).filter(pk=sale.pk).exists()


def resolve_ticket_sale(user, sale_id, *, required):
    if sale_id in (None, ""):
        if required:
            raise ValueError("انتخاب فاکتور الزامی است.")
        return None
    try:
        pk = int(sale_id)
    except (TypeError, ValueError):
        raise ValueError("فاکتور نامعتبر است.") from None
    sale = Sale.objects.select_related("customer").filter(pk=pk).first()
    if not sale or not user_can_pick_invoice(user, sale):
        raise ValueError("فاکتور یافت نشد.")
    return sale


def send_org_message(
    *,
    sender,
    to_user_id=None,
    to_department=None,
    sale_id=None,
    kind="ticket",
    title="",
    body="",
    grade=None,
):
    """ارسال تیکت یا مسئولیت به فرد یا دپارتمان."""
    title = (title or "").strip()
    if not title:
        raise ValueError("عنوان را وارد کنید.")
    kind = (kind or "ticket").strip()
    if kind not in ("ticket", "responsibility"):
        raise ValueError("نوع پیام نامعتبر است.")

    has_user = to_user_id not in (None, "")
    has_department = bool((to_department or "").strip())
    if has_user and has_department:
        raise ValueError("فقط یک گیرنده انتخاب کنید.")
    if not has_user and not has_department:
        raise ValueError("گیرنده را انتخاب کنید.")

    User = get_user_model()
    target = None
    department = ""
    recipients = []
    if has_user:
        try:
            target_id = int(to_user_id)
        except (TypeError, ValueError):
            raise ValueError("گیرنده نامعتبر است.") from None
        if target_id == sender.id:
            raise ValueError("ارسال به خود مجاز نیست.")
        target = (
            User.objects.filter(pk=target_id, is_active=True)
            .exclude(groups__name=roles.PENDING)
            .first()
        )
        if not target:
            raise ValueError("گیرنده یافت نشد.")
        recipients = [target]
    else:
        department = normalize_department(to_department, allow_empty=False)
        recipients = users_in_department(department, exclude_user=sender)
        if not recipients:
            raise ValueError("در این دپارتمان گیرنده‌ای نیست.")

    sale = resolve_ticket_sale(sender, sale_id, required=(kind == "ticket"))

    settings = get_ticket_grades()
    try:
        grade_key = int(grade) if grade is not None else settings["default_grade"]
    except (TypeError, ValueError):
        grade_key = settings["default_grade"]
    allowed = {item["grade"] for item in settings["grades"]}
    if grade_key not in allowed:
        raise ValueError("درجه رنگ نامعتبر است.")
    color = grade_color(grade_key, settings)
    action = (
        Notification.ACTION_ORG_RESPONSIBILITY
        if kind == "responsibility"
        else Notification.ACTION_ORG_TICKET
    )
    sender_name = _user_display(sender)
    payload = {
        "kind": kind,
        "status": "open",
        "sale_id": sale.id if sale else None,
        "invoice_number": (sale.invoice_number or str(sale.id)) if sale else "",
        "customer_name": sale.customer.full_name if sale and sale.customer_id else "",
        "to_user_id": target.id if target else None,
        "to_name": _user_display(target) if target else "",
        "to_department": department or None,
        "claimed_by_id": None,
        "claimed_by_name": "",
        "from_user_id": sender.id,
        "from_name": sender_name,
        "grade": grade_key,
        "color": color,
    }
    return create_notification(
        section=Notification.SECTION_ORG,
        title=title[:160],
        body=(body or "").strip(),
        action_type=action,
        payload=payload,
        recipients=recipients,
        created_by=sender,
    )


def _parse_dispatch_date(value, *, field_label):
    from django.utils.dateparse import parse_date as django_parse_date

    if isinstance(value, date_cls):
        return value
    parsed = django_parse_date((value or "").strip() if isinstance(value, str) else "")
    if not parsed:
        raise ValueError(f"{field_label} را وارد کنید.")
    return parsed


def _dispatch_days(start, end):
    if end < start:
        raise ValueError("تاریخ پایان نباید قبل از شروع باشد.")
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
        if len(days) > MAX_DISPATCH_DAYS:
            raise ValueError(f"بازه نمی‌تواند بیشتر از {MAX_DISPATCH_DAYS} روز باشد.")
    return days


def _format_hours_label(hours):
    text = f"{hours:g}" if isinstance(hours, float) else str(hours)
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _resolve_mission_destination(dest_kind, dest_code, dest_label):
    from backend.models import Branch, StaffAttendance, Warehouse

    kind = (dest_kind or "").strip()
    code = (dest_code or "").strip()
    label = (dest_label or "").strip()
    if kind not in dict(StaffAttendance.MISSION_DEST_CHOICES):
        raise ValueError("مقصد ماموریت نامعتبر است.")
    if kind == StaffAttendance.MISSION_DEST_BRANCH:
        branch = Branch.objects.filter(code=code, is_active=True).first()
        if branch is None:
            raise ValueError("شعبه مقصد یافت نشد.")
        return kind, branch.code, branch.label, branch.code
    if kind == StaffAttendance.MISSION_DEST_WAREHOUSE:
        try:
            warehouse_id = int(code)
        except (TypeError, ValueError):
            raise ValueError("انبار مقصد را انتخاب کنید.") from None
        warehouse = Warehouse.objects.filter(pk=warehouse_id, is_active=True).first()
        if warehouse is None:
            raise ValueError("انبار مقصد یافت نشد.")
        return kind, str(warehouse.id), warehouse.label, None
    if kind == StaffAttendance.MISSION_DEST_FACTORY:
        return kind, "", "کارخانه", None
    if not label:
        raise ValueError("محل ماموریت خارج از شرکت را وارد کنید.")
    return kind, "", label, None


def _leave_title(*, pay_type, duration_unit, hours, days):
    pay_label = LEAVE_PAY_LABELS.get(pay_type, pay_type)
    if duration_unit == "hours":
        return f"مرخصی {pay_label} — {_format_hours_label(hours)} ساعت"
    count = len(days)
    return f"مرخصی {pay_label} — {count} روز"


def _mission_title(dest_kind, dest_label):
    if dest_kind == "outside":
        return f"ماموریت خارج از شرکت — {dest_label}"
    kind_label = MISSION_DEST_LABELS.get(dest_kind, dest_kind)
    if dest_kind == "factory":
        return "ماموریت به کارخانه"
    return f"ماموریت به {kind_label} {dest_label}".strip()


@transaction.atomic
def send_staff_dispatch(
    *,
    sender,
    to_user_id=None,
    kind="leave",
    title="",
    body="",
    pay_type="",
    duration_unit="days",
    hours=None,
    start_date=None,
    end_date=None,
    dest_kind="",
    dest_code="",
    dest_label="",
):
    """ارسال مرخصی یا ماموریت به یک فرد — فقط پورتال مدیران."""
    from logic.attendance import upsert_manager_attendance
    from logic.attendance_settings import work_day_hours
    from logic.module_catalog import can_send_leave_mission
    from logic.sellers import ensure_seller_for_user, get_seller_for_user
    from backend.models import StaffAttendance

    if not can_send_leave_mission(sender):
        raise PermissionError("فقط کاربران بخش مدیران می‌توانند مرخصی یا ماموریت ارسال کنند.")

    kind = (kind or "").strip()
    if kind not in ("leave", "mission"):
        raise ValueError("نوع پیام نامعتبر است.")
    try:
        target_id = int(to_user_id)
    except (TypeError, ValueError):
        raise ValueError("گیرنده را انتخاب کنید.") from None
    if target_id == sender.id:
        raise ValueError("ارسال به خود مجاز نیست.")

    User = get_user_model()
    target = (
        User.objects.filter(pk=target_id, is_active=True)
        .exclude(groups__name=roles.PENDING)
        .first()
    )
    if not target:
        raise ValueError("گیرنده یافت نشد.")

    seller = get_seller_for_user(target) or ensure_seller_for_user(target)
    if seller is None:
        raise ValueError("برای این کاربر پرونده پرسنل یافت نشد.")

    start = _parse_dispatch_date(start_date, field_label="تاریخ شروع")
    duration_unit = (duration_unit or "days").strip() or "days"
    leave_hours = None
    resolved_kind = dest_kind
    resolved_code = dest_code
    resolved_label = dest_label
    work_branch = seller.branch_id
    pay = ""

    if kind == "leave":
        pay = (pay_type or "").strip()
        if pay not in (StaffAttendance.LEAVE_PAY_PAID, StaffAttendance.LEAVE_PAY_UNPAID):
            raise ValueError("نوع مرخصی را انتخاب کنید.")
        if duration_unit not in ("days", "hours"):
            raise ValueError("مدت مرخصی نامعتبر است.")
        if duration_unit == "hours":
            try:
                leave_hours = Decimal(str(hours))
            except (TypeError, ValueError, ArithmeticError):
                raise ValueError("مدت مرخصی ساعتی را وارد کنید.") from None
            if leave_hours <= 0:
                raise ValueError("مدت مرخصی ساعتی باید بیشتر از صفر باشد.")
            day_len = work_day_hours()
            if day_len is None:
                raise ValueError("ابتدا ساعت کاری سراسری را در تنظیمات سایت تعیین کنید.")
            if leave_hours > Decimal(str(day_len)):
                raise ValueError(f"مرخصی ساعتی نمی‌تواند بیشتر از { _format_hours_label(day_len) } ساعت کاری باشد.")
            days = [start]
        else:
            end = _parse_dispatch_date(end_date or start_date, field_label="تاریخ پایان")
            days = _dispatch_days(start, end)
        auto_title = _leave_title(pay_type=pay, duration_unit=duration_unit, hours=float(leave_hours) if leave_hours is not None else None, days=days)
        action = Notification.ACTION_ORG_LEAVE
    else:
        resolved_kind, resolved_code, resolved_label, work_branch_override = _resolve_mission_destination(
            dest_kind, dest_code, dest_label
        )
        if work_branch_override:
            work_branch = work_branch_override
        end = _parse_dispatch_date(end_date or start_date, field_label="تاریخ پایان")
        days = _dispatch_days(start, end)
        auto_title = _mission_title(resolved_kind, resolved_label)
        action = Notification.ACTION_ORG_MISSION

    title = (title or "").strip() or auto_title
    notes = (body or "").strip() or title
    attendance_ids = []
    for day in days:
        record, _created = upsert_manager_attendance(
            seller,
            day,
            "leave" if kind == "leave" else "mission",
            sender,
            branch=work_branch,
            notes=notes[:255],
            leave_pay_type=pay if kind == "leave" else "",
            leave_hours=leave_hours if kind == "leave" else None,
            mission_dest_kind=resolved_kind if kind == "mission" else "",
            mission_dest_code=resolved_code if kind == "mission" else "",
            mission_dest_label=resolved_label if kind == "mission" else "",
        )
        attendance_ids.append(record.id)

    payload = {
        "kind": kind,
        "status": "applied",
        "to_user_id": target.id,
        "to_name": _user_display(target),
        "from_user_id": sender.id,
        "from_name": _user_display(sender),
        "start_date": days[0].isoformat(),
        "end_date": days[-1].isoformat(),
        "attendance_ids": attendance_ids,
        "seller_id": seller.id,
    }
    if kind == "leave":
        payload.update({
            "pay_type": pay,
            "duration_unit": duration_unit,
            "hours": float(leave_hours) if leave_hours is not None else None,
        })
    else:
        payload.update({
            "dest_kind": resolved_kind,
            "dest_code": resolved_code,
            "dest_label": resolved_label,
        })

    return create_notification(
        section=Notification.SECTION_ORG,
        title=title[:160],
        body=(body or "").strip(),
        action_type=action,
        payload=payload,
        recipients=[target],
        created_by=sender,
    )


def _is_thread_party(note, user):
    payload = note.payload or {}
    if note.created_by_id == user.id:
        return True
    if _payload_user_id(payload, "claimed_by_id", "to_user_id") == user.id:
        return True
    return NotificationReceipt.objects.filter(notification=note, user=user).exists()


def can_access_thread(user, note):
    if note.action_type not in ORG_ACTION_TYPES:
        return False
    if is_system_admin(user):
        return True
    return _is_thread_party(note, user)


@transaction.atomic
def open_org_thread(user, notification_id):
    """برگرداندن گفتگو؛ تیکت دپارتمانی با اولین باز شدن مال همان نفر می‌شود."""
    note = (
        Notification.objects.select_for_update()
        .select_related("created_by")
        .filter(pk=notification_id)
        .first()
    )
    if note is None or not can_access_thread(user, note):
        raise LookupError("گفتگو یافت نشد.")

    payload = dict(note.payload or {})
    is_party = _is_thread_party(user=user, note=note)
    admin_only = is_system_admin(user) and not is_party

    if (
        not admin_only
        and note.action_type == Notification.ACTION_ORG_TICKET
        and payload.get("to_department")
        and not payload.get("claimed_by_id")
        and NotificationReceipt.objects.filter(notification=note, user=user).exists()
    ):
        payload["claimed_by_id"] = user.id
        payload["claimed_by_name"] = _user_display(user)
        payload["to_user_id"] = user.id
        payload["to_name"] = _user_display(user)
        note.payload = payload
        note.save(update_fields=["payload"])
        NotificationReceipt.objects.filter(notification=note).exclude(user=user).delete()
        receipt = NotificationReceipt.objects.filter(notification=note, user=user).first()
        if receipt and not receipt.is_read:
            mark_read(receipt, read=True)
        if payload.get("purpose") == "early_ship_disposition" and payload.get("sale_id"):
            from logic.early_ship import attach_disposition_claimer
            from backend.models import Sale as SaleModel

            sale = SaleModel.objects.filter(pk=payload.get("sale_id")).first()
            if sale:
                attach_disposition_claimer(sale, user)
    else:
        claimed_id = _payload_user_id(payload, "claimed_by_id")
        if (
            claimed_id
            and claimed_id != user.id
            and note.created_by_id != user.id
            and not is_system_admin(user)
        ):
            raise LookupError("گفتگو یافت نشد.")

    receipt = NotificationReceipt.objects.filter(notification=note, user=user).first()
    data = notification_to_dict(note, user, box="thread", include_messages=True)
    if receipt:
        data["id"] = receipt.id
        data["is_read"] = receipt.is_read
        data["read_at"] = receipt.read_at.isoformat() if receipt.read_at else None
        data["box"] = "inbox"
    elif note.created_by_id == user.id:
        data["box"] = "sent"
    elif is_system_admin(user):
        data["box"] = "all"
    return data


def close_or_reopen_ticket(note, user, action):
    if note.action_type != Notification.ACTION_ORG_TICKET:
        raise ValueError("این اعلان تیکت نیست.")
    payload = dict(note.payload or {})
    is_sender = note.created_by_id == user.id
    holder_id = _payload_user_id(payload, "claimed_by_id", "to_user_id")
    if not is_sender and holder_id != user.id:
        raise PermissionError("فقط فرستنده یا دارنده می‌تواند وضعیت را عوض کند.")
    action = (action or "").strip()
    if action == "close":
        payload["status"] = "closed"
        note.payload = payload
        note.resolved_at = timezone.now()
        note.resolved_by = user
        note.save(update_fields=["payload", "resolved_at", "resolved_by"])
        return note
    if action == "reopen":
        payload["status"] = "open"
        note.payload = payload
        note.resolved_at = None
        note.resolved_by = None
        note.save(update_fields=["payload", "resolved_at", "resolved_by"])
        return note
    raise ValueError("اقدام نامعتبر است.")


def add_ticket_reply(note, user, body):
    body = (body or "").strip()
    if not body:
        raise ValueError("متن پاسخ را وارد کنید.")
    if note.action_type != Notification.ACTION_ORG_TICKET:
        raise ValueError("فقط تیکت پاسخ دارد.")
    flags = _ticket_flags(note, user)
    if flags.get("is_admin_view"):
        raise PermissionError("مدیر سیستم فقط می‌تواند بخواند.")
    if not flags.get("can_reply"):
        if flags.get("status") == "closed":
            raise ValueError("تیکت بسته است.")
        raise PermissionError("اجازه پاسخ ندارید.")
    return TicketMessage.objects.create(notification=note, author=user, body=body)


def complete_org_responsibility(note, user):
    if note.action_type != Notification.ACTION_ORG_RESPONSIBILITY:
        raise ValueError("این اعلان مسئولیت نیست.")
    if note.resolved_at:
        return note
    payload = dict(note.payload or {})
    holder_id = _payload_user_id(payload, "to_user_id", "claimed_by_id")
    has_receipt = NotificationReceipt.objects.filter(notification=note, user=user).exists()
    if holder_id:
        if holder_id != int(user.id):
            raise ValueError("فقط گیرنده می‌تواند این مسئولیت را ببندد.")
    elif not has_receipt:
        raise ValueError("فقط گیرنده می‌تواند این مسئولیت را ببندد.")
    payload["status"] = "done"
    note.payload = payload
    note.resolved_at = timezone.now()
    note.resolved_by = user
    note.save(update_fields=["payload", "resolved_at", "resolved_by"])
    return note
