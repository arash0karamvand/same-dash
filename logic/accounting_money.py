"""واحد پول حسابداری — تمام مبالغ دفاتر به ریال."""

from decimal import Decimal, ROUND_HALF_UP

TOMAN_TO_RIAL = 10
ACCOUNTING_CURRENCY_LABEL = "ریال"


def to_rial(value):
    """تبدیل مبلغ به ریال (عدد صحیح)."""
    if value is None or value == "":
        return 0
    amount = Decimal(str(value))
    return int(amount.to_integral_value(rounding=ROUND_HALF_UP))


def to_rial_from_toman(value):
    """تبدیل تومان (فروش/متریال) به ریال."""
    if value is None or value == "":
        return 0
    amount = Decimal(str(value)) * TOMAN_TO_RIAL
    return int(amount.to_integral_value(rounding=ROUND_HALF_UP))


def format_rial_amount(value):
    """متن فارسی مبلغ با واحد ریال."""
    return f"{to_rial(value):,} {ACCOUNTING_CURRENCY_LABEL}"
