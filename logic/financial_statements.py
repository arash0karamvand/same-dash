"""ترازنامه، صورت سود و زیان و تراز آزمایشی با تجمیع در دیتابیس.

گردش هر حساب با یک ``Sum`` گروهی حساب می‌شود. ردیف سند به پایتون نمی‌آید؛
جمع‌ها روی درخت حساب (کل / معین / تفصیلی) در حافظهٔ کوچک دفتر کل بالا می‌روند.
"""

from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date

from backend.models import Account, JournalEntry, JournalLine
from logic.accounting_ledger import ledger_totals
from logic.chart_of_accounts import ACCOUNT_CLASS_LABELS
from logic.giant_books.classify import bucket
from logic.ledger import OFFICE_LEDGER

MONEY = DecimalField(max_digits=18, decimal_places=0)


def _zero():
    return Value(Decimal("0"), output_field=MONEY)
MOVEMENT_KEYS = ("opening_debit", "opening_credit", "turnover_debit", "turnover_credit")
LEVEL_DEPTH = {"general": 0, "subsidiary": 1, "detailed": 2}

SECTION_BUCKETS = {
    "assets": ("cash", "operating_asset", "investing_asset"),
    "liabilities": ("operating_liability", "financing_liability"),
    "equity": ("equity",),
    "revenue": ("revenue",),
    "expense": ("expense",),
}
SECTION_LABELS = {
    "assets": "دارایی‌ها",
    "liabilities": "بدهی‌ها",
    "equity": "حقوق صاحبان سهام",
    "revenue": "درآمدها",
    "expense": "هزینه‌ها",
}
BUCKET_LABELS = {
    "cash": "موجودی نقد",
    "operating_asset": "دارایی‌های عملیاتی",
    "investing_asset": "دارایی‌های سرمایه‌ای",
    "operating_liability": "بدهی‌های عملیاتی",
    "financing_liability": "بدهی‌های تأمین مالی",
    "equity": "سرمایه",
    "revenue": "درآمد",
    "expense": "هزینه",
}


def coerce_date(value, label="تاریخ"):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value
    parsed = parse_date(str(value).strip())
    if parsed is None:
        raise ValueError(f"{label} نامعتبر است.")
    return parsed


