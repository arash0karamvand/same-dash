"""منطق حسابداری فروش، پرداخت بخشی و مطالبات (بستانکاری)."""

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from backend.models import AccountingEntry, Sale
from logic.levels import update_customer_level


def balance_due(sale):
    return max(Decimal(0), sale.final_amount - sale.paid_amount)


def normalize_payment_status(status):
    if status == "partial":
        return "installment"
    return status


def resolve_discount_amount(amount, discount_type, discount_value, customer=None):
    """محاسبه تخفیف نهایی (تومان) از نوع و مقدار ورودی."""
    amount = Decimal(amount)
    discount_value = Decimal(discount_value or 0)
    discount_type = (discount_type or "amount").strip()

    if discount_type == "percent":
        if discount_value < 0 or discount_value > 100:
            raise ValueError("درصد تخفیف باید بین ۰ تا ۱۰۰ باشد.")
        discount = (amount * discount_value / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    elif discount_type == "wallet":
        if customer is None:
            raise ValueError("برای استفاده از موجودی حساب، مشتری الزامی است.")
        wallet = Decimal(customer.wallet_balance)
        if wallet <= 0:
            raise ValueError("موجودی کیف پول مشتری کافی نیست.")
        use = discount_value if discount_value > 0 else wallet
        discount = min(use, wallet, amount)
        if discount <= 0:
            raise ValueError("مبلغ استفاده از کیف پول نامعتبر است.")
    else:
        discount = discount_value

    if discount < 0:
        raise ValueError("تخفیف نمی‌تواند منفی باشد.")
    if discount > amount:
        raise ValueError("تخفیف نمی‌تواند از مبلغ فروش بیشتر باشد.")
    return discount


def _resolve_paid_amount(payment_status, final_amount, paid_amount):
    paid = Decimal(paid_amount or 0)
    if payment_status in ("partial", "installment"):
        payment_status = "installment"
        if paid <= 0:
            raise ValueError("برای فروش قسطی، مبلغ پرداخت‌شده اولیه باید بزرگ‌تر از صفر باشد.")
        if paid >= final_amount:
            raise ValueError("مبلغ پرداخت‌شده باید کمتر از مبلغ نهایی باشد.")
        return paid, "installment"
    if payment_status == "paid":
        return final_amount, "paid"
    if payment_status == "unpaid":
        return Decimal(0), "unpaid"
    raise ValueError("وضعیت پرداخت نامعتبر است.")


def _apply_wallet_discount(customer, amount, sale, user=None):
    if amount <= 0:
        return
    from logic.wallet import adjust_wallet

    adjust_wallet(
        customer,
        -amount,
        description=f"پرداخت فروش فاکتور {sale.invoice_number or sale.pk}",
        user=user,
        transaction_type="sale",
        sale=sale,
    )


def _refund_wallet_discount(customer, amount, sale, user=None):
    if amount <= 0:
        return
    from logic.wallet import adjust_wallet

    adjust_wallet(
        customer,
        amount,
        description=f"بازگشت کیف پول — فاکتور {sale.invoice_number or sale.pk}",
        user=user,
        transaction_type="refund",
        sale=None,
    )


def _apply_purchase_to_customer(customer, amount, sold_at, reason, user=None):
    amount = Decimal(amount)
    if amount <= 0:
        return
    customer.total_purchases += amount
    customer.last_purchase_at = sold_at
    customer.save(update_fields=["total_purchases", "last_purchase_at"])
    update_customer_level(customer, reason=reason, user=user)


def _reverse_purchase_from_customer(customer, amount):
    """کاهش مجموع خرید مشتری — معکوس ثبت فروش/پرداخت."""
    amount = Decimal(amount)
    if amount <= 0:
        return
    customer.total_purchases = max(Decimal(0), customer.total_purchases - amount)
    customer.save(update_fields=["total_purchases"])


def _refresh_customer_last_purchase(customer, exclude_sale_id=None):
    """آخرین تاریخ خرید را از فروش‌های باقی‌مانده مشتری به‌روز می‌کند."""
    qs = Sale.objects.filter(customer=customer).order_by("-sold_at")
    if exclude_sale_id:
        qs = qs.exclude(pk=exclude_sale_id)
    last_sale = qs.first()
    customer.last_purchase_at = last_sale.sold_at if last_sale else None
    customer.save(update_fields=["last_purchase_at"])


def _create_sale_accounting(sale, outstanding):
    """سند درآمد (بستانکار) + در صورت مانده، سند مطالبات (بدهکار مشتری)."""
    AccountingEntry.objects.create(
        entry_type="sale",
        credit=sale.final_amount,
        amount=sale.final_amount,
        description=f"درآمد فروش فاکتور {sale.invoice_number or sale.pk}",
        sale=sale,
    )
    if outstanding > 0:
        AccountingEntry.objects.create(
            entry_type="receivable",
            debit=outstanding,
            amount=outstanding,
            description=f"مطالبات مشتری فاکتور {sale.invoice_number or sale.pk}",
            sale=sale,
        )


def _sync_receivable_entry(sale):
    """به‌روزرسانی سند مطالبات بر اساس مانده فعلی."""
    outstanding = balance_due(sale)
    receivable = AccountingEntry.objects.filter(sale=sale, entry_type="receivable").first()
    if outstanding <= 0:
        if receivable:
            receivable.delete()
        return
    if receivable:
        receivable.debit = outstanding
        receivable.amount = outstanding
        receivable.save(update_fields=["debit", "amount"])
    else:
        AccountingEntry.objects.create(
            entry_type="receivable",
            debit=outstanding,
            amount=outstanding,
            description=f"مطالبات مشتری فاکتور {sale.invoice_number or sale.pk}",
            sale=sale,
        )


@transaction.atomic
def record_sale(
    customer,
    amount,
    discount=0,
    discount_type="amount",
    discount_value=None,
    payment_method="cash",
    payment_status="paid",
    paid_amount=None,
    installments=None,
    line_items=None,
    invoice_number="",
    description="",
    sold_at=None,
    recorded_by=None,
    branch="",
    seller=None,
):
    if line_items:
        amount = Decimal(0)
        for item in line_items:
            qty = int(item.get("quantity") or 1)
            price = Decimal(str(item.get("unit_price") or 0))
            amount += price * qty
    amount = Decimal(amount)
    discount_type = (discount_type or "amount").strip()
    if discount_value is None:
        discount_value = discount
    discount = resolve_discount_amount(amount, discount_type, discount_value, customer=customer)
    if amount <= 0:
        raise ValueError("مبلغ فروش باید مثبت باشد.")

    final_amount = amount - discount
    payment_status = normalize_payment_status(payment_status)
    resolved_paid, resolved_status = _resolve_paid_amount(
        payment_status, final_amount, paid_amount if paid_amount is not None else (final_amount if payment_status == "paid" else 0)
    )
    outstanding = final_amount - resolved_paid

    sale_kwargs = {
        "customer": customer,
        "amount": amount,
        "discount_type": discount_type,
        "discount_value": Decimal(discount_value or 0),
        "discount": discount,
        "final_amount": final_amount,
        "paid_amount": resolved_paid,
        "payment_method": payment_method,
        "payment_status": resolved_status,
        "invoice_number": invoice_number,
        "description": description,
        "recorded_by": recorded_by,
        "branch": branch or "",
        "seller": seller,
    }
    if sold_at is not None:
        sale_kwargs["sold_at"] = sold_at
    sale = Sale.objects.create(**sale_kwargs)

    if discount_type == "wallet" and discount > 0:
        customer.refresh_from_db(fields=["wallet_balance"])
        _apply_wallet_discount(customer, discount, sale, user=recorded_by)

    if line_items:
        from backend.models import SaleLineItem

        for item in line_items:
            from logic.products import resolve_line_item_from_catalog

            resolved = resolve_line_item_from_catalog(item)
            if not resolved:
                continue
            qty = resolved["quantity"]
            price = resolved["unit_price"]
            product = resolved["product"]
            variant = resolved["variant"]
            name = resolved["product_name"]
            if resolved["color_name"] and resolved["color_name"] not in name:
                name = f"{name} — {resolved['color_name']}"
            SaleLineItem.objects.create(
                sale=sale,
                product=product,
                variant=variant,
                product_name=name,
                color_name=resolved["color_name"],
                color_hex=resolved["color_hex"],
                quantity=qty,
                unit_price=price,
                line_total=price * qty,
            )

    _create_sale_accounting(sale, outstanding)
    _apply_purchase_to_customer(
        customer,
        resolved_paid,
        sale.sold_at,
        reason="ثبت فروش (مبلغ پرداخت‌شده)",
        user=recorded_by,
    )
    if installments:
        from logic.installments import create_installments

        create_installments(sale, installments)
    return sale


@transaction.atomic
def delete_sale(sale, user=None):
    """حذف فروش و بازگرداندن اثرات آن روی مشتری، کیف پول، اقساط و حسابداری."""
    from logic.accounting import delete_entries_for_sale

    customer = sale.customer
    paid_amount = sale.paid_amount
    wallet_used = sale.discount if sale.discount_type == "wallet" else Decimal(0)

    for inst in sale.installments.all():
        if not inst.is_deleted:
            inst.soft_delete()

    deleted_entries = delete_entries_for_sale(sale)

    if wallet_used > 0:
        _refund_wallet_discount(customer, wallet_used, sale, user=user)

    _reverse_purchase_from_customer(customer, paid_amount)
    _refresh_customer_last_purchase(customer, exclude_sale_id=sale.pk)
    update_customer_level(
        customer,
        reason=f"حذف فروش #{sale.pk}",
        user=user,
        send_level_up_sms=False,
    )

    sale.soft_delete()
    return deleted_entries


@transaction.atomic
def record_payment(sale, amount, description="", recorded_by=None):
    """ثبت پرداخت/قسط جدید روی فروش — کاهش مطالبات و به‌روزرسانی سطح مشتری."""
    amount = Decimal(amount)
    if amount <= 0:
        raise ValueError("مبلغ پرداخت باید مثبت باشد.")

    due = balance_due(sale)
    if due <= 0:
        raise ValueError("این فاکتور مانده‌ای ندارد.")
    if amount > due:
        raise ValueError("مبلغ پرداخت بیش از مانده فاکتور است.")

    sale.paid_amount += amount
    sale.payment_status = "paid" if sale.paid_amount >= sale.final_amount else "installment"
    sale.save(update_fields=["paid_amount", "payment_status"])

    AccountingEntry.objects.create(
        entry_type="payment",
        credit=amount,
        amount=amount,
        description=description or f"دریافت پرداخت فاکتور {sale.invoice_number or sale.pk}",
        sale=sale,
    )
    _sync_receivable_entry(sale)
    _apply_purchase_to_customer(
        sale.customer,
        amount,
        sale.sold_at,
        reason="دریافت پرداخت فاکتور",
        user=recorded_by,
    )
    return sale


@transaction.atomic
def update_sale(
    sale,
    *,
    amount=None,
    discount=None,
    discount_type=None,
    discount_value=None,
    paid_amount=None,
    **meta_fields,
):
    """ویرایش فروش — مبلغ، تخفیف، پرداخت‌شده و فیلدهای متنی."""
    old_paid = sale.paid_amount
    old_wallet = sale.discount if sale.discount_type == "wallet" else Decimal(0)
    customer = sale.customer

    if amount is not None:
        sale.amount = Decimal(str(amount))
    if discount_type is not None:
        sale.discount_type = (discount_type or "amount").strip()
    if discount_value is not None:
        sale.discount_value = Decimal(str(discount_value or 0))
    elif discount is not None and sale.discount_type == "amount":
        sale.discount_value = Decimal(str(discount or 0))

    if old_wallet > 0:
        _refund_wallet_discount(customer, old_wallet, sale)

    sale.discount = resolve_discount_amount(
        sale.amount, sale.discount_type, sale.discount_value, customer=customer
    )
    if sale.discount_type == "wallet" and sale.discount > 0:
        customer.refresh_from_db(fields=["wallet_balance"])
        _apply_wallet_discount(customer, sale.discount, sale)

    if sale.amount <= 0:
        raise ValueError("مبلغ فروش باید مثبت باشد.")

    sale.final_amount = sale.amount - sale.discount

    if paid_amount is not None:
        sale.paid_amount = Decimal(str(paid_amount))
    elif sale.paid_amount > sale.final_amount:
        raise ValueError("مبلغ پرداخت‌شده بیش از مبلغ نهایی است. ابتدا مبلغ را افزایش دهید.")

    if sale.paid_amount < 0:
        raise ValueError("مبلغ پرداخت‌شده نامعتبر است.")
    if sale.paid_amount > sale.final_amount:
        raise ValueError("مبلغ پرداخت‌شده نمی‌تواند از مبلغ نهایی بیشتر باشد.")

    if sale.paid_amount >= sale.final_amount:
        sale.payment_status = "paid"
    elif sale.paid_amount > 0:
        sale.payment_status = "installment"
    else:
        sale.payment_status = "unpaid"

    for field in ("description", "invoice_number", "payment_method"):
        if field in meta_fields:
            setattr(sale, field, (meta_fields[field] or "").strip())

    sale.save()

    sale_entry = AccountingEntry.objects.filter(sale=sale, entry_type="sale").first()
    if sale_entry:
        sale_entry.credit = sale.final_amount
        sale_entry.amount = sale.final_amount
        sale_entry.save(update_fields=["credit", "amount"])

    _sync_receivable_entry(sale)

    paid_delta = sale.paid_amount - old_paid
    if paid_delta != 0:
        _apply_purchase_to_customer(
            sale.customer,
            paid_delta,
            sale.sold_at,
            reason="اصلاح مبلغ پرداخت‌شده فاکتور",
        )

    return sale


def sales_summary(queryset):
    total = Decimal(0)
    count = 0
    for sale in queryset:
        total += sale.final_amount
        count += 1
    return {"count": count, "total_amount": int(total)}
