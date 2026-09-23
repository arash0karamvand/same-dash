"""مبالغ دفتر با py-moneyed. واحد عملیاتی ریال و ارز IRR است."""

from decimal import Decimal, ROUND_HALF_UP

from moneyed import Money, get_currency

from logic.accounting_money import to_rial

IRR = get_currency("IRR")


def rial(value) -> Money:
    return Money(Decimal(to_rial(value)), IRR)


def money_int(value: Money) -> int:
    return int(Decimal(value.amount).to_integral_value(rounding=ROUND_HALF_UP))
