"""موتور RFM — استخراج خام، امتیازدهی پنجک/آستانه، برچسب‌گذاری و پیامک اختیاری."""

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Max, Q, Sum
from django.utils import timezone
from django.utils.text import slugify

from backend.models import (
    Customer,
    CustomerRfmScore,
    RfmActionLog,
    RfmSegment,
    RfmSettings,
    Sale,
    SmsClubSettings,
)
from logic.sms import send_sms
from logic.sms_club import render_template

SCORE_MIN = 1
SCORE_MAX = 5

DEFAULT_SEGMENTS = [
    {
        "slug": "champions",
        "name": "قهرمانان",
        "color": "#b45309",
        "sort_order": 0,
        "description": "خرید اخیر، تکرار بالا و مبلغ زیاد — مشتریان اصلی گالری.",
        "r_scores": [5],
        "f_scores": [4, 5],
        "m_scores": [5],
        "action_type": RfmSegment.ACTION_VIP,
        "action_title": "دعوت VIP — بدون تخفیف",
        "action_body": (
            "به این گروه تخفیف ندهید. با ورود اکسسوری جدید (آباژور، میز عسلی و مشابه) "
            "دعوت‌نامه VIP بفرستید."
        ),
        "no_discount": True,
        "auto_sms": False,
        "sms_template": "{name} عزیز، مجموعه جدید اکسسوری {shop_name} با دعوت ویژه VIP آماده است.",
        "sms_cooldown_days": 90,
    },
    {
        "slug": "hibernating",
        "name": "خواب‌آلودهای سودآور",
        "color": "#0369a1",
        "sort_order": 1,
        "description": "قبلاً پرتکرار و پردرآمد بوده‌اند اما مدت‌هاست خرید نکرده‌اند.",
        "r_scores": [1, 2],
        "f_scores": [4, 5],
        "m_scores": [5],
        "action_type": RfmSegment.ACTION_CALL,
        "action_title": "تماس مستقیم تیم فروش",
        "action_body": (
            "تماس بگیرید. مشاوره رایگان تغییر دکوراسیون یا پیشنهاد تعویض مبلمان قدیمی "
            "می‌تواند آن‌ها را برگرداند."
        ),
        "no_discount": False,
        "auto_sms": False,
        "sms_template": "{name} عزیز، {shop_name} مشتاق دیدار دوباره شماست. برای مشاوره دکوراسیون آماده‌ایم.",
        "sms_cooldown_days": 90,
    },
    {
        "slug": "newcomers",
        "name": "تازه‌واردها",
        "color": "#15803d",
        "sort_order": 2,
        "description": "اولین خرید اخیر با مبلغ متوسط یا کم.",
        "r_scores": [5],
        "f_scores": [1],
        "m_scores": [1, 2],
        "action_type": RfmSegment.ACTION_SMS,
        "action_title": "پیامک تشکر و نظرسنجی",
        "action_body": (
            "پیامک تشکر و نظرسنجی رضایت بفرستید. پس از حدود یک ماه، محصول مکمل "
            "(مثلاً فرش هماهنگ با مبل) پیشنهاد شود."
        ),
        "no_discount": False,
        "auto_sms": False,
        "sms_template": "{name} عزیز، از خرید شما در {shop_name} سپاسگزاریم. نظر شما برای ما ارزشمند است.",
        "sms_cooldown_days": 30,
    },
]


def countable_sales_qs():
    """فروش‌های معتبر برای RFM (بدون لغو و پیش‌فاکتور در انتظار)."""
    return (
        Sale.objects.filter(is_deleted=False)
        .exclude(order_status=Sale.ORDER_STATUS_CANCELLED)
        .exclude(
            order_kind=Sale.ORDER_KIND_PRE_INVOICE,
            order_status=Sale.ORDER_STATUS_PENDING,
        )
    )


def seed_rfm_defaults():
    """تنظیمات و بخش‌های پیش‌فرض — فقط رکوردهای غایب را می‌سازد."""
    RfmSettings.get_solo()
    for spec in DEFAULT_SEGMENTS:
        RfmSegment.objects.get_or_create(slug=spec["slug"], defaults=spec)


