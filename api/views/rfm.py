"""endpointهای تحلیل RFM — /api/rfm/."""

from backend.models import CashbackProgram, Customer, CustomerRfmScore, RfmSegment

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import CREATE_SALE, EDIT_SALE, MANAGE_RFM, SEND_SMS, VIEW_SALES, has_permission
from logic.audit import log_action
from logic.cashback import (
    create_program,
    list_programs,
    program_to_dict,
    quote_cashback,
    update_program,
)
from logic.pagination import paginate
from logic.rfm import (
    build_summary,
    can_view_rfm_panel,
    create_segment,
    list_scores,
    recalculate_all_rfm,
    score_to_dict,
    seed_rfm_defaults,
    segment_to_dict,
    send_segment_sms,
    send_sms_to_segment_customers,
    settings_to_dict,
    update_segment,
    update_settings,
)


@api_view("GET", "PUT")
def rfm_settings(request):
    seed_rfm_defaults()
    if request.method == "GET":
        if not can_view_rfm_panel(request.user):
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
        if not can_view_rfm_panel(request.user):
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
    if not can_view_rfm_panel(request.user):
        return fail("Permission denied", status=403)
    return success(build_summary())


@api_view("GET")
def rfm_customers(request):
    if not can_view_rfm_panel(request.user):
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
    if not can_view_rfm_panel(request.user) or not has_permission(request.user, SEND_SMS):
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


@api_view("POST")
def rfm_send_segment_sms(request, pk):
    if not can_view_rfm_panel(request.user) or not has_permission(request.user, SEND_SMS):
        return fail("Permission denied", status=403)
    try:
        segment = RfmSegment.objects.get(pk=pk)
    except RfmSegment.DoesNotExist:
        return fail("Segment not found", status=404)
    data = parse_json(request)
    result = send_sms_to_segment_customers(
        segment.id,
        message=(data.get("message") or "").strip() or None,
        user=request.user,
        ignore_cooldown=bool(data.get("force")),
    )
    log_action(
        request.user,
        "sms",
        f"ارسال پیامک بخش RFM {segment.name} — موفق: {result.get('successful', 0)}",
        details={"segment_id": segment.id},
    )
    return success(result)


def _can_quote_cashback(user):
    return (
        can_view_rfm_panel(user)
        or has_permission(user, CREATE_SALE)
        or has_permission(user, EDIT_SALE)
        or has_permission(user, VIEW_SALES)
    )


@api_view("GET", "POST")
def rfm_cashback_program_list(request):
    if request.method == "GET":
        if not can_view_rfm_panel(request.user):
            return fail("Permission denied", status=403)
        programs = list_programs()
        return success({"results": [program_to_dict(item) for item in programs]})

    if not has_permission(request.user, MANAGE_RFM):
        return fail("Permission denied", status=403)
    try:
        program = create_program(parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(request.user, "create", f"برنامه کش‌بک: {program.name}")
    return success(program_to_dict(program), status=201)


@api_view("PUT", "DELETE")
def rfm_cashback_program_detail(request, pk):
    try:
        program = CashbackProgram.objects.prefetch_related("segments", "unlock_steps").get(pk=pk)
    except CashbackProgram.DoesNotExist:
        return fail("برنامه کش‌بک پیدا نشد.", status=404)
    if not has_permission(request.user, MANAGE_RFM):
        return fail("Permission denied", status=403)

    if request.method == "DELETE":
        log_action(request.user, "delete", f"حذف برنامه کش‌بک {program.name}")
        program.delete()
        return success({"deleted": True})

    try:
        update_program(program, parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)
    program = CashbackProgram.objects.prefetch_related("segments", "unlock_steps").get(pk=program.pk)
    log_action(request.user, "update", f"ویرایش برنامه کش‌بک {program.name}")
    return success(program_to_dict(program))


@api_view("GET")
def rfm_cashback_quote(request):
    if not _can_quote_cashback(request.user):
        return fail("Permission denied", status=403)
    try:
        customer_id = int(request.GET.get("customer_id") or 0)
    except (TypeError, ValueError):
        customer_id = 0
    if not customer_id:
        return fail("مشتری الزامی است.", status=400)
    try:
        customer = Customer.objects.select_related("rfm_score").get(pk=customer_id)
    except Customer.DoesNotExist:
        return fail("مشتری پیدا نشد.", status=404)
    try:
        amount = int(request.GET.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0
    exclude_sale_id = request.GET.get("exclude_sale_id") or None
    if exclude_sale_id:
        try:
            exclude_sale_id = int(exclude_sale_id)
        except (TypeError, ValueError):
            exclude_sale_id = None
    return success(quote_cashback(customer, amount, exclude_sale_id=exclude_sale_id))

