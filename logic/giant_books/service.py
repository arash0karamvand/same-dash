"""موتور دفاتر: صورت‌های مالی، کنترل Hordak، Beancount و پل Odoo/ERPNext."""

from datetime import datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date

from logic.giant_books.beancount_book import render_beancount, validate_beancount
from logic.giant_books.bridges import (
    erpnext_configured,
    erpnext_entries,
    odoo_configured,
    odoo_moves,
    push_erpnext,
    push_odoo,
)
from logic.giant_books.closing import close_temporary_accounts
from logic.giant_books.engines import engine_status
from logic.giant_books.frames import lines_frame
from logic.giant_books.legs import hordak_check
from logic.giant_books.statements import balance_sheet, cash_flow, income_statement, ratios
from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER

LEDGERS = {"office": OFFICE_LEDGER, "factory": FACTORY_LEDGER}


def parse_book_date(value, label):
    text = (value or "").strip()
    if not text:
        return None
    parsed = parse_date(text)
    if parsed is None:
        raise ValueError(f"{label} نامعتبر است.")
    return parsed


def _frames(ledger, date_from, date_to):
    position = lines_frame(ledger, date_to=date_to)
    activity = lines_frame(ledger, date_from=date_from, date_to=date_to)
    return position, activity


def build_books(ledger, *, date_from=None, date_to=None):
    position, activity = _frames(ledger, date_from, date_to)
    income = income_statement(activity)
    unclosed = income_statement(position)
    sheet = balance_sheet(position, unclosed["net_income"])
    flow = cash_flow(activity, income["net_income"])
    source = render_beancount(ledger, activity)
    beancount = validate_beancount(source)
    moves = odoo_moves(activity)
    entries = erpnext_entries(activity)
    return {
        "ledger": ledger.id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "income_statement": income,
        "balance_sheet": sheet,
        "cash_flow": flow,
        "ratios": ratios(sheet, income),
        "hordak": hordak_check(activity),
        "beancount": {
            "engine": beancount["engine"],
            "valid": beancount["valid"],
            "errors": beancount["errors"],
            "transaction_count": 0 if activity.empty else int(activity["journal_id"].nunique()),
        },
        "odoo": {
            "configured": odoo_configured(),
            "move_count": len(moves),
            "sample": moves[:1],
        },
        "erpnext": {
            "configured": erpnext_configured(),
            "entry_count": len(entries),
            "sample": entries[:1],
        },
        "engines": engine_status(
            odoo_ready=odoo_configured(),
            erpnext_ready=erpnext_configured(),
            beancount_engine=beancount["engine"],
        ),
    }


def beancount_source(ledger, *, date_from=None, date_to=None):
    _position, activity = _frames(ledger, date_from, date_to)
    return render_beancount(ledger, activity)


def close_books(ledger, *, date_from=None, date_to=None, user=None):
    _position, activity = _frames(ledger, date_from, date_to)
    when = None
    if date_to:
        when = timezone.make_aware(datetime.combine(date_to, time.min))
    return close_temporary_accounts(ledger, activity, entry_date=when, user=user)


def push_books(ledger, target, *, date_from=None, date_to=None):
    _position, activity = _frames(ledger, date_from, date_to)
    if target == "odoo":
        return push_odoo(odoo_moves(activity))
    if target == "erpnext":
        return push_erpnext(erpnext_entries(activity))
    raise ValueError("مقصد ارسال باید odoo یا erpnext باشد.")