def _clamp_score(value, bins=SCORE_MAX):
    try:
        score = int(value)
    except (TypeError, ValueError):
        return SCORE_MIN
    return max(SCORE_MIN, min(int(bins or SCORE_MAX), score))


def _normalize_score_list(values, bins=SCORE_MAX):
    if values in (None, "", []):
        return []
    if not isinstance(values, (list, tuple)):
        values = [values]
    out = []
    for item in values:
        try:
            score = _clamp_score(item, bins)
        except (TypeError, ValueError):
            continue
        if score not in out:
            out.append(score)
    return sorted(out)


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_decimal(value, default=Decimal("0")):
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def assign_quantile_scores(values, invert=False, bins=SCORE_MAX):
    """امتیاز ۱..bins بر اساس رتبه. invert=True یعنی مقدار کمتر امتیاز بیشتر (R)."""
    n_items = len(values)
    if n_items == 0:
        return []
    bins = max(2, min(10, int(bins or SCORE_MAX)))
    indexed = list(enumerate(values))
    indexed.sort(key=lambda item: item[1], reverse=not invert)
    scores = [SCORE_MIN] * n_items
    i = 0
    while i < n_items:
        j = i + 1
        while j < n_items and indexed[j][1] == indexed[i][1]:
            j += 1
        pct = i / n_items
        score = bins - int(pct * bins)
        score = max(SCORE_MIN, min(bins, score))
        for k in range(i, j):
            scores[indexed[k][0]] = score
        i = j
    return scores


def score_by_r_thresholds(days, thresholds):
    rows = sorted(
        thresholds or [],
        key=lambda item: (_as_int(item.get("score"), SCORE_MIN), -_as_int(item.get("max_days"), 0)),
        reverse=True,
    )
    for row in rows:
        if days <= _as_int(row.get("max_days"), 0):
            return _clamp_score(row.get("score"))
    return SCORE_MIN


def score_by_min_thresholds(value, thresholds, key):
    numeric = _as_decimal(value) if key == "min_amount" else _as_int(value)
    rows = sorted(
        thresholds or [],
        key=lambda item: _as_int(item.get("score"), SCORE_MIN),
        reverse=True,
    )
    for row in rows:
        cutoff = _as_decimal(row.get(key)) if key == "min_amount" else _as_int(row.get(key))
        if numeric >= cutoff:
            return _clamp_score(row.get("score"))
    return SCORE_MIN


def extract_raw_metrics(settings=None, now=None):
    """سه مقدار خام R/F/M برای هر مشتری دارای فروش شمارش‌پذیر."""
    settings = settings or RfmSettings.get_solo()
    now = now or timezone.now()
    recency_map = {
        row["customer_id"]: row["last_sold"]
        for row in countable_sales_qs().values("customer_id").annotate(last_sold=Max("sold_at"))
    }
    fm_qs = countable_sales_qs()
    if (settings.fm_window or RfmSettings.WINDOW_LOOKBACK) == RfmSettings.WINDOW_LOOKBACK:
        days = max(1, _as_int(settings.lookback_days, 730))
        fm_qs = fm_qs.filter(sold_at__gte=now - timedelta(days=days))
    amount_field = (
        settings.monetary_field
        if settings.monetary_field in (RfmSettings.MONETARY_FINAL, RfmSettings.MONETARY_PAID)
        else RfmSettings.MONETARY_FINAL
    )
    fm_map = {
        row["customer_id"]: row
        for row in fm_qs.values("customer_id").annotate(
            frequency=Count("id"),
            monetary=Sum(amount_field),
        )
    }
    active_ids = set(
        Customer.objects.filter(id__in=recency_map, is_active=True).values_list("id", flat=True)
    )
    rows = []
    today = timezone.localdate(now)
    for customer_id, last_sold in recency_map.items():
        if customer_id not in active_ids:
            continue
        last_date = timezone.localtime(last_sold).date() if last_sold else today
        fm = fm_map.get(customer_id) or {}
        rows.append(
            {
                "customer_id": customer_id,
                "r_raw": max(0, (today - last_date).days),
                "f_raw": int(fm.get("frequency") or 0),
                "m_raw": fm.get("monetary") or Decimal("0"),
                "last_purchase_at": last_sold,
            }
        )
    return rows


