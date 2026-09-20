"""رده‌بندی کارکنان بر اساس فروش — با تفکیک شعبه، تخفیف و حضور."""

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone

from auth.branches import BRANCH_LABELS
from backend.models import JournalEntry, Sale, Seller, StaffAttendance, StaffProfile
from logic.jalali import date_to_jalali
from logic.ranking_settings import get_ranking_settings
from logic.sales_day import apply_jalali_period

User = get_user_model()

SELLER_DISCOUNT_TYPES = frozenset({"percent", "amount"})


def _branch_label(code):
    if not code:
        return "بدون شعبه"
    return BRANCH_LABELS.get(code, code)


def _in_jalali_period(period, ay, am, ad, jy, jm, jd):
    if period == "day":
        return (ay, am, ad) == (jy, jm, jd)
    if period == "month":
        return ay == jy and am == jm
    if period == "year":
        return ay == jy
    return False


def _user_label(user):
    if not user:
        return "—"
    name = user.get_full_name() or user.username
    return name.strip() or user.username


def _as_local_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _delivery_cutoff(delivery_date, delivery_ready_at):
    if delivery_date:
        return _as_local_date(delivery_date)
    return _as_local_date(delivery_ready_at)


def _to_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _avg_percent(discount, gross):
    if gross <= 0:
        return 0.0
    return round((Decimal(discount) / Decimal(gross)) * Decimal("100"), 2)


def _norm_map(values_by_id):
    if not values_by_id:
        return {}
    lo = min(values_by_id.values())
    hi = max(values_by_id.values())
    span = hi - lo
    if span == 0:
        return {uid: 0.0 for uid in values_by_id}
    return {uid: (value - lo) / span for uid, value in values_by_id.items()}


def _empty_stats():
    return {"count": 0, "total": 0, "gross": 0, "discount": 0, "pre_delivery": 0}


def _attendance_by_user(user_ids, period, jy, jm, jd):
    """شعب حضور تأییدشده هر کاربر در بازه."""
    sellers = Seller.objects.filter(user_id__in=user_ids)
    seller_user = {s.id: s.user_id for s in sellers}
    if not seller_user:
        return {}

    by_user = defaultdict(lambda: defaultdict(int))
    for att in StaffAttendance.objects.filter(
        seller_id__in=seller_user.keys(),
        status="present",
        approval_status="approved",
    ).select_related("seller"):
        uid = seller_user.get(att.seller_id)
        if not uid:
            continue
        ay, am, ad = date_to_jalali(att.date)
        if not _in_jalali_period(period, ay, am, ad, jy, jm, jd):
            continue
        branch = att.work_branch_id or att.seller.branch_id or ""
        by_user[uid][branch] += 1
    return by_user


def _branch_rows(counter_map):
    rows = []
    for branch, count in counter_map.items():
        rows.append(
            {
                "branch": branch,
                "branch_label": _branch_label(branch),
                "days": count,
            }
        )
    rows.sort(key=lambda r: (-r["days"], r["branch_label"]))
    return rows


def _sales_branch_rows(branch_stats):
    rows = []
    for branch, stats in branch_stats.items():
        rows.append(
            {
                "branch": branch,
                "branch_label": _branch_label(branch),
                "sale_count": stats["count"],
                "total_final": stats["total"],
            }
        )
    rows.sort(key=lambda r: (-r["total_final"], -r["sale_count"]))
    return rows


def _payment_rows_by_sale(sale_ids):
    """اسناد دریافت هر فروش: تاریخ و مبلغ."""
    if not sale_ids:
        return {}
    journals = (
        JournalEntry.objects.filter(
            order_links__order_id__in=sale_ids,
            entry_type="payment",
        )
        .exclude(status=JournalEntry.STATUS_VOID)
        .annotate(amount=Sum("lines__debit"))
        .values("id", "entry_date", "amount", "order_links__order_id")
    )
    by_sale = defaultdict(list)
    for row in journals:
        sale_id = row["order_links__order_id"]
        amount = _to_int(row["amount"])
        if amount <= 0:
            continue
        by_sale[sale_id].append((_as_local_date(row["entry_date"]), amount))
    return by_sale


def _pre_delivery_for_sale(row, payments):
    paid = _to_int(row["paid_amount"])
    if paid <= 0:
        return 0
    cutoff = _delivery_cutoff(row["delivery_date"], row["delivery_ready_at"])
    if not payments:
        return paid
    collected = 0
    for pay_date, amount in payments:
        if cutoff is None or (pay_date is not None and pay_date <= cutoff):
            collected += amount
    if collected > paid:
        return paid
    return collected


def _add_sale_stats(stats, *, count=1, total=0, gross=0, discount=0, pre_delivery=0):
    stats["count"] += count
    stats["total"] += total
    stats["gross"] += gross
    stats["discount"] += discount
    stats["pre_delivery"] += pre_delivery


