"""صورت‌های مالی به سبک Django-Ledger: ترازنامه، سود و زیان، جریان نقد."""

from logic.giant_books.frames import account_totals
from logic.giant_books.money import money_int, rial

SECTION_BUCKETS = {
    "assets": ("cash", "operating_asset", "investing_asset"),
    "liabilities": ("operating_liability", "financing_liability"),
    "equity": ("equity",),
    "revenue": ("revenue",),
    "expense": ("expense",),
}


def _sum_column(frame, column):
    if frame.empty:
        return 0
    return int(frame[column].sum())


def _normal_balance(row):
    amount = rial(row.debit) - rial(row.credit)
    if row.normal_balance == "credit":
        amount = -amount
    return money_int(amount)


def _rows(totals, buckets):
    if totals.empty:
        return []
    selected = totals[totals["bucket"].isin(buckets)]
    rows = []
    for row in selected.itertuples(index=False):
        balance = _normal_balance(row)
        if balance == 0 and int(row.debit) == 0 and int(row.credit) == 0:
            continue
        rows.append({
            "account_id": int(row.account_id),
            "code": str(row.code),
            "name": str(row.name),
            "balance": balance,
        })
    return rows


def _section_total(rows):
    return sum(row["balance"] for row in rows)


def _ratio(numerator, denominator):
    if not denominator:
        return None
    return round(numerator / denominator, 4)


def _movement(frame, name):
    part = frame[frame["bucket"] == name] if not frame.empty else frame
    debit = _sum_column(part, "debit")
    credit = _sum_column(part, "credit")
    if name in {"cash", "operating_asset", "investing_asset"}:
        return debit - credit
    return credit - debit


def income_statement(activity):
    totals = account_totals(activity)
    revenue = _rows(totals, SECTION_BUCKETS["revenue"])
    expenses = _rows(totals, SECTION_BUCKETS["expense"])
    revenue_total = _section_total(revenue)
    expense_total = _section_total(expenses)
    return {
        "revenue": revenue,
        "expenses": expenses,
        "revenue_total": revenue_total,
        "expense_total": expense_total,
        "net_income": revenue_total - expense_total,
    }


def balance_sheet(position, net_income):
    totals = account_totals(position)
    assets = _rows(totals, SECTION_BUCKETS["assets"])
    liabilities = _rows(totals, SECTION_BUCKETS["liabilities"])
    equity = _rows(totals, SECTION_BUCKETS["equity"])
    asset_total = _section_total(assets)
    liability_total = _section_total(liabilities)
    equity_total = _section_total(equity)
    liabilities_and_equity = liability_total + equity_total + net_income
    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "asset_total": asset_total,
        "liability_total": liability_total,
        "equity_total": equity_total,
        "net_income": net_income,
        "liabilities_and_equity": liabilities_and_equity,
        "balanced": asset_total == liabilities_and_equity,
    }


def cash_flow(activity, net_income):
    operating_asset = _movement(activity, "operating_asset")
    operating_liability = _movement(activity, "operating_liability")
    investing_asset = _movement(activity, "investing_asset")
    financing_liability = _movement(activity, "financing_liability")
    equity = _movement(activity, "equity")
    cash_change = _movement(activity, "cash")
    operating = [
        {"label": "سود (زیان) خالص", "amount": net_income},
        {"label": "افزایش دارایی‌های عملیاتی", "amount": -operating_asset},
        {"label": "افزایش بدهی‌های عملیاتی", "amount": operating_liability},
    ]
    investing = [{"label": "افزایش دارایی‌های سرمایه‌ای", "amount": -investing_asset}]
    financing = [
        {"label": "افزایش بدهی‌های تأمین مالی", "amount": financing_liability},
        {"label": "افزایش سرمایه", "amount": equity},
    ]
    operating_total = sum(row["amount"] for row in operating)
    investing_total = sum(row["amount"] for row in investing)
    financing_total = sum(row["amount"] for row in financing)
    net_change = operating_total + investing_total + financing_total
    return {
        "operating": operating,
        "investing": investing,
        "financing": financing,
        "operating_total": operating_total,
        "investing_total": investing_total,
        "financing_total": financing_total,
        "net_change": net_change,
        "cash_change": cash_change,
        "reconciled": net_change == cash_change,
    }


def ratios(sheet, income):
    equity_base = sheet["equity_total"] + sheet["net_income"]
    return [
        {"key": "current_ratio", "label": "نسبت دارایی به بدهی", "value": _ratio(sheet["asset_total"], sheet["liability_total"])},
        {"key": "debt_to_equity", "label": "نسبت بدهی به حقوق صاحبان سهام", "value": _ratio(sheet["liability_total"], equity_base)},
        {"key": "net_margin", "label": "حاشیه سود خالص", "value": _ratio(income["net_income"], income["revenue_total"])},
        {"key": "expense_ratio", "label": "نسبت هزینه به درآمد", "value": _ratio(income["expense_total"], income["revenue_total"])},
    ]
