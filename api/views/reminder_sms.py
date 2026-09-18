"""کمپین‌های یادآوری دوره‌ای — فقط مدیر."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import MANAGE_REMINDERS, has_permission
from backend.models import ReminderCampaign
from logic.audit import log_action
from logic.reminder_sms import (
    _set_campaign_segments,
    campaign_to_dict,
    preview_campaign,
    run_campaign,
    run_due_campaigns,
)


@api_view("GET", "POST")
def reminder_list(request):
    if not has_permission(request.user, MANAGE_REMINDERS):
        return fail("Permission denied", status=403)

    if request.method == "GET":
        campaigns = ReminderCampaign.objects.prefetch_related("rfm_segments").order_by("name")
        return success({"results": [campaign_to_dict(c) for c in campaigns]})

    data = parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return fail("نام کمپین الزامی است.", status=400)
    interval = int(data.get("interval_months") or 3)
    if interval < 1 or interval > 24:
        return fail("بازه باید بین ۱ تا ۲۴ ماه باشد.", status=400)

    campaign = ReminderCampaign.objects.create(
        name=name,
        is_enabled=bool(data.get("is_enabled", True)),
        interval_months=interval,
        message_template=(data.get("message_template") or "").strip()
        or ReminderCampaign._meta.get_field("message_template").default,
        shop_name=(data.get("shop_name") or "سام اکسون").strip()[:100],
        min_months_since_purchase=data.get("min_months_since_purchase") or None,
    )
    segment_ids = data.get("segment_ids") or data.get("level_ids") or []
    _set_campaign_segments(campaign, segment_ids)
    log_action(
        request.user,
        "create",
        f"کمپین یادآوری: {name}",
        entity_type="ReminderCampaign",
        entity_id=campaign.id,
    )
    return success(campaign_to_dict(campaign), status=201)


@api_view("GET", "PUT", "DELETE")
def reminder_detail(request, pk):
    if not has_permission(request.user, MANAGE_REMINDERS):
        return fail("Permission denied", status=403)
    try:
        campaign = ReminderCampaign.objects.prefetch_related("rfm_segments").get(pk=pk)
    except ReminderCampaign.DoesNotExist:
        return fail("کمپین یافت نشد.", status=404)

    if request.method == "GET":
        return success(campaign_to_dict(campaign))

    if request.method == "DELETE":
        campaign.delete()
        log_action(request.user, "delete", f"حذف کمپین یادآوری {pk}", entity_type="ReminderCampaign")
        return success({"deleted": True})

    data = parse_json(request)
    if "name" in data:
        campaign.name = (data.get("name") or campaign.name).strip()
    if "is_enabled" in data:
        campaign.is_enabled = bool(data.get("is_enabled"))
    if "interval_months" in data:
        campaign.interval_months = max(1, min(24, int(data.get("interval_months") or 3)))
    if "message_template" in data:
        tpl = (data.get("message_template") or "").strip()
        if tpl:
            campaign.message_template = tpl
    if "shop_name" in data:
        campaign.shop_name = (data.get("shop_name") or campaign.shop_name).strip()[:100]
    if "min_months_since_purchase" in data:
        raw = data.get("min_months_since_purchase")
        campaign.min_months_since_purchase = int(raw) if raw else None
    if "level_ids" in data or "segment_ids" in data:
        _set_campaign_segments(campaign, data.get("segment_ids") or data.get("level_ids") or [])
    campaign.save()
    return success(campaign_to_dict(campaign))


@api_view("GET")
def reminder_preview(request):
    if not has_permission(request.user, MANAGE_REMINDERS):
        return fail("Permission denied", status=403)
    campaign_id = request.GET.get("campaign_id")
    auto = request.GET.get("auto") == "1"
    previews = preview_campaign(int(campaign_id) if campaign_id else None)
    auto_results = run_due_campaigns(user=request.user) if auto else None
    return success({"campaigns": previews, "auto_results": auto_results})


@api_view("POST")
def reminder_send(request, pk):
    if not has_permission(request.user, MANAGE_REMINDERS):
        return fail("Permission denied", status=403)
    try:
        campaign = ReminderCampaign.objects.prefetch_related("rfm_segments").get(pk=pk)
    except ReminderCampaign.DoesNotExist:
        return fail("کمپین یافت نشد.", status=404)
    data = parse_json(request) or {}
    force = bool(data.get("force"))
    result = run_campaign(campaign, user=request.user, force=force)
    log_action(
        request.user,
        "sms",
        f"ارسال یادآوری {campaign.name}: {result.get('successful', 0)} موفق",
        entity_type="ReminderCampaign",
        entity_id=campaign.id,
    )
    return success(result)
