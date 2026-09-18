"""تایید نهایی ساخته‌شده‌ها، تعیین تکلیف ارسال زودتر از موعد و ارسال به باربری."""

from datetime import date as date_cls

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from auth.permissions import APPROVE_SALE_ACCOUNTING, has_permission
from backend.models import Notification, Sale, TicketMessage
from logic.departments import DEPARTMENT_OFFICE, DEPARTMENT_SHOP, users_in_department
from logic.notifications import create_notification
from logic.ticket_grades import get_ticket_grades, grade_color

STAGE_PRODUCTION_DONE = "production_done"
STAGE_IN_FREIGHT = "in_freight"

LEAD_DAYS_FOR_DISPOSITION = 10
REMAINING_DAYS_FOR_DISPOSITION = 2
URGENCY_ORANGE_DAYS = 7
URGENCY_RED_DAYS = 3
READY_FOR_DELIVERY_LABEL = "آماده تحویل"
READY_FOR_DELIVERY_COLOR = "#22c55e"
DISPOSITION_PURPOSE = "early_ship_disposition"

CLEAR_READY_FIELDS = {
    "delivery_ready_at": None,
    "delivery_ready_by_id": None,
    "early_disposition_required": False,
    "early_ship_allowed_date": None,
    "early_disposition_by_id": None,
    "shipped_early": False,
}


def _sale_date(sale):
    sold_at = getattr(sale, "sold_at", None)
    if not sold_at:
        return None
    if timezone.is_aware(sold_at):
        return timezone.localtime(sold_at).date()
    return sold_at.date()


def original_lead_days(sale):
    sold_date = _sale_date(sale)
    if not sold_date or not sale.delivery_date:
        return None
    return (sale.delivery_date - sold_date).days


def days_until_delivery(sale, today=None):
    if not sale.delivery_date:
        return None
    today = today or timezone.localdate()
    return (sale.delivery_date - today).days


def needs_early_disposition(sale, today=None):
    lead = original_lead_days(sale)
    remaining = days_until_delivery(sale, today)
    if lead is None or remaining is None:
        return False
    return lead > LEAD_DAYS_FOR_DISPOSITION and remaining > REMAINING_DAYS_FOR_DISPOSITION


def delivery_urgency(sale, today=None):
    if getattr(sale, "delivery_ready_at", None):
        return ""
    remaining = days_until_delivery(sale, today)
    if remaining is None:
        return ""
    if remaining <= URGENCY_RED_DAYS:
        return "red"
    if remaining <= URGENCY_ORANGE_DAYS:
        return "orange"
    return ""


def stage_badge_for_sale(sale):
    from logic.sale_workflow import WORKFLOW_STAGE_LABELS

    stage = sale.workflow_stage_id
    if stage == STAGE_PRODUCTION_DONE and sale.delivery_ready_at:
        return READY_FOR_DELIVERY_LABEL, READY_FOR_DELIVERY_COLOR
    return WORKFLOW_STAGE_LABELS.get(stage, stage), None


def _user_display(user):
    if not user:
        return ""
    return (user.get_full_name() or user.username or "").strip()


def _invoice_label(sale):
    return (sale.invoice_number or str(sale.pk)).strip()


def disposition_recipients(*, exclude_user=None):
    seen = {}
    for department in (DEPARTMENT_OFFICE, DEPARTMENT_SHOP):
        for user in users_in_department(department, exclude_user=exclude_user):
            seen[user.id] = user
    return list(seen.values())


def _base_disposition_payload(sale, sender, *, kind):
    settings = get_ticket_grades()
    grade_key = settings["default_grade"]
    return {
        "kind": kind,
        "status": "open",
        "purpose": DISPOSITION_PURPOSE,
        "sale_id": sale.id,
        "invoice_number": _invoice_label(sale),
        "customer_name": sale.customer.full_name if sale.customer_id else "",
        "to_user_id": None,
        "to_name": "",
        "to_department": DEPARTMENT_OFFICE,
        "to_departments": [DEPARTMENT_OFFICE, DEPARTMENT_SHOP],
        "claimed_by_id": None,
        "claimed_by_name": "",
        "from_user_id": sender.id if sender else None,
        "from_name": _user_display(sender),
        "grade": grade_key,
        "color": grade_color(grade_key, settings),
        "original_delivery_date": sale.delivery_date.isoformat() if sale.delivery_date else None,
        "days_remaining": days_until_delivery(sale),
        "lead_days": original_lead_days(sale),
        "early_ship_allowed_date": None,
    }


