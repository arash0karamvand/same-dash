"""موتور ایزوله مالیات بر ارزش افزوده.

ماژول‌های فروش و خرید فقط مبلغ کالا را می‌دهند. نرخ، پایه مشمول، و آرتیکل
بدهی (فروش) یا طلب (خرید) فقط اینجا حساب می‌شود. سند فاکتور بدون نتیجه
مهارشده این موتور در دفتر روزنامه ثبت نمی‌شود.

مالیات جزو بهای کالا نیست. پایه مشمول، مبلغ پس از تخفیف تجاری است و حمل،
بیمه و سایر مخارج داخل آن نمی‌آیند.
"""

from dataclasses import dataclass
from decimal import Decimal

from logic.accounting_money import to_rial
from logic.chart_of_accounts import ACCOUNT_SLUGS

DEFAULT_VAT_RATE = Decimal("10")

KIND_SALE = "sale"
KIND_PURCHASE = "purchase"
KIND_SALE_RETURN = "sale_return"
KIND_PURCHASE_RETURN = "purchase_return"
KIND_SALE_DISCOUNT = "sale_discount"
KIND_PURCHASE_DISCOUNT = "purchase_discount"

# فروش بستانکارِ بدهی مالیاتی است؛ خرید بدهکارِ طلب مالیاتی است. برگشت و تخفیف برعکس می‌شوند.
_SIDES = {
    KIND_SALE: (ACCOUNT_SLUGS.VAT_PAYABLE, "credit"),
    KIND_PURCHASE: (ACCOUNT_SLUGS.VAT_RECEIVABLE, "debit"),
    KIND_SALE_RETURN: (ACCOUNT_SLUGS.VAT_PAYABLE, "debit"),
    KIND_PURCHASE_RETURN: (ACCOUNT_SLUGS.VAT_RECEIVABLE, "credit"),
    KIND_SALE_DISCOUNT: (ACCOUNT_SLUGS.VAT_PAYABLE, "debit"),
    KIND_PURCHASE_DISCOUNT: (ACCOUNT_SLUGS.VAT_RECEIVABLE, "credit"),
}

_TITLES = {
    KIND_SALE: "مالیات و عوارض ارزش افزوده فروش",
    KIND_PURCHASE: "مالیات و عوارض ارزش افزوده خرید",
    KIND_SALE_RETURN: "برگشت مالیات و عوارض ارزش افزوده فروش",
    KIND_PURCHASE_RETURN: "برگشت مالیات و عوارض ارزش افزوده خرید",
    KIND_SALE_DISCOUNT: "کاهش مالیات فروش",
    KIND_PURCHASE_DISCOUNT: "کاهش مالیات خرید",
}


@dataclass(frozen=True)
class VatAssessment:
    kind: str
    taxable_base: int
    rate: Decimal
    vat_amount: int
    net_of_tax: int
    gross: int
    account_slug: str
    debit: int
    credit: int
    description: str
    included: bool
    sealed: bool = True


def parse_rate(value, *, default=DEFAULT_VAT_RATE):
    try:
        rate = Decimal(str(value if value not in (None, "") else default))
    except Exception as exc:
        raise ValueError("نرخ مالیات نامعتبر است.") from exc
    if rate < 0 or rate > 100:
        raise ValueError("نرخ مالیات باید بین ۰ و ۱۰۰ باشد.")
    return rate


def vat_on(base, rate):
    """مالیات جدا از مبلغ کالا: پایه × نرخ / ۱۰۰."""
    rate = parse_rate(rate)
    amount = to_rial(base)
    if amount < 0:
        raise ValueError("پایه مالیات نمی‌تواند منفی باشد.")
    if rate == 0 or amount == 0:
        return 0
    return to_rial(Decimal(amount) * rate / Decimal(100))


def split_included(gross, rate):
    """مبلغ قابل‌پرداخت شامل مالیات است. جزء خالص و مالیات طوری جدا می‌شوند که جمع‌شان همان مبلغ بماند."""
    rate = parse_rate(rate)
    amount = to_rial(gross)
    if amount < 0:
        raise ValueError("مبلغ فاکتور نمی‌تواند منفی باشد.")
    if rate == 0 or amount == 0:
        return amount, 0
    vat = to_rial(Decimal(amount) * rate / (Decimal(100) + rate))
    if vat > amount:
        vat = amount
    return amount - vat, vat


def allocate(total, take, remaining):
    """سهم مالیات یک برگشت یا تسهیم، از مانده سند مبنا."""
    total = to_rial(total)
    take = Decimal(str(take if take not in (None, "") else 0))
    remaining = Decimal(str(remaining if remaining not in (None, "") else 0))
    if take < 0 or remaining <= 0 or take > remaining:
        raise ValueError("تسهیم مالیات با مانده سند مبنا نمی‌خواند.")
    if take == remaining:
        return total
    return to_rial(Decimal(total) * take / remaining)