def build_employee_ranking(qs, period, jy, jm=None, jd=None, branch=None, weights=None):
    """لیست کارکنان مرتب‌شده با فروش، تخفیف و دریافت قبل از تحویل."""
    qs = apply_jalali_period(qs, period, jy, jm=jm, jd=jd)
    qs = qs.exclude(order_status=Sale.ORDER_STATUS_CANCELLED)

    sale_rows = list(
        qs.values(
            "id",
            "recorded_by_id",
            "branch",
            "final_amount",
            "amount",
            "discount",
            "discount_type",
            "paid_amount",
            "delivery_date",
            "delivery_ready_at",
        )
    )
    payments_by_sale = _payment_rows_by_sale(
        [row["id"] for row in sale_rows if row.get("id")]
    )

    user_branch_sales = defaultdict(lambda: defaultdict(_empty_stats))
    user_totals = defaultdict(_empty_stats)

    for row in sale_rows:
        uid = row["recorded_by_id"]
        if not uid:
            continue
        sale_branch = row["branch"] or ""
        total = _to_int(row["final_amount"])
        is_seller_discount = (row["discount_type"] or "") in SELLER_DISCOUNT_TYPES
        gross = _to_int(row["amount"]) if is_seller_discount else 0
        discount = _to_int(row["discount"]) if is_seller_discount else 0
        pre_delivery = _pre_delivery_for_sale(row, payments_by_sale.get(row["id"], []))
        payload = {
            "count": 1,
            "total": total,
            "gross": gross,
            "discount": discount,
            "pre_delivery": pre_delivery,
        }
        _add_sale_stats(user_branch_sales[uid][sale_branch], **payload)
        _add_sale_stats(user_totals[uid], **payload)

    if branch:
        ranked_ids = [
            uid
            for uid, branches in user_branch_sales.items()
            if branch in branches and branches[branch]["count"] > 0
        ]
        rank_stats = {uid: user_branch_sales[uid][branch] for uid in ranked_ids}
    else:
        ranked_ids = list(user_totals.keys())
        rank_stats = {uid: user_totals[uid] for uid in ranked_ids}

    if not ranked_ids:
        return []

    weights = dict(weights or get_ranking_settings())
    sales_norm = _norm_map({uid: rank_stats[uid]["total"] for uid in ranked_ids})
    prepay_norm = _norm_map({uid: rank_stats[uid]["pre_delivery"] for uid in ranked_ids})
    discount_pct_norm = _norm_map(
        {
            uid: float(_avg_percent(rank_stats[uid]["discount"], rank_stats[uid]["gross"]))
            for uid in ranked_ids
        }
    )
    discount_rial_norm = _norm_map({uid: rank_stats[uid]["discount"] for uid in ranked_ids})

    w_sales = weights.get("sales") or 0
    w_prepay = weights.get("pre_delivery") or 0
    w_discount_pct = weights.get("discount_percent") or 0
    w_discount_rial = weights.get("discount_rial") or 0
    weight_sum = w_sales + w_prepay + w_discount_pct + w_discount_rial

    scores = {}
    for uid in ranked_ids:
        if weight_sum <= 0:
            scores[uid] = float(rank_stats[uid]["total"])
            continue
        score = (
            w_sales * sales_norm[uid]
            + w_prepay * prepay_norm[uid]
            + w_discount_pct * (1 - discount_pct_norm[uid])
            + w_discount_rial * (1 - discount_rial_norm[uid])
        )
        scores[uid] = round(score, 4)

    ranked_ids.sort(
        key=lambda uid: (-scores[uid], -rank_stats[uid]["total"], uid),
    )

    users = {
        u.id: u
        for u in User.objects.filter(pk__in=ranked_ids).only(
            "id", "username", "first_name", "last_name"
        )
    }
    profiles = {
        p.user_id: p
        for p in StaffProfile.objects.filter(user_id__in=ranked_ids).select_related("org_rank")
    }
    attendance_map = _attendance_by_user(ranked_ids, period, jy, jm, jd)

    results = []
    for rank, uid in enumerate(ranked_ids, start=1):
        user = users.get(uid)
        profile = profiles.get(uid)
        home_branch = profile.branch_id if profile else ""
        sales_rows = _sales_branch_rows(user_branch_sales[uid])
        att_rows = _branch_rows(attendance_map.get(uid, {}))
        stats = rank_stats[uid]

        results.append(
            {
                "rank": rank,
                "user_id": uid,
                "full_name": _user_label(user),
                "username": user.username if user else "",
                "home_branch": home_branch,
                "home_branch_label": _branch_label(home_branch),
                "job_title": profile.job_title if profile else "",
                "org_rank_name": profile.org_rank.name if profile and profile.org_rank_id else "",
                "attendance_branches": att_rows,
                "sales_by_branch": sales_rows,
                "sale_count": stats["count"],
                "total_final": stats["total"],
                "total_discount": stats["discount"],
                "avg_discount_percent": float(_avg_percent(stats["discount"], stats["gross"])),
                "pre_delivery_paid": stats["pre_delivery"],
                "score": round(float(scores[uid]), 2),
                "total_all_branches": user_totals[uid]["total"],
                "sale_count_all_branches": user_totals[uid]["count"],
            }
        )
    return results
