"""بستن حساب‌های موقت به سود و زیان انباشته. سند پیش‌نویس می‌سازد."""

from logic.accounting_accounts import get_account
from logic.accounting_documents import create_accounting_document
from logic.giant_books.statements import income_statement


def closing_lines(ledger, activity):
    income = income_statement(activity)
    retained = get_account("retained_earnings", ledger=ledger)
    lines = []
    for row in income["revenue"]:
        if row["balance"] > 0:
            lines.append({
                "account_id": row["account_id"], "debit": row["balance"], "credit": 0,
                "description": "بستن درآمد",
            })
        elif row["balance"] < 0:
            lines.append({
                "account_id": row["account_id"], "debit": 0, "credit": -row["balance"],
                "description": "بستن درآمد",
            })
    for row in income["expenses"]:
        if row["balance"] > 0:
            lines.append({
                "account_id": row["account_id"], "debit": 0, "credit": row["balance"],
                "description": "بستن هزینه",
            })
        elif row["balance"] < 0:
            lines.append({
                "account_id": row["account_id"], "debit": -row["balance"], "credit": 0,
                "description": "بستن هزینه",
            })
    profit = income["net_income"]
    if profit > 0:
        lines.append({
            "account_id": retained.id, "debit": 0, "credit": profit,
            "description": "انتقال سود دوره",
        })
    elif profit < 0:
        lines.append({
            "account_id": retained.id, "debit": -profit, "credit": 0,
            "description": "انتقال زیان دوره",
        })
    if len(lines) < 2:
        raise ValueError("در این دوره مانده‌ای برای بستن حساب‌های موقت نیست.")
    return lines, income["net_income"]


def close_temporary_accounts(ledger, activity, *, entry_date=None, user=None):
    lines, net_income = closing_lines(ledger, activity)
    created = create_accounting_document(
        lines=lines,
        entry_date=entry_date,
        description="بستن حساب‌های موقت",
        is_approved=False,
        entry_type="adjustment",
        ledger=ledger,
        user=user,
    )
    return {
        "document_code": created["document_code"],
        "document_number": created["document_number"],
        "net_income": net_income,
        "line_count": len(lines),
    }