def assess(*, kind, taxable_base=0, rate=None, exempt=False, included=False, vat_amount=None, label=""):
    """تنها ورودی قانونی فاکتور. خروجی مهارشده است و سند بدون آن ساخته نمی‌شود."""
    if kind not in _SIDES:
        raise ValueError("نوع فاکتور برای محاسبه مالیات شناخته نشده است.")
    if vat_amount is not None and included:
        raise ValueError("مبلغ مالیات و حالت درون‌فاکتور با هم ارسال نمی‌شوند.")

    rate = Decimal(0) if exempt else parse_rate(rate)
    base = to_rial(taxable_base)
    if base < 0:
        raise ValueError("پایه مالیات نمی‌تواند منفی باشد.")

    if exempt or rate == 0:
        net, vat, gross = base, 0, base
    elif vat_amount is not None:
        vat = to_rial(vat_amount)
        if vat < 0:
            raise ValueError("مبلغ مالیات نمی‌تواند منفی باشد.")
        net, gross = base, base + vat
    elif included:
        net, vat = split_included(base, rate)
        gross = base
    else:
        vat = vat_on(base, rate)
        net, gross = base, base + vat

    slug, side = _SIDES[kind]
    text = (label or "").strip() or _TITLES[kind]
    return VatAssessment(
        kind=kind,
        taxable_base=base,
        rate=rate,
        vat_amount=vat,
        net_of_tax=net,
        gross=gross,
        account_slug=slug,
        debit=vat if side == "debit" else 0,
        credit=vat if side == "credit" else 0,
        description=text,
        included=included,
    )


def _line_slug(line):
    account = line.get("account")
    return getattr(account, "slug", None) or line.get("account_slug") or ""


def carve_included_credit(lines, assessment, *, revenue_slug):
    """مالیات را از بستانکار درآمد کم می‌کند تا جمع سند برابر مبلغ قابل‌پرداخت بماند."""
    if assessment.vat_amount <= 0:
        return list(lines)
    if not assessment.included:
        raise ValueError("تفکیک مالیات درون مبلغ فقط برای فاکتورِ داخل‌قیمت است.")

    remaining = assessment.vat_amount
    found = False
    kept = []
    for line in lines:
        credit = to_rial(line.get("credit") or 0)
        if _line_slug(line) == revenue_slug and credit > 0 and remaining:
            found = True
            cut = min(credit, remaining)
            credit -= cut
            remaining -= cut
            if credit <= 0:
                continue
            kept.append({**line, "credit": credit})
            continue
        kept.append(line)
    if not found or remaining:
        raise ValueError("مبلغ فروش فاکتور برای جدا کردن مالیات کافی نیست.")
    return kept


def bind_tax_article(lines, assessment, *, ledger=None):
    """آرتیکل بدهی یا طلب را، اگر ماژول نیاورده باشد، به سند اضافه می‌کند."""
    if not isinstance(assessment, VatAssessment) or not assessment.sealed:
        raise ValueError("فاکتور پیش از ثبت سند باید از موتور مالیات عبور کند.")
    prepared = list(lines)
    if assessment.vat_amount <= 0:
        return prepared

    side = "debit" if assessment.debit else "credit"
    opposite = "credit" if side == "debit" else "debit"
    posted = 0
    opposite_total = 0
    for line in prepared:
        if _line_slug(line) != assessment.account_slug:
            continue
        posted += to_rial(line.get(side) or 0)
        opposite_total += to_rial(line.get(opposite) or 0)
    if opposite_total:
        raise ValueError("طرف آرتیکل مالیات با نوع فاکتور نمی‌خواند.")
    if posted == assessment.vat_amount:
        return prepared
    if posted:
        raise ValueError("آرتیکل مالیات با محاسبه قانونی یکی نیست.")

    from logic.accounting_accounts import get_account
    from logic.ledger import OFFICE_LEDGER

    prepared.append({
        "account": get_account(assessment.account_slug, ledger=ledger or OFFICE_LEDGER),
        "debit": assessment.debit,
        "credit": assessment.credit,
        "description": assessment.description,
    })
    return prepared


def post_assessed_journal(*, lines, assessment, **kwargs):
    """تنها مسیر تبدیل فاکتور فروش یا خرید به سند روزنامه."""
    from logic.accounting import create_journal
    from logic.ledger import OFFICE_LEDGER

    if not isinstance(assessment, VatAssessment) or not assessment.sealed:
        raise ValueError("فاکتور پیش از ثبت سند باید از موتور مالیات عبور کند.")
    ledger = kwargs.get("ledger", OFFICE_LEDGER)
    prepared = bind_tax_article(lines, assessment, ledger=ledger)
    return create_journal(lines=prepared, **kwargs)
