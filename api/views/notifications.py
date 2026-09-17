"""API اعلان‌ها — فهرست، خواندن، اقدام تغییر شعبه."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import MANAGE_ATTENDANCE, has_permission, is_system_admin
from backend.models import Notification
from logic.attendance import approve_branch_switch
from logic.notifications import (
    add_ticket_reply,
    all_threads_queryset,
    close_or_reopen_ticket,
    complete_org_responsibility,
    list_message_recipients,
    list_recipient_departments,
    list_ticket_invoices,
    mark_read,
    notification_sections_for_user,
    notification_to_dict,
    open_org_thread,
    receipt_queryset,
    receipt_to_dict,
    send_org_message,
    sent_queryset,
    unread_count,
)
from logic.pagination import paginate


@api_view("GET")
def notification_list(request):
    if not request.user.is_authenticated:
        return fail("Unauthorized", status=401)
    box = (request.GET.get("box") or "inbox").strip() or "inbox"
    if box == "all":
        if not is_system_admin(request.user):
            return fail("Permission denied", status=403)
        qs = all_threads_queryset(request.user)
        page, meta = paginate(qs, request.GET)
        return success(
            {
                "results": [notification_to_dict(row, request.user, box="all") for row in page],
                "unread_count": unread_count(request.user),
                "sections": notification_sections_for_user(request.user),
                "box": "all",
                **meta,
            }
        )
    if box == "sent":
        qs = sent_queryset(request.user)
        page, meta = paginate(qs, request.GET)
        return success(
            {
                "results": [notification_to_dict(row, request.user, box="sent") for row in page],
                "unread_count": unread_count(request.user),
                "sections": notification_sections_for_user(request.user),
                "box": "sent",
                **meta,
            }
        )
    qs = receipt_queryset(request.user)
    section = (request.GET.get("section") or "").strip()
    if section:
        qs = qs.filter(notification__section=section)
    unread_only = request.GET.get("unread") == "1"
    if unread_only:
        qs = qs.filter(is_read=False)
    page, meta = paginate(qs, request.GET)
    return success(
        {
            "results": [receipt_to_dict(row, request.user) for row in page],
            "unread_count": unread_count(request.user),
            "sections": notification_sections_for_user(request.user),
            "box": "inbox",
            **meta,
        }
    )


@api_view("GET")
def notification_unread(request):
    if not request.user.is_authenticated:
        return fail("Unauthorized", status=401)
    return success(
        {
            "unread_count": unread_count(request.user),
            "sections": notification_sections_for_user(request.user),
        }
    )


@api_view("POST")
def notification_read(request, pk):
    if not request.user.is_authenticated:
        return fail("Unauthorized", status=401)
    receipt = receipt_queryset(request.user).filter(pk=pk).first()
    if receipt is None:
        return fail("اعلان یافت نشد.", status=404)
    data = parse_json(request)
    read = True if "read" not in data else bool(data.get("read"))
    return success(receipt_to_dict(mark_read(receipt, read=read), request.user))


@api_view("POST")
def notification_read_all(request):
    if not request.user.is_authenticated:
        return fail("Unauthorized", status=401)
    from django.utils import timezone

    qs = receipt_queryset(request.user).filter(is_read=False)
    qs.update(is_read=True, read_at=timezone.now())
    return success({"unread_count": 0})


@api_view("GET")
def notification_recipients(request):
    if not request.user.is_authenticated:
        return fail("Unauthorized", status=401)
    return success(
        {
            "results": list_message_recipients(request.user),
            "departments": list_recipient_departments(),
        }
    )


@api_view("GET")
def notification_invoices(request):
    if not request.user.is_authenticated:
        return fail("Unauthorized", status=401)
    return success(
        {
            "results": list_ticket_invoices(
                request.user,
                search=request.GET.get("search") or "",
                date=request.GET.get("date") or "",
                limit=request.GET.get("limit") or 10,
            )
        }
    )


@api_view("POST")
def notification_messages(request):
    if not request.user.is_authenticated:
        return fail("Unauthorized", status=401)
    data = parse_json(request)
    try:
        note = send_org_message(
            sender=request.user,
            to_user_id=data.get("to_user_id"),
            to_department=data.get("to_department"),
            sale_id=data.get("sale_id"),
            kind=data.get("kind") or "ticket",
            title=data.get("title") or "",
            body=data.get("body") or "",
            grade=data.get("grade"),
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success({"id": note.id, "title": note.title, "action_type": note.action_type, "payload": note.payload})


@api_view("GET")
def notification_detail(request, pk):
    if not request.user.is_authenticated:
        return fail("Unauthorized", status=401)
    try:
        data = open_org_thread(request.user, pk)
    except LookupError:
        return fail("گفتگو یافت نشد.", status=404)
    return success(data)


@api_view("POST")
def notification_replies(request, pk):
    if not request.user.is_authenticated:
        return fail("Unauthorized", status=401)
    try:
        thread = open_org_thread(request.user, pk)
    except LookupError:
        return fail("گفتگو یافت نشد.", status=404)
    note = Notification.objects.filter(pk=thread["notification_id"]).first()
    if note is None:
        return fail("گفتگو یافت نشد.", status=404)
    data = parse_json(request)
    try:
        message = add_ticket_reply(note, request.user, data.get("body") or "")
    except PermissionError as exc:
        return fail(str(exc), status=403)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(
        {
            "id": message.id,
            "author_name": message.author.get_full_name() or message.author.username if message.author_id else "",
            "author_id": message.author_id,
            "body": message.body,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "is_initial": False,
        }
    )


@api_view("POST")
def notification_act(request, pk):
    if not request.user.is_authenticated:
        return fail("Unauthorized", status=401)
    data = parse_json(request)
    action = (data.get("action") or "").strip()
    if action in ("close", "reopen"):
        try:
            thread = open_org_thread(request.user, pk)
        except LookupError:
            return fail("گفتگو یافت نشد.", status=404)
        note = Notification.objects.filter(pk=thread["notification_id"]).first()
        if note is None:
            return fail("گفتگو یافت نشد.", status=404)
        try:
            close_or_reopen_ticket(note, request.user, action)
        except PermissionError as exc:
            return fail(str(exc), status=403)
        except ValueError as exc:
            return fail(str(exc), status=400)
        try:
            return success(open_org_thread(request.user, note.id))
        except LookupError:
            return fail("گفتگو یافت نشد.", status=404)
    receipt = receipt_queryset(request.user).filter(pk=pk).first()
    if receipt is None:
        return fail("اعلان یافت نشد.", status=404)
    note = receipt.notification
    if note.action_type == Notification.ACTION_BRANCH_SWITCH:
        if not has_permission(request.user, MANAGE_ATTENDANCE):
            return fail("Permission denied", status=403)
        try:
            approve_branch_switch(note, request.user)
        except ValueError as exc:
            return fail(str(exc), status=400)
        mark_read(receipt, read=True)
        receipt.refresh_from_db()
        return success(receipt_to_dict(receipt, request.user))
    if note.action_type == Notification.ACTION_ORG_RESPONSIBILITY:
        try:
            complete_org_responsibility(note, request.user)
        except ValueError as exc:
            return fail(str(exc), status=400)
        mark_read(receipt, read=True)
        receipt.refresh_from_db()
        return success(receipt_to_dict(receipt, request.user))
    return fail("این اعلان اقدام قابل انجام ندارد.", status=400)