def create_early_ship_disposition(sale, sender):
    """تیکت و مسئولیت تعیین تکلیف برای اداری و مدیریت مشتریان."""
    recipients = disposition_recipients(exclude_user=sender)
    if not recipients:
        return None, None

    invoice = _invoice_label(sale)
    remaining = days_until_delivery(sale)
    lead = original_lead_days(sale)
    delivery_label = sale.delivery_date.isoformat() if sale.delivery_date else "—"
    body = (
        f"ساخت سفارش تمام شده و تایید نهایی خورده است. "
        f"سقف تحویل هنگام ثبت {lead if lead is not None else '—'} روز بوده "
        f"و اکنون {remaining if remaining is not None else '—'} روز تا تاریخ تحویل ({delivery_label}) مانده. "
        "تاریخ مجاز ارسال زودتر از موعد را تعیین کنید."
    )
    ticket = create_notification(
        section=Notification.SECTION_ORG,
        title=f"تعیین تکلیف ارسال زودتر از موعد — {invoice}",
        body=body,
        action_type=Notification.ACTION_ORG_TICKET,
        payload=_base_disposition_payload(sale, sender, kind="ticket"),
        recipients=recipients,
        created_by=sender,
    )
    responsibility = create_notification(
        section=Notification.SECTION_ORG,
        title=f"مسئولیت تعیین تکلیف ارسال — {invoice}",
        body=body,
        action_type=Notification.ACTION_ORG_RESPONSIBILITY,
        payload=_base_disposition_payload(sale, sender, kind="responsibility"),
        recipients=recipients,
        created_by=sender,
    )
    return ticket, responsibility


def disposition_notes_for_sale(sale):
    return Notification.objects.filter(
        action_type__in=[
            Notification.ACTION_ORG_TICKET,
            Notification.ACTION_ORG_RESPONSIBILITY,
        ]
    ).filter(
        Q(payload__purpose=DISPOSITION_PURPOSE) & Q(payload__sale_id=sale.pk)
    )


def attach_disposition_claimer(sale, user):
    if not sale or not user:
        return
    Sale.objects.filter(pk=sale.pk).update(early_disposition_by_id=user.pk)


def close_disposition_threads(sale, user=None):
    now = timezone.now()
    for note in disposition_notes_for_sale(sale):
        payload = dict(note.payload or {})
        if payload.get("status") in {"closed", "done"}:
            continue
        payload["status"] = "closed" if note.action_type == Notification.ACTION_ORG_TICKET else "done"
        note.payload = payload
        note.resolved_at = now
        note.resolved_by = user
        note.save(update_fields=["payload", "resolved_at", "resolved_by"])


def parse_allowed_date(value):
    if isinstance(value, date_cls):
        return value
    text = str(value or "").strip()
    parsed = parse_date(text)
    if parsed is None:
        raise ValueError("تاریخ ارسال نامعتبر است.")
    return parsed


def can_set_early_ship_date(user, sale, note=None):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if has_permission(user, APPROVE_SALE_ACCOUNTING):
        return True
    if note is None:
        return False
    payload = note.payload or {}
    if payload.get("purpose") != DISPOSITION_PURPOSE:
        return False
    holder_id = payload.get("claimed_by_id") or payload.get("to_user_id")
    try:
        holder_id = int(holder_id) if holder_id is not None else None
    except (TypeError, ValueError):
        holder_id = None
    status = (payload.get("status") or "open").strip() or "open"
    return holder_id == user.id and status != "closed"


def set_early_ship_allowed_date(sale, user, allowed_date, *, notification=None):
    if sale.workflow_stage_id != STAGE_PRODUCTION_DONE:
        raise ValueError("فقط سفارش آماده باربری قابل تعیین تکلیف است.")
    if not sale.delivery_ready_at:
        raise ValueError("ابتدا تایید نهایی انجام شود.")
    allowed = parse_allowed_date(allowed_date)
    today = timezone.localdate()
    if allowed < today:
        raise ValueError("تاریخ ارسال نمی‌تواند قبل از امروز باشد.")
    if sale.delivery_date and allowed > sale.delivery_date:
        raise ValueError("تاریخ ارسال نمی‌تواند بعد از تاریخ تحویل باشد.")
    sale.early_ship_allowed_date = allowed
    if not sale.early_disposition_by_id:
        sale.early_disposition_by = user
    sale.save(update_fields=["early_ship_allowed_date", "early_disposition_by"])
    if notification is None:
        notification = (
            disposition_notes_for_sale(sale)
            .filter(action_type=Notification.ACTION_ORG_TICKET)
            .first()
        )
    notes = [notification] if notification else []
    if notification:
        for extra in disposition_notes_for_sale(sale):
            if extra.pk != notification.pk:
                notes.append(extra)
    for note in notes:
        if note is None:
            continue
        payload = dict(note.payload or {})
        payload["early_ship_allowed_date"] = allowed.isoformat()
        note.payload = payload
        note.save(update_fields=["payload"])
    if notification and notification.action_type == Notification.ACTION_ORG_TICKET:
        TicketMessage.objects.create(
            notification=notification,
            author=user,
            body=f"تاریخ مجاز ارسال: {allowed.isoformat()}",
        )
    return sale


