"""خواندن اسناد قطعی و تجمیع آن‌ها با Pandas."""

from datetime import date, datetime

import pandas as pd

from backend.models import JournalEntry, JournalLine
from logic.giant_books.classify import bucket

COLUMNS = [
    "journal_id",
    "document_code",
    "entry_date",
    "description",
    "line_number",
    "account_id",
    "code",
    "name",
    "slug",
    "path",
    "account_class",
    "normal_balance",
    "bucket",
    "debit",
    "credit",
]


def _iso_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def lines_frame(ledger, *, date_from=None, date_to=None):
    qs = JournalLine.objects.filter(
        journal__ledger__code=ledger.id,
        journal__status_ref_id=JournalEntry.STATUS_POSTED,
    ).select_related("account", "journal")
    if date_from:
        qs = qs.filter(journal__entry_date__date__gte=date_from)
    if date_to:
        qs = qs.filter(journal__entry_date__date__lte=date_to)
    rows = []
    for line in qs.order_by("journal__entry_date", "journal_id", "line_number"):
        account = line.account
        rows.append({
            "journal_id": line.journal_id,
            "document_code": line.journal.document_code,
            "entry_date": _iso_date(line.journal.entry_date),
            "description": line.journal.description or "",
            "line_number": line.line_number,
            "account_id": account.id,
            "code": account.code,
            "name": account.name,
            "slug": account.slug,
            "path": account.path,
            "account_class": account.account_class,
            "normal_balance": account.normal_balance,
            "bucket": bucket(account.account_class, account.slug, account.path, account.code),
            "debit": int(line.debit or 0),
            "credit": int(line.credit or 0),
        })
    frame = pd.DataFrame(rows, columns=COLUMNS)
    if frame.empty:
        return frame
    frame["debit"] = frame["debit"].astype("int64")
    frame["credit"] = frame["credit"].astype("int64")
    return frame


def account_totals(frame):
    """یک ردیف برای هر حساب: جمع بدهکار و بستانکار."""
    group_cols = [
        "account_id", "code", "name", "slug", "account_class", "normal_balance", "bucket",
    ]
    if frame.empty:
        return pd.DataFrame(columns=group_cols + ["debit", "credit"])
    grouped = (
        frame.groupby(group_cols, as_index=False)[["debit", "credit"]]
        .sum()
        .sort_values("code")
    )
    grouped["debit"] = grouped["debit"].astype("int64")
    grouped["credit"] = grouped["credit"].astype("int64")
    return grouped
