"""برنامه‌های کش‌بک RFM: کسب، سقف قابل‌استفاده، پله اپسل و سه حالت مصرف."""

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum

from backend.models import CashbackProgram, CashbackTransaction, CashbackUnlockStep, Customer
from logic.rfm import countable_sales_qs

ZERO = Decimal("0")
HUNDRED = Decimal("100")


def _money(value):
    return Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _percent(value, default="0"):
    return Decimal(str(value if value is not None else default))


def _clamp_percent(value):
    pct = _percent(value)
    if pct < 0 or pct > HUNDRED:
        raise ValueError("درصد باید بین ۰ تا ۱۰۰ باشد.")
    return pct


def cashback_balance(customer):
    return customer.cashback_transactions.aggregate(total=Sum("amount"))["total"] or ZERO


def matching_program(customer):
    """اولین برنامه فعال بر اساس اولویت که بخش مشتری را پوشش دهد (بدون بخش = همه)."""
    from django.core.exceptions import ObjectDoesNotExist

    segment_id = None
    try:
        score = customer.rfm_score
    except ObjectDoesNotExist:
        score = None
    if score is not None:
        segment_id = score.segment_id
    programs = (
        CashbackProgram.objects.filter(is_active=True)
        .prefetch_related("segments", "unlock_steps")
        .order_by("sort_order", "id")
    )
    for program in programs:
        segment_ids = {item.id for item in program.segments.all()}
        if not segment_ids or segment_id in segment_ids:
            return program
    return None


def last_sale_amount(customer, exclude_sale_id=None):
    qs = countable_sales_qs().filter(customer=customer).order_by("-sold_at", "-id")
    if exclude_sale_id:
        qs = qs.exclude(pk=exclude_sale_id)
    sale = qs.first()
    if not sale:
        return ZERO
    return _money(sale.amount)


def usable_percent(program, invoice_amount, previous_amount):
    base = _percent(program.base_usable_percent)
    extra = ZERO
    invoice_amount = _money(invoice_amount)
    previous_amount = _money(previous_amount)
    if previous_amount > 0 and invoice_amount > previous_amount:
        growth = (invoice_amount - previous_amount) * HUNDRED / previous_amount
        matched = None
        for step in sorted(program.unlock_steps.all(), key=lambda item: item.extra_purchase_percent, reverse=True):
            if growth >= _percent(step.extra_purchase_percent):
                matched = step
                break
        if matched:
            extra = _percent(matched.extra_usable_percent)
    pct = base + extra
    if pct < 0:
        return ZERO
    if pct > HUNDRED:
        return HUNDRED
    return pct


def next_unlock_hint(program, invoice_amount, previous_amount):
    previous_amount = _money(previous_amount)
    invoice_amount = _money(invoice_amount)
    if previous_amount <= 0:
        return None
    growth = ZERO
    if invoice_amount > previous_amount:
        growth = (invoice_amount - previous_amount) * HUNDRED / previous_amount
    for step in sorted(program.unlock_steps.all(), key=lambda item: item.extra_purchase_percent):
        need = _percent(step.extra_purchase_percent)
        if growth < need:
            target_amount = (previous_amount * (HUNDRED + need) / HUNDRED).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            extra_needed = max(ZERO, target_amount - invoice_amount)
            resulting = min(HUNDRED, _percent(program.base_usable_percent) + _percent(step.extra_usable_percent))
            return {
                "extra_purchase_percent": float(need),
                "extra_usable_percent": float(step.extra_usable_percent),
                "extra_amount": int(extra_needed),
                "target_amount": int(target_amount),
                "resulting_usable_percent": float(resulting),
            }
    return None


def quote_cashback(customer, invoice_amount, exclude_sale_id=None, program=None):
    invoice_amount = _money(invoice_amount)
    program = program or matching_program(customer)
    balance = _money(cashback_balance(customer))
    previous = last_sale_amount(customer, exclude_sale_id=exclude_sale_id)
    if program is None:
        return {
            "program_id": None,
            "program_name": None,
            "redeem_mode": None,
            "balance": int(balance),
            "earn_percent": 0,
            "usable_percent": 0,
            "usable_amount": 0,
            "last_sale_amount": int(previous),
            "next_unlock": None,
        }
    percent = usable_percent(program, invoice_amount, previous)
    usable_amount = min(
        invoice_amount,
        (balance * percent / HUNDRED).quantize(Decimal("1"), rounding=ROUND_HALF_UP),
    )
    if usable_amount < 0:
        usable_amount = ZERO
    return {
        "program_id": program.id,
        "program_name": program.name,
        "redeem_mode": program.redeem_mode,
        "balance": int(balance),
        "earn_percent": float(program.earn_percent),
        "usable_percent": float(percent),
        "usable_amount": int(usable_amount),
        "last_sale_amount": int(previous),
        "next_unlock": next_unlock_hint(program, invoice_amount, previous),
    }


