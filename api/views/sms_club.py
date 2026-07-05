"""endpointهای پیامک باشگاه مشتریان — /api/sms/club/."""

from decimal import Decimal, InvalidOperation

from api.helpers import api_view, fail, parse_json, success
from api.serializers import sms_result_to_dict
from auth.permissions import MANAGE_BIRTHDAY_SMS, MANAGE_SMS_CLUB, SEND_SMS, VIEW_SMS_LOGS, has_permission
from backend.models import Customer
from logic.audit import log_action
from logic.sms_club import (
    build_discount_message,
    send_discount_bulk,
    send_discount_sms,
    settings_to_dict,
    update_club_settings,
)


def _require_send(user):
    if not has_permission(user, SEND_SMS):
        return fail("Permission denied", status=403)
    return None


def _require_manage_club(user):
    if has_permission(user, MANAGE_SMS_CLUB) or has_permission(user, SEND_SMS):
        return None
    return fail("Permission denied", status=403)


@api_view("GET", "PUT")
def club_settings(request):
    denied = _require_manage_club(request.user)
    if denied:
        return denied

    if request.method == "GET":
        return success(settings_to_dict())

    try:
        settings = update_club_settings(parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(request.user, "update", "بروزرسانی تنظیمات پیامک باشگاه")
    return success(settings_to_dict(settings))


@api_view("POST")
def club_send_discount(request):
    denied = _require_send(request.user)
    if denied:
        return denied

    data = parse_json(request)
    discount_type = (data.get("discount_type") or "amount").strip()
    try:
        discount_value = Decimal(str(data.get("discount_value") or 0))
    except (InvalidOperation, TypeError):
        return fail("مقدار تخفیف نامعتبر است.", status=400)

    if discount_value <= 0:
        return fail("مقدار تخفیف باید بزرگ‌تر از صفر باشد.", status=400)

    target = (data.get("target") or "single").strip()
    message_template = (data.get("message_template") or "").strip() or None

    try:
        if target == "single":
            customer_id = data.get("customer_id")
            if not customer_id:
                return fail("customer_id الزامی است.", status=400)
            customer = Customer.objects.filter(pk=customer_id, is_active=True).first()
            if not customer:
                return fail("Customer not found", status=404)
            msg = message_template or None
            if message_template:
                from logic.sms_club import render_template, _format_discount_label, _base_ctx

                msg = render_template(
                    message_template,
                    **_base_ctx(customer),
                    discount_label=_format_discount_label(discount_type, discount_value),
                    discount_amount=int(discount_value) if discount_type == "amount" else 0,
                    discount_percent=int(discount_value) if discount_type == "percent" else 0,
                )
            log = send_discount_sms(
                customer,
                discount_type,
                discount_value,
                user=request.user,
                message=msg,
            )
            from logic.sms import _single_result

            result = _single_result(log)
        elif target == "level":
            level_id = data.get("level_id")
            if not level_id:
                return fail("level_id الزامی است.", status=400)
            result = send_discount_bulk(
                discount_type,
                discount_value,
                user=request.user,
                level_id=level_id,
                message_template=message_template,
            )
        elif target == "all":
            result = send_discount_bulk(
                discount_type,
                discount_value,
                user=request.user,
                send_to_all=True,
                message_template=message_template,
            )
        elif target == "selected":
            customer_ids = data.get("customer_ids") or []
            if not customer_ids:
                return fail("customer_ids الزامی است.", status=400)
            result = send_discount_bulk(
                discount_type,
                discount_value,
                user=request.user,
                customer_ids=customer_ids,
                message_template=message_template,
            )
        else:
            return fail("target نامعتبر است.", status=400)
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "sms",
        f"ارسال تخفیف ویژه — موفق: {result.get('successful', 0)}",
        details={"discount_type": discount_type, "discount_value": int(discount_value)},
    )
    return success(sms_result_to_dict(result), status=201)


@api_view("GET")
def club_discount_preview(request):
    if not has_permission(request.user, VIEW_SMS_LOGS) and not has_permission(
        request.user, SEND_SMS
    ):
        return fail("Permission denied", status=403)

    customer_id = request.GET.get("customer_id")
    if not customer_id:
        return fail("customer_id الزامی است.", status=400)

    customer = Customer.objects.filter(pk=customer_id).first()
    if not customer:
        return fail("Customer not found", status=404)

    discount_type = request.GET.get("discount_type") or "amount"
    try:
        discount_value = Decimal(str(request.GET.get("discount_value") or 0))
    except (InvalidOperation, TypeError):
        return fail("مقدار تخفیف نامعتبر است.", status=400)

    message = build_discount_message(customer, discount_type, discount_value)
    return success({"message": message, "customer_id": customer.id})