def set_early_ship_from_ticket(note, user, allowed_date):
    payload = note.payload or {}
    if payload.get("purpose") != DISPOSITION_PURPOSE:
        raise ValueError("این تیکت تعیین تکلیف ارسال نیست.")
    sale_id = payload.get("sale_id")
    sale = Sale.objects.filter(pk=sale_id).first() if sale_id else None
    if sale is None:
        raise ValueError("سفارش این تیکت یافت نشد.")
    if not can_set_early_ship_date(user, sale, note):
        raise PermissionError("اجازه تعیین تاریخ ارسال ندارید.")
    return set_early_ship_allowed_date(sale, user, allowed_date, notification=note)


@transaction.atomic
def confirm_factory_delivery_ready(factory_order, user):
    if factory_order.workflow_stage_id != STAGE_PRODUCTION_DONE:
        raise ValueError("این سفارش هنوز ساخته نشده است.")
    if factory_order.delivery_ready_at:
        raise ValueError("تایید نهایی قبلاً انجام شده است.")
    sale = Sale.objects.select_for_update().get(pk=factory_order.pk)
    required = needs_early_disposition(sale)
    sale.delivery_ready_at = timezone.now()
    sale.delivery_ready_by = user
    sale.early_disposition_required = required
    sale.early_ship_allowed_date = None if required else timezone.localdate()
    sale.save(
        update_fields=[
            "delivery_ready_at",
            "delivery_ready_by",
            "early_disposition_required",
            "early_ship_allowed_date",
        ]
    )
    if required:
        create_early_ship_disposition(sale, user)
    from logic.order_queues import as_factory_order

    return as_factory_order(sale)


@transaction.atomic
def send_factory_order_to_freight(factory_order, user):
    today = timezone.localdate()
    if factory_order.workflow_stage_id != STAGE_PRODUCTION_DONE:
        raise ValueError("این سفارش هنوز آماده باربری نیست.")
    sale = Sale.objects.select_for_update().get(pk=factory_order.pk)
    if not sale.delivery_ready_at:
        raise ValueError("ابتدا تایید نهایی را بزنید.")
    early = bool(sale.delivery_date and sale.delivery_date > today)
    if early:
        if sale.early_disposition_required and not sale.early_ship_allowed_date:
            raise ValueError("منتظر تعیین تکلیف اداری برای ارسال زودتر از موعد هستید.")
        if sale.early_ship_allowed_date and today < sale.early_ship_allowed_date:
            raise ValueError("ارسال از تاریخ تعیین‌شده توسط اداری مجاز است.")
    from logic.materials import deduct_materials_for_factory_order
    from logic.order_queues import as_factory_order, transition_order

    deduct_materials_for_factory_order(sale)
    updated = transition_order(
        sale,
        STAGE_IN_FREIGHT,
        user,
        freight_received_at=timezone.now(),
        freight_received_by_id=user.pk if user else None,
        shipped_early=early,
    )
    return as_factory_order(updated)


def freight_ready_payload(sale):
    label, color = stage_badge_for_sale(sale)
    remaining = days_until_delivery(sale)
    return {
        "delivery_ready_at": sale.delivery_ready_at.isoformat() if sale.delivery_ready_at else None,
        "early_disposition_required": bool(sale.early_disposition_required),
        "early_ship_allowed_date": (
            sale.early_ship_allowed_date.isoformat() if sale.early_ship_allowed_date else None
        ),
        "shipped_early": bool(sale.shipped_early),
        "days_until_delivery": remaining,
        "urgency": delivery_urgency(sale),
        "stage_badge_label": label,
        "stage_badge_color": color,
        "early_disposition_pending": bool(
            sale.early_disposition_required
            and not sale.early_ship_allowed_date
            and sale.workflow_stage_id == STAGE_PRODUCTION_DONE
        ),
    }