def maybe_autoselect_cashback_discount(customer, amount, discount_type, discount_value):
    discount_type = (discount_type or "amount").strip()
    value = _money(discount_value)
    if discount_type not in ("amount", "") or value > 0:
        return discount_type or "amount", discount_value
    program = matching_program(customer)
    if program is None or program.redeem_mode != CashbackProgram.REDEEM_AUTO:
        return discount_type or "amount", discount_value
    quote = quote_cashback(customer, amount, program=program)
    if quote["usable_amount"] <= 0:
        return discount_type or "amount", discount_value
    return "cashback", Decimal(quote["usable_amount"])


def _typed_sum(sale, types):
    if sale is None or not sale.pk:
        return ZERO
    return (
        CashbackTransaction.objects.filter(sale=sale, transaction_type__in=types).aggregate(
            total=Sum("amount")
        )["total"]
        or ZERO
    )


def _post(customer, amount, transaction_type, *, program=None, sale=None, user=None, description=""):
    amount = _money(amount)
    if amount == 0:
        return None
    return CashbackTransaction.objects.create(
        customer=customer,
        program=program,
        amount=amount,
        transaction_type=transaction_type,
        description=(description or "").strip(),
        sale=sale,
        recorded_by=user,
    )


def apply_cashback_spend(customer, sale, amount, user=None):
    amount = _money(amount)
    if sale is None:
        return None
    if amount < 0:
        amount = ZERO
    already = -_typed_sum(sale, [CashbackTransaction.TYPE_SPEND])
    delta = amount - already
    if delta == 0:
        return None
    program = matching_program(customer)
    if delta > 0:
        return _post(
            customer,
            -delta,
            CashbackTransaction.TYPE_SPEND,
            program=program,
            sale=sale,
            user=user,
            description=f"مصرف کش‌بک فاکتور {sale.invoice_number or sale.pk}",
        )
    return _post(
        customer,
        -delta,
        CashbackTransaction.TYPE_SPEND,
        program=program,
        sale=sale,
        user=user,
        description=f"اصلاح مصرف کش‌بک فاکتور {sale.invoice_number or sale.pk}",
    )


def accrue_cashback(customer, sale=None, user=None):
    """کسب متناسب با مبلغ پرداخت‌شده فاکتور؛ برای wallet_credit سقف قابل‌استفاده را شارژ می‌کند."""
    if sale is None or not sale.pk or sale.customer_id != customer.pk:
        return None
    program = matching_program(customer)
    if program is None:
        return None
    paid = _money(sale.paid_amount)
    target_earn = (paid * _percent(program.earn_percent) / HUNDRED).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    already_earn = _typed_sum(sale, [CashbackTransaction.TYPE_EARN])
    delta = target_earn - already_earn
    if delta:
        _post(
            customer,
            delta,
            CashbackTransaction.TYPE_EARN,
            program=program,
            sale=sale,
            user=user,
            description=f"کسب کش‌بک فاکتور {sale.invoice_number or sale.pk}",
        )
    if program.redeem_mode == CashbackProgram.REDEEM_WALLET:
        _credit_wallet_from_cashback(customer, sale, program, user=user)
    return program


def _credit_wallet_from_cashback(customer, sale, program, user=None):
    from logic.wallet import adjust_wallet

    quote = quote_cashback(customer, sale.amount, exclude_sale_id=sale.pk, program=program)
    already_wallet = -_typed_sum(sale, [CashbackTransaction.TYPE_WALLET])
    balance = _money(cashback_balance(customer))
    pool = balance + already_wallet
    target = min(
        pool,
        (pool * _percent(quote["usable_percent"]) / HUNDRED).quantize(Decimal("1"), rounding=ROUND_HALF_UP),
    )
    delta = target - already_wallet
    if delta == 0:
        return
    if delta > 0:
        _post(
            customer,
            -delta,
            CashbackTransaction.TYPE_WALLET,
            program=program,
            sale=sale,
            user=user,
            description=f"شارژ کیف پول از کش‌بک فاکتور {sale.invoice_number or sale.pk}",
        )
        adjust_wallet(
            customer,
            delta,
            description=f"کش‌بک فاکتور {sale.invoice_number or sale.pk}",
            user=user,
            transaction_type="cashback",
            sale=sale,
        )
        return
    _post(
        customer,
        -delta,
        CashbackTransaction.TYPE_WALLET,
        program=program,
        sale=sale,
        user=user,
        description=f"اصلاح شارژ کیف پول کش‌بک فاکتور {sale.invoice_number or sale.pk}",
    )
    try:
        adjust_wallet(
            customer,
            delta,
            description=f"برگشت کش‌بک فاکتور {sale.invoice_number or sale.pk}",
            user=user,
            transaction_type="refund",
            sale=sale,
        )
    except ValueError:
        withdraw = min(_money(customer.wallet_balance), -delta)
        if withdraw > 0:
            adjust_wallet(
                customer,
                -withdraw,
                description=f"برگشت کش‌بک فاکتور {sale.invoice_number or sale.pk}",
                user=user,
                transaction_type="refund",
                sale=sale,
            )


