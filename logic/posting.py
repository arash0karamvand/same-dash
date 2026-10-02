"""تبدیل قوانین ثبت (Posting Rules) به ردیف‌های سند حسابداری."""

from __future__ import annotations

from decimal import Decimal

from logic.dynamic_choices import posting_rules


def build_journal_lines(
    rule_name: str,
    *,
    amounts: dict,
    accounts: dict | None = None,
    description: str = "",
    ledger=None,
    branch=None,
    warehouse=None,
    item_category="",
    effective_date=None,
):
    """rule_name → list of journal line dicts with resolved Account objects."""
    from logic.accounting_accounts import get_account
    from logic.account_mappings import resolve_mapped_account, validate_postable_account

    if ledger is None:
        from logic.ledger import OFFICE_LEDGER

        ledger = OFFICE_LEDGER

    accounts = accounts or {}
    rules = posting_rules(rule_name)
    if not rules:
        raise ValueError(f"قانون ثبت «{rule_name}» تعریف نشده است.")

    lines = []
    for rule in rules:
        amount = Decimal(str(amounts.get(rule["amount_key"]) or 0))
        if rule.get("min_amount") and amount <= 0:
            continue
        if amount <= 0:
            continue

        account_key = rule.get("account_key")
        role = rule.get("role") or account_key or rule.get("slug")
        side = rule["side"]
        explicit_account = accounts.get(role) or accounts.get(rule.get("slug"))
        account = explicit_account or resolve_mapped_account(
            rule_name,
            role,
            side,
            ledger=ledger,
            branch=branch,
            warehouse=warehouse,
            item_category=item_category,
            effective_date=effective_date,
        )
        if account is not None:
            pass
        elif account_key:
            account = accounts.get(account_key)
            if account is None:
                raise ValueError(f"حساب «{account_key}» برای قانون ثبت مشخص نشده است.")
        else:
            account = get_account(rule["slug"], ledger=ledger)
        validate_postable_account(account, ledger=ledger)

        lines.append(
            {
                "account": account,
                "debit": amount if side == "debit" else Decimal(0),
                "credit": amount if side == "credit" else Decimal(0),
                "description": description,
            }
        )
    return lines