def _day_start(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _next_day(day):
    return _day_start(day + timedelta(days=1))


def _sum(field, condition=None):
    if condition is None:
        total = Sum(field, output_field=MONEY)
    else:
        total = Sum(field, filter=condition, output_field=MONEY)
    return Coalesce(total, _zero())


def _line_queryset(ledger, *, date_to=None, approved_only=True):
    qs = JournalLine.objects.filter(journal__ledger__code=ledger.id)
    if approved_only:
        qs = qs.filter(journal__status_ref_id=JournalEntry.STATUS_POSTED)
    else:
        qs = qs.exclude(journal__status_ref_id=JournalEntry.STATUS_VOID)
    if date_to:
        qs = qs.filter(journal__entry_date__lt=_next_day(date_to))
    return qs


def aggregate_account_movements(ledger, *, date_from=None, date_to=None, approved_only=True):
    """یک ردیف برای هر حسابِ دارای سند: مانده اول دوره و گردش دوره."""
    qs = _line_queryset(ledger, date_to=date_to, approved_only=approved_only)
    if date_from:
        opening = Q(journal__entry_date__lt=_day_start(date_from))
        period = Q(journal__entry_date__gte=_day_start(date_from))
        annotations = {
            "opening_debit": _sum("debit", opening),
            "opening_credit": _sum("credit", opening),
            "turnover_debit": _sum("debit", period),
            "turnover_credit": _sum("credit", period),
        }
    else:
        annotations = {
            "opening_debit": _zero(),
            "opening_credit": _zero(),
            "turnover_debit": _sum("debit"),
            "turnover_credit": _sum("credit"),
        }
    rows = qs.values("account_id").annotate(**annotations)
    return {
        row["account_id"]: {key: int(row[key] or 0) for key in MOVEMENT_KEYS}
        for row in rows
    }


def load_accounts(ledger):
    return list(
        Account.objects.filter(ledger__code=ledger.id).values(
            "id", "parent_id", "code", "path", "name", "slug",
            "account_class", "normal_balance", "sort_order", "is_active",
        )
    )


def _zeros():
    return {key: 0 for key in MOVEMENT_KEYS}


def rollup_movements(accounts, movements):
    """جمع هر حساب به‌علاوهٔ همهٔ زیرحساب‌ها، بدون خواندن ردیف سند."""
    children = defaultdict(list)
    for account in accounts:
        children[account["parent_id"]].append(account["id"])
    cache = {}

    def rolled(account_id):
        cached = cache.get(account_id)
        if cached is not None:
            return cached
        total = dict(movements.get(account_id) or _zeros())
        for child_id in children.get(account_id, ()):
            child = rolled(child_id)
            for key in MOVEMENT_KEYS:
                total[key] += child[key]
        cache[account_id] = total
        return total

    for account in accounts:
        rolled(account["id"])
    return cache


def _index_accounts(accounts):
    by_id = {account["id"]: account for account in accounts}
    depths = {}

    def depth(account_id):
        if account_id in depths:
            return depths[account_id]
        parent_id = by_id[account_id]["parent_id"]
        depths[account_id] = 0 if not parent_id else depth(parent_id) + 1
        return depths[account_id]

    for account in accounts:
        depth(account["id"])
    return by_id, depths


def _is_under(account_id, ancestor_id, by_id):
    current = account_id
    seen = set()
    while current and current not in seen:
        if current == ancestor_id:
            return True
        seen.add(current)
        current = by_id.get(current, {}).get("parent_id")
    return False


def _split(debit, credit):
    net = int(debit) - int(credit)
    if net >= 0:
        return net, 0
    return 0, -net


def _signed(account, debit, credit):
    amount = int(debit) - int(credit)
    if account["normal_balance"] == "credit":
        amount = -amount
    return amount


def _cumulative(amounts):
    return (
        amounts["opening_debit"] + amounts["turnover_debit"],
        amounts["opening_credit"] + amounts["turnover_credit"],
    )


class StatementBooks:
    """دو کوئری مشترک برای هر سه گزارش."""

    def __init__(self, ledger, *, date_from=None, date_to=None, approved_only=True):
        self.ledger = ledger
        self.date_from = coerce_date(date_from, "تاریخ شروع")
        self.date_to = coerce_date(date_to, "تاریخ پایان")
        self.approved_only = approved_only
        self.movements = aggregate_account_movements(
            ledger,
            date_from=self.date_from,
            date_to=self.date_to,
            approved_only=approved_only,
        )
        self.accounts = load_accounts(ledger)
        self.rolled = rollup_movements(self.accounts, self.movements)
        self.by_id, self.depths = _index_accounts(self.accounts)

    def iso_from(self):
        return self.date_from.isoformat() if self.date_from else None

    def iso_to(self):
        return self.date_to.isoformat() if self.date_to else None


def trial_balance_report(
    ledger=OFFICE_LEDGER,
    *,
    date_from=None,
    date_to=None,
    account_class=None,
    account_id=None,
    subsidiary_id=None,
    approved_only=False,
    level="general",
    include_zero=True,
    books=None,
):
    if level not in LEVEL_DEPTH:
        level = "general"
    books = books or StatementBooks(
        ledger, date_from=date_from, date_to=date_to, approved_only=approved_only,
    )
    depth = LEVEL_DEPTH[level]
    selected = []
    for account in books.accounts:
        if not account["is_active"] or books.depths[account["id"]] != depth:
            continue
        if account_class and account["account_class"] != account_class:
            continue
        if account_id and not _is_under(account["id"], account_id, books.by_id):
            continue
        if subsidiary_id and not _is_under(account["id"], subsidiary_id, books.by_id):
            continue
        selected.append(account)
    selected.sort(key=lambda account: (account["sort_order"], account["code"]))

    rows = []
    for account in selected:
        amounts = books.rolled[account["id"]]
        opening_debit, opening_credit = _split(amounts["opening_debit"], amounts["opening_credit"])
        balance_debit, balance_credit = _split(*_cumulative(amounts))
        if (
            not include_zero
            and not any((
                opening_debit, opening_credit, amounts["turnover_debit"], amounts["turnover_credit"],
                balance_debit, balance_credit,
            ))
        ):
            continue
        row = {
            "account_code": account["path"],
            "account_name": account["name"],
            "account_class": account["account_class"],
            "account_class_label": ACCOUNT_CLASS_LABELS.get(
                account["account_class"], account["account_class"],
            ),
            "opening_debit": opening_debit,
            "opening_credit": opening_credit,
            "turnover_debit": amounts["turnover_debit"],
            "turnover_credit": amounts["turnover_credit"],
            "balance_debit": balance_debit,
            "balance_credit": balance_credit,
        }
        if depth == 0:
            row["account_id"] = account["id"]
        elif depth == 1:
            row.update(subsidiary_id=account["id"], account_id=account["parent_id"])
        else:
            parent = books.by_id[account["parent_id"]]
            row.update(
                detailed_id=account["id"],
                subsidiary_id=account["parent_id"],
                account_id=parent["parent_id"],
            )
        rows.append(row)

    totals = ledger_totals(rows)
    raw_debit = sum(item["turnover_debit"] for item in books.movements.values())
    raw_credit = sum(item["turnover_credit"] for item in books.movements.values())
    totals.update(
        raw_turnover_debit=raw_debit,
        raw_turnover_credit=raw_credit,
        turnover_balanced=raw_debit == raw_credit,
    )
    return rows, totals


def _statement_rows(books, *, period, buckets):
    rows = []
    for account in books.accounts:
        if not account["is_active"] or books.depths[account["id"]] != 0:
            continue
        amounts = books.rolled[account["id"]]
        if period:
            debit, credit = amounts["turnover_debit"], amounts["turnover_credit"]
        else:
            debit, credit = _cumulative(amounts)
        if debit == 0 and credit == 0:
            continue
        name = bucket(account["account_class"], account["slug"], account["path"], account["code"])
        if name not in buckets:
            continue
        balance = _signed(account, debit, credit)
        if balance == 0 and debit == 0 and credit == 0:
            continue
        rows.append({
            "account_id": account["id"],
            "code": account["path"],
            "name": account["name"],
            "bucket": name,
            "balance": balance,
        })
    rows.sort(key=lambda row: row["code"])
    return rows


def _groups(rows, buckets):
    groups = []
    for name in buckets:
        grouped = [row for row in rows if row["bucket"] == name]
        if not grouped:
            continue
        groups.append({
            "key": name,
            "label": BUCKET_LABELS.get(name, name),
            "rows": [
                {"account_id": row["account_id"], "code": row["code"], "name": row["name"], "balance": row["balance"]}
                for row in grouped
            ],
            "total": sum(row["balance"] for row in grouped),
        })
    return groups


def income_statement_report(
    ledger=OFFICE_LEDGER, *, date_from=None, date_to=None, approved_only=True, books=None,
):
    books = books or StatementBooks(
        ledger, date_from=date_from, date_to=date_to, approved_only=approved_only,
    )
    revenue = _statement_rows(books, period=True, buckets=SECTION_BUCKETS["revenue"])
    expenses = _statement_rows(books, period=True, buckets=SECTION_BUCKETS["expense"])
    revenue_total = sum(row["balance"] for row in revenue)
    expense_total = sum(row["balance"] for row in expenses)
    return {
        "date_from": books.iso_from(),
        "date_to": books.iso_to(),
        "sections": [
            {
                "key": "revenue",
                "label": SECTION_LABELS["revenue"],
                "groups": _groups(revenue, SECTION_BUCKETS["revenue"]),
                "total": revenue_total,
            },
            {
                "key": "expense",
                "label": SECTION_LABELS["expense"],
                "groups": _groups(expenses, SECTION_BUCKETS["expense"]),
                "total": expense_total,
            },
        ],
        "revenue_total": revenue_total,
        "expense_total": expense_total,
        "net_income": revenue_total - expense_total,
    }


def _unclosed_income(books):
    """سود و زیان انباشتهٔ بسته‌نشده تا پایان بازه؛ رقم ترازکنندهٔ ترازنامه."""
    revenue = _statement_rows(books, period=False, buckets=SECTION_BUCKETS["revenue"])
    expenses = _statement_rows(books, period=False, buckets=SECTION_BUCKETS["expense"])
    return sum(row["balance"] for row in revenue) - sum(row["balance"] for row in expenses)


def balance_sheet_report(
    ledger=OFFICE_LEDGER, *, date_from=None, date_to=None, approved_only=True, books=None,
):
    books = books or StatementBooks(
        ledger, date_from=date_from, date_to=date_to, approved_only=approved_only,
    )
    net_income = _unclosed_income(books)
    sections = []
    totals = {}
    for key in ("assets", "liabilities", "equity"):
        rows = _statement_rows(books, period=False, buckets=SECTION_BUCKETS[key])
        total = sum(row["balance"] for row in rows)
        totals[key] = total
        sections.append({
            "key": key,
            "label": SECTION_LABELS[key],
            "groups": _groups(rows, SECTION_BUCKETS[key]),
            "total": total,
        })
    liabilities_and_equity = totals["liabilities"] + totals["equity"] + net_income
    return {
        "as_of": books.iso_to(),
        "sections": sections,
        "asset_total": totals["assets"],
        "liability_total": totals["liabilities"],
        "equity_total": totals["equity"],
        "net_income": net_income,
        "unclosed_result": {
            "label": "سود (زیان) خالص بسته‌نشده",
            "balance": net_income,
        },
        "liabilities_and_equity": liabilities_and_equity,
        "balanced": totals["assets"] == liabilities_and_equity,
    }


def management_statements(
    ledger=OFFICE_LEDGER,
    *,
    date_from=None,
    date_to=None,
    approved_only=True,
    level="general",
):
    """هر سه گزارش از یک تصویر تجمیعی، برای یک بار لود داشبورد."""
    date_from = coerce_date(date_from, "تاریخ شروع")
    date_to = coerce_date(date_to, "تاریخ پایان")
    if date_from and date_to and date_from > date_to:
        raise ValueError("تاریخ شروع بعد از تاریخ پایان است.")
    if level not in LEVEL_DEPTH:
        raise ValueError("سطح تراز باید general، subsidiary یا detailed باشد.")
    books = StatementBooks(
        ledger, date_from=date_from, date_to=date_to, approved_only=approved_only,
    )
    rows, totals = trial_balance_report(
        ledger, level=level, include_zero=False, approved_only=approved_only, books=books,
    )
    income = income_statement_report(ledger, approved_only=approved_only, books=books)
    sheet = balance_sheet_report(ledger, approved_only=approved_only, books=books)
    return {
        "ledger": ledger.id,
        "date_from": books.iso_from(),
        "date_to": books.iso_to(),
        "basis": "posted" if approved_only else "including_drafts",
        "cards": [
            {"key": "net_income", "label": "سود (زیان) خالص", "value": income["net_income"]},
            {"key": "revenue", "label": "درآمد", "value": income["revenue_total"]},
            {"key": "expense", "label": "هزینه", "value": income["expense_total"]},
            {"key": "assets", "label": "دارایی‌ها", "value": sheet["asset_total"]},
            {"key": "liabilities", "label": "بدهی‌ها", "value": sheet["liability_total"]},
            {
                "key": "equity",
                "label": "حقوق صاحبان سهام",
                "value": sheet["equity_total"] + sheet["net_income"],
            },
        ],
        "trial_balance": {
            "level": level,
            "results": rows,
            "totals": totals,
            "total": len(rows),
        },
        "income_statement": income,
        "balance_sheet": sheet,
    }
