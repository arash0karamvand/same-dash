"""رده‌بندی کارکنان بر اساس فروش — با تفکیک شعبه و حضور."""

from collections import defaultdict

from django.contrib.auth import get_user_model

from auth.branches import BRANCH_LABELS
from backend.models import Seller, StaffAttendance, StaffProfile
from logic.jalali import date_to_jalali
from logic.sales_day import apply_jalali_period

User = get_user_model()


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


def build_employee_ranking(qs, period, jy, jm=None, jd=None, branch=None):
    """لیست کارکنان مرتب‌شده بر اساس فروش — با تفکیک شعبه فروش و حضور."""
    qs = apply_jalali_period(qs, period, jy, jm=jm, jd=jd)

    user_branch_sales = defaultdict(lambda: defaultdict(lambda: {"count": 0, "total": 0}))
    user_totals = defaultdict(lambda: {"count": 0, "total": 0})

    for row in qs.values("recorded_by_id", "branch", "final_amount"):
        uid = row["recorded_by_id"]
        if not uid:
            continue
        sale_branch = row["branch"] or ""
        amount = int(row["final_amount"] or 0)
        user_branch_sales[uid][sale_branch]["count"] += 1
        user_branch_sales[uid][sale_branch]["total"] += amount
        user_totals[uid]["count"] += 1
        user_totals[uid]["total"] += amount

    if branch:
        ranked_ids = [
            uid
            for uid, branches in user_branch_sales.items()
            if branch in branches and branches[branch]["count"] > 0
        ]
        ranked_ids.sort(
            key=lambda uid: user_branch_sales[uid][branch]["total"],
            reverse=True,
        )
    else:
        ranked_ids = sorted(user_totals.keys(), key=lambda uid: -user_totals[uid]["total"])

    if not ranked_ids:
        return []

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

        if branch:
            branch_total = user_branch_sales[uid][branch]["total"]
            branch_count = user_branch_sales[uid][branch]["count"]
        else:
            branch_total = user_totals[uid]["total"]
            branch_count = user_totals[uid]["count"]

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
                "sale_count": branch_count,
                "total_final": branch_total,
                "total_all_branches": user_totals[uid]["total"],
                "sale_count_all_branches": user_totals[uid]["count"],
            }
        )
    return results