def _apply_scores(raw_rows, settings):
    bins = max(2, min(10, _as_int(settings.quantile_count, SCORE_MAX)))
    method = settings.score_method or RfmSettings.SCORE_METHOD_QUANTILE
    if method == RfmSettings.SCORE_METHOD_THRESHOLD:
        for row in raw_rows:
            row["r_score"] = score_by_r_thresholds(row["r_raw"], settings.r_thresholds)
            row["f_score"] = score_by_min_thresholds(row["f_raw"], settings.f_thresholds, "min_count")
            row["m_score"] = score_by_min_thresholds(row["m_raw"], settings.m_thresholds, "min_amount")
            row["rfm_code"] = f"{row['r_score']}{row['f_score']}{row['m_score']}"
        return raw_rows

    r_scores = assign_quantile_scores([row["r_raw"] for row in raw_rows], invert=True, bins=bins)
    f_scores = assign_quantile_scores([row["f_raw"] for row in raw_rows], invert=False, bins=bins)
    m_scores = assign_quantile_scores([row["m_raw"] for row in raw_rows], invert=False, bins=bins)
    for index, row in enumerate(raw_rows):
        row["r_score"] = r_scores[index]
        row["f_score"] = f_scores[index]
        row["m_score"] = m_scores[index]
        row["rfm_code"] = f"{row['r_score']}{row['f_score']}{row['m_score']}"
    return raw_rows


def segment_matches(segment, r_score, f_score, m_score):
    r_ok = not segment.r_scores or r_score in _normalize_score_list(segment.r_scores)
    f_ok = not segment.f_scores or f_score in _normalize_score_list(segment.f_scores)
    m_ok = not segment.m_scores or m_score in _normalize_score_list(segment.m_scores)
    return r_ok and f_ok and m_ok


def match_segment(r_score, f_score, m_score, segments):
    for segment in segments:
        if not segment.is_active:
            continue
        if segment_matches(segment, r_score, f_score, m_score):
            return segment
    return None


def settings_to_dict(settings=None):
    settings = settings or RfmSettings.get_solo()
    return {
        "lookback_days": settings.lookback_days,
        "score_method": settings.score_method,
        "score_method_label": settings.get_score_method_display(),
        "quantile_count": settings.quantile_count,
        "monetary_field": settings.monetary_field,
        "fm_window": settings.fm_window,
        "r_thresholds": settings.r_thresholds or [],
        "f_thresholds": settings.f_thresholds or [],
        "m_thresholds": settings.m_thresholds or [],
        "last_run_at": settings.last_run_at.isoformat() if settings.last_run_at else None,
        "last_run_stats": settings.last_run_stats or {},
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    }


def _clean_threshold_rows(rows, kind):
    cleaned = []
    if not isinstance(rows, list):
        return cleaned
    for row in rows:
        if not isinstance(row, dict):
            continue
        score = _clamp_score(row.get("score"))
        if kind == "r":
            cleaned.append({"max_days": max(0, _as_int(row.get("max_days"))), "score": score})
        elif kind == "f":
            cleaned.append({"min_count": max(0, _as_int(row.get("min_count"))), "score": score})
        else:
            cleaned.append({"min_amount": max(0, _as_int(row.get("min_amount"))), "score": score})
    return cleaned or None


def update_settings(data):
    settings = RfmSettings.get_solo()
    if "lookback_days" in data:
        settings.lookback_days = max(30, min(3650, _as_int(data.get("lookback_days"), 730)))
    if "score_method" in data:
        method = (data.get("score_method") or "").strip()
        if method not in (RfmSettings.SCORE_METHOD_QUANTILE, RfmSettings.SCORE_METHOD_THRESHOLD):
            raise ValueError("روش امتیاز نامعتبر است.")
        settings.score_method = method
    if "quantile_count" in data:
        settings.quantile_count = max(2, min(10, _as_int(data.get("quantile_count"), SCORE_MAX)))
    if "monetary_field" in data:
        field = (data.get("monetary_field") or "").strip()
        if field not in (RfmSettings.MONETARY_FINAL, RfmSettings.MONETARY_PAID):
            raise ValueError("منبع مبلغ نامعتبر است.")
        settings.monetary_field = field
    if "fm_window" in data:
        window = (data.get("fm_window") or "").strip()
        if window not in (RfmSettings.WINDOW_LOOKBACK, RfmSettings.WINDOW_LIFETIME):
            raise ValueError("بازهٔ F/M نامعتبر است.")
        settings.fm_window = window
    if "r_thresholds" in data:
        settings.r_thresholds = _clean_threshold_rows(data.get("r_thresholds"), "r") or settings.r_thresholds
    if "f_thresholds" in data:
        settings.f_thresholds = _clean_threshold_rows(data.get("f_thresholds"), "f") or settings.f_thresholds
    if "m_thresholds" in data:
        settings.m_thresholds = _clean_threshold_rows(data.get("m_thresholds"), "m") or settings.m_thresholds
    settings.save()
    return settings


