"""endpointهای پیامک — /api/sms/."""

from api.helpers import api_view, fail, parse_json, success
from api.serializers import sms_result_to_dict, sms_to_dict
from auth.permissions import SEND_SMS, VIEW_SMS_LOGS, has_permission
from backend.models import SMSLog
from logic.sms import (
    send_sms,
    send_sms_to_all_active_customers,
    send_sms_to_customer,
    send_sms_to_level,
)
from logic.audit import log_action


@api_view("GET")
def sms_logs(request):
    if not has_permission(request.user, VIEW_SMS_LOGS):
        return fail("Permission denied", status=403)
    logs = SMSLog.objects.select_related("customer", "created_by").all()
    return success({"results": [sms_to_dict(m) for m in logs]})


@api_view("POST")
def sms_send(request):
    if not has_permission(request.user, SEND_SMS):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    message = (data.get("message") or "").strip()
    if not message:
        return fail("Message text is required", status=400)

    try:
        if data.get("customer_id"):
            result = send_sms_to_customer(
                data["customer_id"],
                message,
                user=request.user,
                sms_type="manual",
            )
        else:
            phone = (data.get("phone_number") or data.get("phone") or "").strip()
            if not phone:
                return fail("phone_number or customer_id is required", status=400)
            log = send_sms(
                phone,
                message,
                sms_type="manual",
                user=request.user,
            )
            result = {
                "successful": 1 if log.status == "sent" else 0,
                "failed": 1 if log.status == "failed" and log.error_message != "Invalid or empty phone number." else 0,
                "skipped": 1 if log.error_message == "Invalid or empty phone number." else 0,
                "results": [log],
            }
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "sms",
        f"ارسال پیامک — موفق: {result.get('successful', 0)}",
        details={"failed": result.get("failed", 0), "skipped": result.get("skipped", 0)},
    )
    return success(sms_result_to_dict(result), status=201)


@api_view("POST")
def sms_send_to_level(request):
    if not has_permission(request.user, SEND_SMS):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    message = (data.get("message") or "").strip()
    level_id = data.get("level_id")
    if not message:
        return fail("Message text is required", status=400)
    if not level_id:
        return fail("level_id is required", status=400)

    try:
        result = send_sms_to_level(level_id, message, user=request.user, sms_type="promotion")
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "sms",
        f"ارسال پیامک به سطح — موفق: {result.get('successful', 0)}",
        details={"level_id": level_id},
    )
    return success(sms_result_to_dict(result), status=201)


@api_view("POST")
def sms_send_to_all(request):
    if not has_permission(request.user, SEND_SMS):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    message = (data.get("message") or "").strip()
    if not message:
        return fail("Message text is required", status=400)

    try:
        result = send_sms_to_all_active_customers(message, user=request.user, sms_type="promotion")
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "sms",
        f"ارسال پیامک به همه — موفق: {result.get('successful', 0)}",
    )
    return success(sms_result_to_dict(result), status=201)