@transaction.atomic
def reverse_sale_cashback(customer, sale, user=None):
    if sale is None or not sale.pk:
        return
    txs = list(CashbackTransaction.objects.filter(sale=sale).exclude(
        transaction_type=CashbackTransaction.TYPE_REVERSAL
    ))
    if not txs:
        return
    if CashbackTransaction.objects.filter(
        sale=sale, transaction_type=CashbackTransaction.TYPE_REVERSAL
    ).exists():
        return
    wallet_credited = ZERO
    net = ZERO
    program = None
    for tx in txs:
        net += tx.amount
        if tx.transaction_type == CashbackTransaction.TYPE_WALLET:
            wallet_credited += -tx.amount
        if tx.program_id:
            program = tx.program
    if wallet_credited > 0:
        from logic.wallet import adjust_wallet

        withdraw = min(_money(customer.wallet_balance), wallet_credited)
        if withdraw > 0:
            adjust_wallet(
                customer,
                -withdraw,
                description=f"برگشت شارژ کش‌بک فاکتور {sale.invoice_number or sale.pk}",
                user=user,
                transaction_type="refund",
                sale=None,
            )
    if net != 0:
        _post(
            customer,
            -net,
            CashbackTransaction.TYPE_REVERSAL,
            program=program,
            sale=sale,
            user=user,
            description=f"برگشت کش‌بک فاکتور {sale.invoice_number or sale.pk}",
        )


def program_to_dict(program):
    return {
        "id": program.id,
        "name": program.name,
        "is_active": program.is_active,
        "sort_order": program.sort_order,
        "description": program.description or "",
        "earn_percent": float(program.earn_percent),
        "base_usable_percent": float(program.base_usable_percent),
        "redeem_mode": program.redeem_mode,
        "redeem_mode_display": program.get_redeem_mode_display(),
        "segment_ids": list(program.segments.values_list("id", flat=True)),
        "unlock_steps": [
            {
                "id": step.id,
                "extra_purchase_percent": float(step.extra_purchase_percent),
                "extra_usable_percent": float(step.extra_usable_percent),
            }
            for step in program.unlock_steps.all()
        ],
    }


def _replace_unlock_steps(program, rows):
    program.unlock_steps.all().delete()
    if not rows:
        return
    seen = []
    for row in rows:
        extra_purchase = _clamp_percent(row.get("extra_purchase_percent"))
        extra_usable = _clamp_percent(row.get("extra_usable_percent"))
        seen.append(
            CashbackUnlockStep(
                program=program,
                extra_purchase_percent=extra_purchase,
                extra_usable_percent=extra_usable,
            )
        )
    CashbackUnlockStep.objects.bulk_create(seen)


def _apply_program_payload(program, data, *, creating):
    if creating or "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("نام برنامه الزامی است.")
        program.name = name
    if creating or "description" in data:
        program.description = (data.get("description") or "").strip()
    if creating or "is_active" in data:
        program.is_active = bool(data.get("is_active", True if creating else program.is_active))
    if creating or "sort_order" in data:
        try:
            program.sort_order = max(0, int(data.get("sort_order") or 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("اولویت نامعتبر است.") from exc
    if creating or "earn_percent" in data:
        program.earn_percent = _clamp_percent(data.get("earn_percent", 0))
    if creating or "base_usable_percent" in data:
        default = 100 if creating else program.base_usable_percent
        program.base_usable_percent = _clamp_percent(data.get("base_usable_percent", default))
    if creating or "redeem_mode" in data:
        mode = (data.get("redeem_mode") or CashbackProgram.REDEEM_MANUAL).strip()
        valid = {item[0] for item in CashbackProgram.REDEEM_CHOICES}
        if mode not in valid:
            raise ValueError("حالت مصرف نامعتبر است.")
        program.redeem_mode = mode
    return program


def create_program(data):
    program = _apply_program_payload(CashbackProgram(), data, creating=True)
    program.save()
    segment_ids = data.get("segment_ids") or []
    if segment_ids:
        program.segments.set(segment_ids)
    _replace_unlock_steps(program, data.get("unlock_steps") or [])
    return program


def update_program(program, data):
    _apply_program_payload(program, data, creating=False)
    program.save()
    if "segment_ids" in data:
        program.segments.set(data.get("segment_ids") or [])
    if "unlock_steps" in data:
        _replace_unlock_steps(program, data.get("unlock_steps") or [])
    return program


def list_programs():
    return CashbackProgram.objects.prefetch_related("segments", "unlock_steps").all()