def segment_to_dict(segment):
    return {
        "id": segment.id,
        "name": segment.name,
        "slug": segment.slug,
        "color": segment.color,
        "sort_order": segment.sort_order,
        "is_active": segment.is_active,
        "description": segment.description,
        "r_scores": _normalize_score_list(segment.r_scores),
        "f_scores": _normalize_score_list(segment.f_scores),
        "m_scores": _normalize_score_list(segment.m_scores),
        "action_type": segment.action_type,
        "action_type_label": segment.get_action_type_display(),
        "action_title": segment.action_title,
        "action_body": segment.action_body,
        "no_discount": segment.no_discount,
        "auto_sms": segment.auto_sms,
        "sms_template": segment.sms_template,
        "sms_cooldown_days": segment.sms_cooldown_days,
    }


def _unique_slug(name, exclude_id=None):
    base = slugify(name, allow_unicode=True) or "segment"
    slug = base[:40]
    suffix = 2
    qs = RfmSegment.objects.all()
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    while qs.filter(slug=slug).exists():
        slug = f"{base[:36]}-{suffix}"
        suffix += 1
    return slug


def _apply_segment_payload(segment, data, creating=False):
    if "name" in data or creating:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("نام بخش الزامی است.")
        segment.name = name
    if creating or "slug" in data:
        slug = (data.get("slug") or "").strip()
        segment.slug = slug or _unique_slug(segment.name, exclude_id=segment.pk)
    if "color" in data:
        segment.color = (data.get("color") or "#6366f1").strip() or "#6366f1"
    if "sort_order" in data:
        segment.sort_order = max(0, _as_int(data.get("sort_order")))
    if "is_active" in data:
        segment.is_active = bool(data.get("is_active"))
    if "description" in data:
        segment.description = (data.get("description") or "").strip()
    if "r_scores" in data or creating:
        segment.r_scores = _normalize_score_list(data.get("r_scores"))
    if "f_scores" in data or creating:
        segment.f_scores = _normalize_score_list(data.get("f_scores"))
    if "m_scores" in data or creating:
        segment.m_scores = _normalize_score_list(data.get("m_scores"))
    if "action_type" in data or creating:
        action = (data.get("action_type") or RfmSegment.ACTION_PLAYBOOK).strip()
        allowed = {choice[0] for choice in RfmSegment.ACTION_CHOICES}
        if action not in allowed:
            raise ValueError("نوع اکشن نامعتبر است.")
        segment.action_type = action
    if "action_title" in data:
        segment.action_title = (data.get("action_title") or "").strip()
    if "action_body" in data:
        segment.action_body = (data.get("action_body") or "").strip()
    if "no_discount" in data:
        segment.no_discount = bool(data.get("no_discount"))
    if "auto_sms" in data:
        segment.auto_sms = bool(data.get("auto_sms"))
    if "sms_template" in data:
        segment.sms_template = (data.get("sms_template") or "").strip()
    if "sms_cooldown_days" in data:
        segment.sms_cooldown_days = max(0, _as_int(data.get("sms_cooldown_days"), 90))
    return segment


def create_segment(data):
    segment = _apply_segment_payload(RfmSegment(), data, creating=True)
    segment.save()
    return segment


def update_segment(segment, data):
    _apply_segment_payload(segment, data, creating=False)
    segment.save()
    return segment


