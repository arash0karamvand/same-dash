"""یادآوری دوره‌ای باشگاه مشتریان — قابل تنظیم توسط مدیر."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from backend.models import Customer, ReminderCampaign, ReminderSendLog
from logic.membership import ensure_membership_code
from logic.sms import send_sms, _bulk_result
from logic.sms_club import render_template

TEMPLATE_VARS = ("name", "shop_name", "phone", "code", "level")


def _period_key(now=None):
    now = now or timezone.now()
    return now.strftime("%Y-%m")


def _add_months(dt, months):
    year = dt.year
    month = dt.month + months
    while month > 12:
        month -= 12
        year += 1
    while month <= 0:
        month += 12
        year -= 1
    day = min(dt.day, 28)
    return dt.replace(year=year, month=month, day=day)


def _months_ago(months, from_dt=None):
    return _add_months(from_dt or timezone.now(), -months)


def campaign_to_dict(campaign):
    levels = list(campaign.loyalty_levels.filter(is_active=True).values("id", "name", "color"))
    return {
        "id": campaign.id,
        "name": campaign.name,
        "is_enabled": campaign.is_enabled,
        "interval_months": campaign.interval_months,
        "message_template": campaign.message_template,
        "shop_name": campaign.shop_name,
        "level_ids": [l["id"] for l in levels],
        "levels": levels,
        "min_months_since_purchase": campaign.min_months_since_purchase,
        "last_run_at": campaign.last_run_at.isoformat() if campaign.last_run_at else None,
        "template_vars": list(TEMPLATE_VARS),
    }


def _eligible_customers(campaign):
    qs = Customer.objects.filter(is_active=True, is_deleted=False).select_related("level")
    level_ids = list(campaign.loyalty_levels.values_list("id", flat=True))
    if level_ids:
        qs = qs.filter(level_id__in=level_ids)
    if campaign.min_months_since_purchase:
        cutoff = _months_ago(campaign.min_months_since_purchase)
        qs = qs.filter(Q(last_purchase_at__lt=cutoff) | Q(last_purchase_at__isnull=True))
    return qs


def _already_sent_in_period(campaign, customer_id, period):
    return ReminderSendLog.objects.filter(
        campaign=campaign, customer_id=customer_id, period_key=period
    ).exists()


def _should_run_campaign(campaign, now=None):
    now = now or timezone.now()
    if not campaign.is_enabled:
        return False
    if not campaign.last_run_at:
        return True
    return now >= _add_months(campaign.last_run_at, campaign.interval_months)


def build_message(campaign, customer):
    ensure_membership_code(customer)
    return render_template(
        campaign.message_template,
        name=customer.full_name,
        shop_name=campaign.shop_name,
        phone=customer.phone,
        code=customer.membership_code,
        level=customer.level.name if customer.level_id else "—",
    )


def preview_campaign(campaign_id=None):
    campaigns = ReminderCampaign.objects.prefetch_related("loyalty_levels").all()
    if campaign_id:
        campaigns = campaigns.filter(pk=campaign_id)
    now = timezone.now()
    period = _period_key(now)
    previews = []
    for campaign in campaigns:
        recipients = []
        for customer in _eligible_customers(campaign):
            recipients.append(
                {
                    "customer_id": customer.id,
                    "full_name": customer.full_name,
                    "phone": customer.phone,
                    "level": customer.level.name if customer.level_id else "—",
                    "preview_message": build_message(campaign, customer),
                    "already_sent": _already_sent_in_period(campaign, customer.id, period),
                }
            )
        will_send = [r for r in recipients if not r["already_sent"]]
        previews.append(
            {
                **campaign_to_dict(campaign),
                "send_due": _should_run_campaign(campaign, now),
                "period_key": period,
                "total_eligible": len(recipients),
                "will_send_count": len(will_send),
                "recipients": recipients[:100],
            }
        )
    return previews


def run_campaign(campaign, user=None, force=False):
    now = timezone.now()
    period = _period_key(now)
    if not force and not _should_run_campaign(campaign, now):
        return {"successful": 0, "failed": 0, "skipped": 0, "results": [], "not_due": True}

    logs = []
    for customer in _eligible_customers(campaign):
        if _already_sent_in_period(campaign, customer.id, period) and not force:
            continue
        message = build_message(campaign, customer)
        log = send_sms(
            customer.phone,
            message,
            customer=customer,
            sms_type="reminder",
            user=user,
        )
        logs.append(log)
        if log.status != "failed":
            ReminderSendLog.objects.get_or_create(
                campaign=campaign,
                customer=customer,
                period_key=period,
            )

    campaign.last_run_at = now
    campaign.save(update_fields=["last_run_at", "updated_at"])
    result = _bulk_result(logs)
    result["not_due"] = False
    return result


def run_due_campaigns(user=None):
    results = []
    for campaign in ReminderCampaign.objects.filter(is_enabled=True).prefetch_related("loyalty_levels"):
        if _should_run_campaign(campaign):
            results.append({"campaign_id": campaign.id, **run_campaign(campaign, user=user)})
    return results
