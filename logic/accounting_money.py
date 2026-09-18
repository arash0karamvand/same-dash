"""واحد پول پروژه — همه مبالغ عملیاتی و حسابداری به ریال (عدد صحیح).

جدول فیلدهای پولی (همه DecimalField با MONEY_KWARGS):
  LoyaltyLevel          min_purchase, max_purchase
  Customer              wallet_balance, cashback_balance, total_purchases
  Sale                  amount, discount_value, discount, final_amount, paid_amount
  SaleInstallment       amount
  SaleLineItem          unit_price, line_total
  Product               default_price
  ProductVariant        price
  Material              unit_cost
  OfficeOrder           amount, discount_value, discount, final_amount, paid_amount
  OfficeOrderLineItem   unit_price, line_total
  OfficeOrderInstallment amount
  CustomerLevelHistory  total_purchases_at_change
  WalletTransaction     amount, balance_after
  SmsClubSettings       default_discount_value
  AccountingEntry       debit, credit, amount, opening_*, balance_*  (از ابتدا ریال)
"""

from decimal import Decimal, ROUND_HALF_UP

MONEY_UNIT = "rial"
MONEY_UNIT_LABEL = "ریال"
ACCOUNTING_CURRENCY_LABEL = MONEY_UNIT_LABEL

# فقط برای مهاجرت دادهٔ قدیمی (تومان → ریال)
TOMAN_TO_RIAL = 10

# (نام مدل Django, فیلدهای پولی) — برای migrate_money_to_rial
BUSINESS_MONEY_MODEL_FIELDS = (
    ("LoyaltyLevel", ("min_purchase", "max_purchase")),
    ("Customer", ("wallet_balance", "total_purchases")),
    ("Sale", ("amount", "discount_value", "discount", "final_amount", "paid_amount")),
    ("SaleInstallment", ("amount",)),
    ("SaleLineItem", ("unit_price", "line_total")),
    ("Product", ("default_price",)),
    ("ProductVariant", ("price",)),
    ("Material", ("unit_cost",)),
    ("OfficeOrder", ("amount", "discount_value", "discount", "final_amount", "paid_amount")),
    ("OfficeOrderLineItem", ("unit_price", "line_total")),
    ("OfficeOrderInstallment", ("amount",)),
    ("CustomerLevelHistory", ("total_purchases_at_change",)),
    ("WalletTransaction", ("amount", "balance_after")),
    ("CashbackTransaction", ("amount",)),
    ("SmsClubSettings", ("default_discount_value",)),
)


def to_rial(value):
    """نرمال‌سازی مبلغ به ریال (عدد صحیح)."""
    if value is None or value == "":
        return 0
    amount = Decimal(str(value))
    return int(amount.to_integral_value(rounding=ROUND_HALF_UP))


def to_rial_from_toman(value):
    """سازگاری با کد قدیمی — دیگر تبدیل نمی‌کند؛ همان to_rial."""
    return to_rial(value)


def format_rial_amount(value):
    """متن مبلغ با واحد ریال."""
    return f"{to_rial(value):,} {MONEY_UNIT_LABEL}"


def scale_money_fields_on_instance(obj, field_names, factor):
    """ضرب/تقسیم فیلدهای پولی یک رکورد (مهاجرت)."""
    changed = False
    for name in field_names:
        val = getattr(obj, name, None)
        if val is None:
            continue
        if val == 0:
            continue
        setattr(obj, name, val * factor)
        changed = True
    if changed:
        obj.save()
    return changed