def score_to_dict(score):
    customer = score.customer
    segment = score.segment
    return {
        "id": score.id,
        "customer_id": customer.id,
        "full_name": customer.full_name,
        "phone": customer.phone,
        "membership_code": customer.membership_code or "",
        "r_raw": score.r_raw,
        "f_raw": score.f_raw,
        "m_raw": int(score.m_raw or 0),
        "r_score": score.r_score,
        "f_score": score.f_score,
        "m_score": score.m_score,
        "rfm_code": score.rfm_code,
        "last_purchase_at": score.last_purchase_at.isoformat() if score.last_purchase_at else None,
        "computed_at": score.computed_at.isoformat() if score.computed_at else None,
        "segment_id": segment.id if segment else None,
        "segment_name": segment.name if segment else "سایر",
        "segment_color": segment.color if segment else "#94a3b8",
        "action_type": segment.action_type if segment else RfmSegment.ACTION_PLAYBOOK,
        "action_title": segment.action_title if segment else "بدون اکشن تعریف‌شده",
        "action_body": segment.action_body if segment else "",
        "no_discount": bool(segment.no_discount) if segment else False,
        "auto_sms": bool(segment.auto_sms) if segment else False,
        "sms_template": segment.sms_template if segment else "",
    }


def list_scores(params):
    qs = CustomerRfmScore.objects.select_related("customer", "segment").order_by(
        "-m_raw", "r_raw", "customer_id"
    )
    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(Q(customer__full_name__icontains=search) | Q(customer__phone__icontains=search))
    segment_id = (params.get("segment_id") or "").strip()
    if segment_id in ("none", "other"):
        qs = qs.filter(segment__isnull=True)
    elif segment_id:
        qs = qs.filter(segment_id=segment_id)
    action_type = (params.get("action_type") or "").strip()
    if action_type:
        qs = qs.filter(segment__action_type=action_type)
    return qs


def build_summary():
    settings = RfmSettings.get_solo()
    seed_rfm_defaults()
    segments = list(RfmSegment.objects.all())
    counts = {
        row["segment_id"]: row["n"]
        for row in CustomerRfmScore.objects.values("segment_id").annotate(n=Count("id"))
    }
    total = sum(counts.values())
    unmatched = counts.get(None, 0)
    items = []
    for segment in segments:
        items.append(
            {
                **segment_to_dict(segment),
                "customer_count": counts.get(segment.id, 0),
            }
        )
    return {
        "settings": settings_to_dict(settings),
        "total": total,
        "unmatched": unmatched,
        "segments": items,
    }


def _sms_context(customer, segment, score_row):
    shop = SmsClubSettings.get_solo().shop_name
    return {
        "name": customer.full_name,
        "shop_name": shop,
        "phone": customer.phone,
        "code": customer.membership_code or "",
        "rfm": score_row.get("rfm_code", ""),
        "segment": segment.name if segment else "",
    }


def _cooldown_ok(customer_id, segment_id, cooldown_days, now):
    days = max(0, _as_int(cooldown_days, 90))
    since = now - timedelta(days=days or 1)
    return not RfmActionLog.objects.filter(
        customer_id=customer_id,
        segment_id=segment_id,
        action_type=RfmSegment.ACTION_SMS,
        sent_at__gte=since,
    ).exists()


def send_segment_sms(score, message=None, user=None, ignore_cooldown=False):
    """ارسال پیامک اکشن RFM برای یک مشتری امتیازدهی‌شده."""
    customer = score.customer if hasattr(score, "customer") else None
    if customer is None:
        raise ValueError("امتیاز RFM نامعتبر است.")
    segment = score.segment
    template = (message or (segment.sms_template if segment else "") or "").strip()
    if not template:
        raise ValueError("متن پیامک خالی است.")
    now = timezone.now()
    if (
        not ignore_cooldown
        and segment
        and not _cooldown_ok(customer.id, segment.id, segment.sms_cooldown_days, now)
    ):
        return {"skipped": True, "reason": "cooldown"}
    ctx = _sms_context(
        customer,
        segment,
        {
            "rfm_code": score.rfm_code,
        },
    )
    log = send_sms(
        customer.phone,
        render_template(template, **ctx),
        customer=customer,
        sms_type="rfm",
        user=user,
    )
    RfmActionLog.objects.create(
        customer=customer,
        segment=segment,
        action_type=RfmSegment.ACTION_SMS,
        sms_log=log,
    )
    return {
        "skipped": False,
        "status": log.status,
        "sms_id": log.id,
    }


