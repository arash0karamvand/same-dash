"""endpointهای تحلیل RFM — /api/rfm/."""

from backend.models import CustomerRfmScore, RfmSegment

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import MANAGE_RFM, SEND_SMS, VIEW_RFM, has_permission
from logic.audit import log_action
from logic.pagination import paginate
from logic.rfm import (
    build_summary,
    create_segment,
    list_scores,
    recalculate_all_rfm,
    score_to_dict,
    seed_rfm_defaults,
    segment_to_dict,
    send_segment_sms,
    settings_to_dict,
    update_segment,
    update_settings,
)


@api_view("GET", "PUT")
def rfm_settings(request):
    seed_rfm_defaults()
    if request.method == "GET":
        if not has_permission(request.user, VIEW_RFM):
            return fail("Permission denied", status=403)
        return success(settings_to_dict())

    if not has_permission(request.user, MANAGE_RFM):
        return fail("Permission denied", status=403)
    try:
        settings = update_settings(parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(request.user, "update", "ویرایش تنظیمات امتیاز RFM")
    return success(settings_to_dict(settings))


@api_view("GET", "POST")
def rfm_segment_list(request):
    seed_rfm_defaults()
    if request.method == "GET":
        if not has_permission(request.user, VIEW_RFM):
            return fail("Permission denied", status=403)
        segments = RfmSegment.objects.all()
        return success({"results": [segment_to_dict(item) for item in segments]})

    if not has_permission(request.user, MANAGE_RFM):
        return fail("Permission denied", status=403)
    try:
        segment = create_segment(parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(request.user, "create", f"بخش RFM: {segment.name}")
    return success(segment_to_dict(segment), status=201)


@api_view("PUT", "DELETE")
def rfm_segment_detail(request, pk):
    try:
        segment = RfmSegment.objects.get(pk=pk)
    except RfmSegment.DoesNotExist:
        return fail("Segment not found", status=404)
    if not has_permission(request.user, MANAGE_RFM):
        return fail("Permission denied", status=403)

    if request.method == "DELETE":
        log_action(request.user, "delete", f"حذف بخش RFM {segment.name}")
        segment.delete()
        return success({"deleted": True})

    try:
        update_segment(segment, parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(request.user, "update", f"ویرایش بخش RFM {segment.name}")
    return success(segment_to_dict(segment))


@api_view("GET")
def rfm_summary(request):
    if not has_permission(request.user, VIEW_RFM):
        return fail("Permission denied", status=403)
    return success(build_summary())


@api_view("GET")
def rfm_customers(request):
    if not has_permission(request.user, VIEW_RFM):
        return fail("Permission denied", status=403)
    page, meta = paginate(list_scores(request.GET), request.GET)
    return success({"results": [score_to_dict(item) for item in page], **meta})


@api_view("POST")
def rfm_recalculate(request):
    if not has_permission(request.user, MANAGE_RFM):
        return fail("Permission denied", status=403)
    data = parse_json(request)
    send_actions = data.get("send_sms", True)
    result = recalculate_all_rfm(send_actions=bool(send_actions))
    log_action(request.user, "update", "بازمحاسبه امتیاز RFM")
    return success(result)


@api_view("POST")
def rfm_send_sms(request, pk):
    if not has_permission(request.user, VIEW_RFM) or not has_permission(request.user, SEND_SMS):
        return fail("Permission denied", status=403)
    try:
        score = CustomerRfmScore.objects.select_related("customer", "segment").get(customer_id=pk)
    except CustomerRfmScore.DoesNotExist:
        return fail("RFM score not found", status=404)
    data = parse_json(request)
    try:
        result = send_segment_sms(
            score,
            message=(data.get("message") or "").strip() or None,
            user=request.user,
            ignore_cooldown=bool(data.get("force")),
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(result)
