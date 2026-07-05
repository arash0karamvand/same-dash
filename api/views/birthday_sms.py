"""endpointهای پیامک تبریک تولد — /api/sms/birthday/."""

from api.helpers import api_view, fail, parse_json, success
from api.serializers import sms_result_to_dict
from auth.permissions import MANAGE_BIRTHDAY_SMS, SEND_SMS, VIEW_SMS_LOGS, has_permission
from logic.audit import log_action
from logic.birthday_sms import (
    build_preview,
    exclude_customer,
    remove_exclusion,
    send_birthday_batch,
    settings_to_dict,
    update_settings,
)


def _require_send(user):
    if not has_permission(user, SEND_SMS):
        return fail("Permission denied", status=403)
    return None


def _require_manage_birthday(user):
    if has_permission(user, MANAGE_BIRTHDAY_SMS) or has_permission(user, SEND_SMS):
        return None
    return fail("Permission denied", status=403)


@api_view("GET", "PUT")
def birthday_settings(request):
    denied = _require_manage_birthday(request.user)
    if denied:
        return denied

    if request.method == "GET":
        return success(settings_to_dict())

    try:
        settings = update_settings(parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(request.user, "update", "بروزرسانی تنظیمات پیامک تولد")
    return success(settings_to_dict(settings))


@api_view("GET")
def birthday_preview(request):
    if not has_permission(request.user, VIEW_SMS_LOGS) and not has_permission(
        request.user, SEND_SMS
    ):
        return fail("Permission denied", status=403)

    auto = (request.GET.get("auto") or "").lower() in ("1", "true", "yes")
    preview = build_preview(auto_run=auto and has_permission(request.user, SEND_SMS))
    if preview.get("auto_result"):
        r = preview["auto_result"]
        if r.get("successful") or r.get("failed"):
            log_action(
                request.user,
                "sms",
                f"ارسال خودکار تبریک تولد — موفق: {r.get('successful', 0)}",
            )
    return success(preview)


@api_view("POST")
def birthday_exclude(request):
    denied = _require_send(request.user)
    if denied:
        return denied

    data = parse_json(request)
    customer_id = data.get("customer_id")
    if not customer_id:
        return fail("customer_id الزامی است.", status=400)
    try:
        customer = exclude_customer(int(customer_id))
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "update",
        f"حذف {customer.full_name} از لیست ارسال تولد امروز",
        entity_type="Customer",
        entity_id=customer.id,
    )
    return success({"excluded": True, "customer_id": customer.id})


@api_view("DELETE")
def birthday_unexclude(request, customer_id):
    denied = _require_send(request.user)
    if denied:
        return denied

    remove_exclusion(customer_id)
    return success({"excluded": False, "customer_id": customer_id})


@api_view("POST")
def birthday_send(request):
    denied = _require_send(request.user)
    if denied:
        return denied

    data = parse_json(request)
    force = bool(data.get("force"))

    try:
        result = send_birthday_batch(user=request.user, scheduled=False, force=force)
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "sms",
        f"ارسال دستی تبریک تولد — موفق: {result.get('successful', 0)}",
        details={"failed": result.get("failed", 0), "skipped": result.get("skipped", 0)},
    )
    return success(sms_result_to_dict(result), status=201)