def _send_auto_sms(scored_rows, segments_by_id, now):
    sent = 0
    skipped = 0
    failed = 0
    customer_ids = [row["customer_id"] for row in scored_rows if row.get("segment_id")]
    customers = {
        item.id: item
        for item in Customer.objects.filter(id__in=customer_ids)
    }
    for row in scored_rows:
        segment = segments_by_id.get(row.get("segment_id"))
        if not segment or not segment.auto_sms or not (segment.sms_template or "").strip():
            continue
        if not _cooldown_ok(row["customer_id"], segment.id, segment.sms_cooldown_days, now):
            skipped += 1
            continue
        customer = customers.get(row["customer_id"])
        if customer is None:
            skipped += 1
            continue
        try:
            log = send_sms(
                customer.phone,
                render_template(segment.sms_template, **_sms_context(customer, segment, row)),
                customer=customer,
                sms_type="rfm",
            )
            RfmActionLog.objects.create(
                customer=customer,
                segment=segment,
                action_type=RfmSegment.ACTION_SMS,
                sms_log=log,
            )
            if log.status in ("failed",):
                failed += 1
            else:
                sent += 1
        except Exception:
            failed += 1
    return {"sms_sent": sent, "sms_skipped": skipped, "sms_failed": failed}


def recalculate_all_rfm(send_actions=True, now=None):
    """محاسبهٔ کامل RFM، به‌روزرسانی کش، و ارسال پیامک بخش‌های auto_sms."""
    seed_rfm_defaults()
    settings = RfmSettings.get_solo()
    now = now or timezone.now()
    raw_rows = extract_raw_metrics(settings, now=now)
    scored = _apply_scores(raw_rows, settings)
    segments = list(RfmSegment.objects.filter(is_active=True).order_by("sort_order", "id"))
    unmatched = 0
    for row in scored:
        segment = match_segment(row["r_score"], row["f_score"], row["m_score"], segments)
        row["segment_id"] = segment.id if segment else None
        if segment is None:
            unmatched += 1

    existing = {item.customer_id: item for item in CustomerRfmScore.objects.all()}
    to_create = []
    to_update = []
    seen = set()
    for row in scored:
        seen.add(row["customer_id"])
        obj = existing.get(row["customer_id"])
        if obj is None:
            to_create.append(
                CustomerRfmScore(
                    customer_id=row["customer_id"],
                    r_raw=row["r_raw"],
                    f_raw=row["f_raw"],
                    m_raw=row["m_raw"],
                    r_score=row["r_score"],
                    f_score=row["f_score"],
                    m_score=row["m_score"],
                    rfm_code=row["rfm_code"],
                    last_purchase_at=row["last_purchase_at"],
                    segment_id=row["segment_id"],
                    computed_at=now,
                )
            )
            continue
        obj.r_raw = row["r_raw"]
        obj.f_raw = row["f_raw"]
        obj.m_raw = row["m_raw"]
        obj.r_score = row["r_score"]
        obj.f_score = row["f_score"]
        obj.m_score = row["m_score"]
        obj.rfm_code = row["rfm_code"]
        obj.last_purchase_at = row["last_purchase_at"]
        obj.segment_id = row["segment_id"]
        obj.computed_at = now
        to_update.append(obj)

    CustomerRfmScore.objects.bulk_create(to_create, batch_size=500)
    if to_update:
        CustomerRfmScore.objects.bulk_update(
            to_update,
            [
                "r_raw",
                "f_raw",
                "m_raw",
                "r_score",
                "f_score",
                "m_score",
                "rfm_code",
                "last_purchase_at",
                "segment_id",
                "computed_at",
            ],
            batch_size=500,
        )
    CustomerRfmScore.objects.exclude(customer_id__in=seen).delete()

    sms_stats = {"sms_sent": 0, "sms_skipped": 0, "sms_failed": 0}
    if send_actions:
        segments_by_id = {item.id: item for item in segments}
        sms_stats = _send_auto_sms(scored, segments_by_id, now)

    stats = {
        "scored": len(scored),
        "unmatched": unmatched,
        **sms_stats,
    }
    settings.last_run_at = now
    settings.last_run_stats = stats
    settings.save(update_fields=["last_run_at", "last_run_stats", "updated_at"])
    return stats
