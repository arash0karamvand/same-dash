"""گزارش‌های پایهٔ داشبورد: تراز آزمایشی، سود و زیان، ترازنامه."""

from api.helpers import api_view, fail, success
from auth.permissions import VIEW_ACCOUNTING, VIEW_FACTORY_ACCOUNTING
from logic.financial_statements import (
    balance_sheet_report,
    coerce_date,
    income_statement_report,
    management_statements,
    trial_balance_report,
)
from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER


def _filters(request):
    date_from = coerce_date(request.GET.get("date_from"), "تاریخ شروع")
    date_to = coerce_date(request.GET.get("date_to"), "تاریخ پایان")
    if date_from and date_to and date_from > date_to:
        raise ValueError("تاریخ شروع بعد از تاریخ پایان است.")
    raw = (request.GET.get("approved_only") or "").strip().lower()
    approved_only = raw not in {"false", "0"}
    level = (request.GET.get("level") or "general").strip() or "general"
    return date_from, date_to, approved_only, level


def make_statement_views(*, ledger, view_permission):
    @api_view("GET", permission=view_permission)
    def dashboard(request):
        try:
            date_from, date_to, approved_only, level = _filters(request)
            return success(management_statements(
                ledger,
                date_from=date_from,
                date_to=date_to,
                approved_only=approved_only,
                level=level,
            ))
        except ValueError as exc:
            return fail(str(exc))

    @api_view("GET", permission=view_permission)
    def trial_balance(request):
        try:
            date_from, date_to, approved_only, level = _filters(request)
            rows, totals = trial_balance_report(
                ledger,
                date_from=date_from,
                date_to=date_to,
                approved_only=approved_only,
                level=level,
                include_zero=False,
            )
        except ValueError as exc:
            return fail(str(exc))
        return success({"level": level, "results": rows, "totals": totals, "total": len(rows)})

    @api_view("GET", permission=view_permission)
    def income(request):
        try:
            date_from, date_to, approved_only, _level = _filters(request)
            return success(income_statement_report(
                ledger, date_from=date_from, date_to=date_to, approved_only=approved_only,
            ))
        except ValueError as exc:
            return fail(str(exc))

    @api_view("GET", permission=view_permission)
    def balance_sheet(request):
        try:
            date_from, date_to, approved_only, _level = _filters(request)
            return success(balance_sheet_report(
                ledger, date_from=date_from, date_to=date_to, approved_only=approved_only,
            ))
        except ValueError as exc:
            return fail(str(exc))

    dashboard.__name__ = f"statements_{ledger.id}"
    trial_balance.__name__ = f"statements_trial_{ledger.id}"
    income.__name__ = f"statements_income_{ledger.id}"
    balance_sheet.__name__ = f"statements_balance_{ledger.id}"
    return dashboard, trial_balance, income, balance_sheet


office_statements, office_trial, office_income, office_balance = make_statement_views(
    ledger=OFFICE_LEDGER, view_permission=VIEW_ACCOUNTING,
)
factory_statements, factory_trial, factory_income, factory_balance = make_statement_views(
    ledger=FACTORY_LEDGER, view_permission=VIEW_FACTORY_ACCOUNTING,
)
