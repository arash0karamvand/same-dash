"""منطق حسابداری فروش، پرداخت بخشی و مطالبات (بستانکاری)."""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from backend.models import JournalEntry, JournalLine, Sale
from logic.accounting import create_accounting_entry, create_journal
from logic.rfm import recalculate_customer_rfm


def balance_due(sale):
    return max(Decimal(0), sale.final_amount - sale.paid_amount)


def is_pre_invoice_pending(sale):
    return sale.order_kind == Sale.ORDER_KIND_PRE_INVOICE and sale.order_status == Sale.ORDER_STATUS_PENDING


def is_order_cancelled(sale):
    return sale.order_status == Sale.ORDER_STATUS_CANCELLED


def normalize_order_kind(kind):
    kind = (kind or Sale.ORDER_KIND_NORMAL).strip()
    valid = {Sale.ORDER_KIND_NORMAL, Sale.ORDER_KIND_PRE_INVOICE, Sale.ORDER_KIND_DEPOSIT}
    if kind not in valid:
        return Sale.ORDER_KIND_NORMAL
    return kind


def normalize_payment_status(status):
    if status == "partial":
        return "installment"
    return status


VALID_PAYMENT_METHODS = frozenset({"cash", "card", "check"})


def normalize_payment_method(method, default="cash"):
    value = (method or default).strip()
    if value not in VALID_PAYMENT_METHODS:
        raise ValueError("روش پرداخت باید نقدی، کارت‌خوان یا چک باشد.")
    return value


def resolve_discount_amount(amount, discount_type, discount_value, customer=None, exclude_sale_id=None):
    """محاسبه تخفیف نهایی (ریال) از نوع و مقدار ورودی."""
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
    elif discount_type == "cashback":
        if customer is None:
            raise ValueError("برای استفاده از کش‌بک، مشتری الزامی است.")
        from logic.cashback import quote_cashback

        quote = quote_cashback(customer, amount, exclude_sale_id=exclude_sale_id)
        cap = Decimal(quote["usable_amount"])
        if cap <= 0:
            raise ValueError("کش‌بک قابل‌استفاده برای این فاکتور وجود ندارد.")
        use = discount_value if discount_value > 0 else cap
        discount = min(use, cap, amount)
        if discount <= 0:
            raise ValueError("مبلغ استفاده از کش‌بک نامعتبر است.")
    else:
        discount = discount_value

    if discount < 0:
        raise ValueError("تخفیف نمی‌تواند منفی باشد.")
    if discount > amount:
        raise ValueError("تخفیف نمی‌تواند از مبلغ فروش بیشتر باشد.")
    return discount


def _resolve_paid_amount(payment_status, final_amount, paid_amount, *, allow_partial=True):
    paid = Decimal(paid_amount or 0)
    if payment_status in ("partial", "installment"):
        payment_status = "installment"
        if paid < 0:
            raise ValueError("مبلغ پرداخت‌شده نمی‌تواند منفی باشد.")
        if allow_partial and paid >= final_amount:
            return final_amount, "paid"
        if paid >= final_amount:
            raise ValueError("مبلغ پرداخت‌شده باید کمتر از مبلغ نهایی باشد.")
        return paid, "installment" if paid > 0 else "unpaid"
    if payment_status == "paid":
        return final_amount, "paid"
    if payment_status == "unpaid":
        if paid > 0 and allow_partial:
            return paid, "installment" if paid < final_amount else "paid"
        return Decimal(0), "unpaid"
    raise ValueError("وضعیت پرداخت نامعتبر است.")


def _payment_status_from_paid(final_amount, paid_amount):
    paid = Decimal(paid_amount or 0)
    if paid >= final_amount:
        return "paid"
    if paid > 0:
        return "installment"
    return "unpaid"


def _record_deposit_payment(sale, amount, description="", recorded_by=None):
    """ثبت دریافت بیعانه — بدهکار بانک/صندوق."""
    amount = Decimal(amount)
    if amount <= 0:
        return
    from logic.accounting import assign_document_code, assign_document_number, generate_document_code, next_document_number
    from logic.accounting_accounts import payment_account_for_sale

    doc_num = next_document_number(entry_date=sale.sold_at)
    doc_code = generate_document_code(entry_date=sale.sold_at)
    create_accounting_entry(
        entry_type="payment",
        account=payment_account_for_sale(sale),
        debit=amount,
        amount=amount,
        description=description or f"بیعانه فاکتور {sale.invoice_number or sale.pk}",
        sale=sale,
        is_approved=True,
        document_code=doc_code,
        document_number=doc_num,
        entry_date=sale.sold_at,
    )
    _apply_purchase_to_customer(
        sale.customer,
        amount,
        sale.sold_at,
        reason="دریافت بیعانه",
        user=recorded_by,
        sale=sale,
    )


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


def _apply_purchase_to_customer(customer, amount, sold_at, reason, user=None, sale=None):
    amount = Decimal(amount)
    if amount <= 0:
        return
    customer.last_purchase_at = sold_at
    customer.save(update_fields=["last_purchase_at"])
    recalculate_customer_rfm(customer, user=user)
    if sale is not None:
        from logic.cashback import accrue_cashback

        accrue_cashback(customer, sale=sale, user=user)


def _reverse_purchase_from_customer(customer, amount):
    """Purchases are derived from Sale rows; no stored counter is mutated."""
    amount = Decimal(amount)
    if amount <= 0:
        return


def _refresh_customer_last_purchase(customer, exclude_sale_id=None):
    """آخرین تاریخ خرید را از فروش‌های باقی‌مانده مشتری به‌روز می‌کند."""
    qs = Sale.objects.filter(customer=customer).order_by("-sold_at")
    if exclude_sale_id:
        qs = qs.exclude(pk=exclude_sale_id)
    last_sale = qs.first()
    customer.last_purchase_at = last_sale.sold_at if last_sale else None
    customer.save(update_fields=["last_purchase_at"])


def _create_sale_accounting(sale, outstanding, *, is_approved=True, force=False):
    """سند فروش — بستانکار درآمد (7240) + بدهکار مطالبات (1310) و/یا بانک (1210)."""
    if is_pre_invoice_pending(sale):
        return
    if not force and JournalEntry.objects.filter(
        order_links__order=sale, entry_type_ref_id="sale"
    ).exclude(status_ref_id=JournalEntry.STATUS_VOID).exists():
        return

    from logic.accounting import generate_document_code, next_document_number
    from logic.accounting_accounts import payment_account_for_sale

    doc_num = next_document_number(entry_date=sale.sold_at)
    doc_code = generate_document_code(entry_date=sale.sold_at)
    paid = Decimal(sale.paid_amount or 0)
    final_amount = Decimal(sale.final_amount or 0)
    outstanding = Decimal(outstanding or 0)

    from logic.posting import build_journal_lines

    desc = f"فروش فاکتور {sale.invoice_number or sale.pk}"
    lines = build_journal_lines(
        "sale",
        amounts={"final_amount": final_amount, "outstanding": outstanding, "paid": paid},
        accounts={"payment_account": payment_account_for_sale(sale)},
        description=desc,
    )
    create_journal(
        lines=lines, entry_type="sale", description=desc,
        sale=sale, is_approved=is_approved, document_code=doc_code,
        document_number=doc_num, entry_date=sale.sold_at,
    )


def ensure_draft_sale_accounting(sale):
    """پیش‌نویس سند حسابداری هنگام ارسال به اداری — فقط حالت خودکار."""
    from backend.models import Sale

    if sale.accounting_mode != Sale.ACCOUNTING_MODE_AUTOMATIC:
        return
    # The normalized journal phase may not yet expose the legacy reverse link.
    if is_pre_invoice_pending(sale):
        return
    if sale.journal_links.exists():
        return
    _create_sale_accounting(sale, balance_due(sale), is_approved=False)


def _create_pre_invoice_deposit_accounting(sale, paid_amount, recorded_by=None):
    """پیش‌فاکتور: فقط ثبت بیعانه دریافتی."""
    if paid_amount > 0:
        _record_deposit_payment(
            sale,
            paid_amount,
            description=f"بیعانه پیش‌فاکتور {sale.invoice_number or sale.pk}",
            recorded_by=recorded_by,
        )


def _sync_receivable_entry(sale):
    """Payments are separate journals; the original sale journal remains immutable."""
    if is_pre_invoice_pending(sale) or is_order_cancelled(sale):
        return
    return


def _create_deposit_installment(sale, delivery_date, payment_method="cash"):
    """قسط تسویه یک روز قبل از تحویل — برای بیعانیه."""
    balance = balance_due(sale)
    if balance <= 0 or not delivery_date:
        return
    due = delivery_date - timedelta(days=1)
    from logic.installments import create_installments

    create_installments(
        sale,
        [
            {
                "amount": int(balance),
                "due_date": due.isoformat(),
                "payment_method": payment_method,
                "notes": "تسویه قبل از تحویل",
            }
        ],
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
    order_kind=Sale.ORDER_KIND_NORMAL,
    delivery_date=None,
    accounting_mode=None,
    stock_source=None,
):
    if recorded_by is not None:
        from logic.sale_attendance import assert_user_can_record_sale

        assert_user_can_record_sale(recorded_by)

    resolved_items = None
    if line_items:
        from logic.products import resolve_line_item_from_catalog

        resolved_items = []
        amount = Decimal(0)
        for item in line_items:
            resolved = resolve_line_item_from_catalog(item)
            if not resolved:
                raise ValueError("هر ردیف فروش باید از کاتالوگ محصولات انتخاب شود.")
            resolved_items.append(resolved)
            amount += Decimal(resolved["unit_price"]) * resolved["quantity"]
    amount = Decimal(amount)
    discount_type = (discount_type or "amount").strip()
    if discount_value is None:
        discount_value = discount
    from logic.cashback import maybe_autoselect_cashback_discount

    discount_type, discount_value = maybe_autoselect_cashback_discount(
        customer, amount, discount_type, discount_value
    )
    discount = resolve_discount_amount(amount, discount_type, discount_value, customer=customer)
    payment_method = normalize_payment_method(payment_method)
    from logic.accounting_accounts import resolve_sale_accounting_mode

    resolved_accounting_mode = resolve_sale_accounting_mode(accounting_mode, payment_method)
    if amount <= 0:
        raise ValueError("مبلغ فروش باید مثبت باشد.")

    final_amount = amount - discount
    order_kind = normalize_order_kind(order_kind)

    if order_kind == Sale.ORDER_KIND_DEPOSIT and not delivery_date:
        raise ValueError("برای بیعانیه، تاریخ تحویل الزامی است.")

    if order_kind == Sale.ORDER_KIND_PRE_INVOICE:
        payment_status = normalize_payment_status(payment_status or "unpaid")
        resolved_paid, resolved_status = _resolve_paid_amount(
            payment_status,
            final_amount,
            paid_amount if paid_amount is not None else 0,
            allow_partial=True,
        )
        order_status = Sale.ORDER_STATUS_PENDING
    elif order_kind == Sale.ORDER_KIND_DEPOSIT:
        initial_paid = Decimal(paid_amount or 0)
        if initial_paid < 0:
            raise ValueError("مبلغ بیعانه نمی‌تواند منفی باشد.")
        if initial_paid > final_amount:
            raise ValueError("مبلغ بیعانه نمی‌تواند از مبلغ نهایی بیشتر باشد.")
        resolved_paid = initial_paid
        resolved_status = _payment_status_from_paid(final_amount, resolved_paid)
        order_status = Sale.ORDER_STATUS_PENDING
    else:
        payment_status = normalize_payment_status(payment_status)
        resolved_paid, resolved_status = _resolve_paid_amount(
            payment_status,
            final_amount,
            paid_amount if paid_amount is not None else (final_amount if payment_status == "paid" else 0),
            allow_partial=False,
        )
        order_status = Sale.ORDER_STATUS_CONFIRMED

    from logic.sale_workflow import STAGE_PENDING_BRANCH, uses_workflow_on_create

    workflow_stage = Sale.WORKFLOW_STAGE_COMPLETED
    defer_accounting = False
    if recorded_by and uses_workflow_on_create(recorded_by):
        workflow_stage = STAGE_PENDING_BRANCH
        order_status = Sale.ORDER_STATUS_PENDING
        defer_accounting = True

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
        "accounting_mode": resolved_accounting_mode,
        "invoice_number": invoice_number,
        "description": description,
        "recorded_by": recorded_by,
        "branch_id": branch or "branch_1",
        "seller": seller,
        "order_kind": order_kind,
        "order_status": order_status,
        "workflow_stage_id": workflow_stage,
        "delivery_date": delivery_date,
        "office_released_at": None,
        "factory_released_at": None,
    }
    from logic.stock_locations import LOCATION_WAREHOUSE, default_warehouse, parse_location

    location = None
    if stock_source:
        location = parse_location(stock_source, required=True)
    elif line_items:
        warehouse = default_warehouse()
        location = parse_location({"kind": LOCATION_WAREHOUSE, "warehouse_id": warehouse.id}, required=True)
    if location:
        sale_kwargs["stock_source_kind"] = location["kind"]
        if location["kind"] == LOCATION_WAREHOUSE:
            sale_kwargs["stock_source_warehouse"] = location["warehouse"]
        else:
            sale_kwargs["stock_source_branch"] = location["branch"]
    if sold_at is not None:
        sale_kwargs["sold_at"] = sold_at
    sale = Sale.objects.create(**sale_kwargs)
    from backend.models import OrderTransition, WorkflowStage

    OrderTransition.objects.create(
        order=sale,
        from_stage=None,
        to_stage=WorkflowStage.objects.get(code=workflow_stage),
        actor=recorded_by,
        note="ثبت سفارش",
    )

    if discount_type == "wallet" and discount > 0:
        _apply_wallet_discount(customer, discount, sale, user=recorded_by)
    if discount_type == "cashback" and discount > 0:
        from logic.cashback import apply_cashback_spend

        apply_cashback_spend(customer, sale, discount, user=recorded_by)

    if resolved_items:
        from backend.models import SaleLineItem

        for resolved in resolved_items:
            qty = resolved["quantity"]
            price = resolved["unit_price"]
            product = resolved["product"]
            variant = resolved["variant"]
            name = resolved["product_name"]
            SaleLineItem.objects.create(
                sale=sale,
                product=product,
                variant=variant,
                product_name=name,
                product_model=resolved["product_model"],
                fabric=resolved["fabric"],
                color_name=resolved["color_name"],
                color_hex=resolved["color_hex"],
                quantity=qty,
                unit_price=price,
                line_total=price * qty,
            )
        from logic.products import deduct_variant_stock_for_sale

        deduct_variant_stock_for_sale(sale, recorded_by=recorded_by)

    if order_kind == Sale.ORDER_KIND_PRE_INVOICE:
        if not defer_accounting:
            _create_pre_invoice_deposit_accounting(sale, resolved_paid, recorded_by=recorded_by)
    elif order_kind == Sale.ORDER_KIND_DEPOSIT:
        if not defer_accounting:
            _create_sale_accounting(sale, outstanding)
        elif resolved_accounting_mode == Sale.ACCOUNTING_MODE_AUTOMATIC:
            _create_sale_accounting(sale, outstanding, is_approved=False)
    elif not defer_accounting:
        _create_sale_accounting(sale, outstanding)
        _apply_purchase_to_customer(
            customer,
            resolved_paid,
            sale.sold_at,
            reason="ثبت فروش (مبلغ پرداخت‌شده)",
            user=recorded_by,
            sale=sale,
        )
    elif resolved_accounting_mode == Sale.ACCOUNTING_MODE_AUTOMATIC:
        _create_sale_accounting(sale, outstanding, is_approved=False)
        _apply_purchase_to_customer(
            customer,
            resolved_paid,
            sale.sold_at,
            reason="ثبت فروش (مبلغ پرداخت‌شده)",
            user=recorded_by,
            sale=sale,
        )

    if order_kind == Sale.ORDER_KIND_DEPOSIT:
        _create_deposit_installment(sale, delivery_date, payment_method=payment_method)
    elif installments:
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

    from logic.cashback import reverse_sale_cashback

    reverse_sale_cashback(customer, sale, user=user)

    from logic.products import restore_variant_stock_for_sale

    restore_variant_stock_for_sale(sale, recorded_by=user)

    _reverse_purchase_from_customer(customer, paid_amount)
    _refresh_customer_last_purchase(customer, exclude_sale_id=sale.pk)

    from logic.order_queues import soft_delete_workflow_orders_for_sale

    soft_delete_workflow_orders_for_sale(sale)
    sale.soft_delete()
    recalculate_customer_rfm(
        customer,
        user=user,
        send_level_up_sms=False,
    )
    return deleted_entries


@transaction.atomic
def record_payment(sale, amount, description="", recorded_by=None, account=None):
    """ثبت پرداخت/قسط جدید روی فروش — کاهش مطالبات و به‌روزرسانی سطح مشتری."""
    if is_order_cancelled(sale):
        raise ValueError("این سفارش لغو شده و قابل پرداخت نیست.")

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

    if is_pre_invoice_pending(sale):
        _record_deposit_payment(
            sale,
            amount,
            description=description or f"بیعانه پیش‌فاکتور {sale.invoice_number or sale.pk}",
            recorded_by=recorded_by,
        )
        return sale

    from logic.accounting_accounts import payment_account_for_sale
    from logic.posting import build_journal_lines

    desc = description or f"دریافت پرداخت فاکتور {sale.invoice_number or sale.pk}"
    lines = build_journal_lines(
        "payment",
        amounts={"amount": amount},
        accounts={"payment_account": account or payment_account_for_sale(sale)},
        description=desc,
    )
    create_journal(
        lines=lines, entry_type="payment", description=description, sale=sale, is_approved=True,
    )
    _sync_receivable_entry(sale)
    _apply_purchase_to_customer(
        sale.customer,
        amount,
        sale.sold_at,
        reason="دریافت پرداخت فاکتور",
        user=recorded_by,
        sale=sale,
    )

    return sale


@transaction.atomic
def reverse_payment(sale, amount, user=None):
    """برگرداندن یک پرداخت ثبت‌شده — معکوس record_payment."""
    if is_order_cancelled(sale):
        raise ValueError("این سفارش لغو شده است.")

    amount = Decimal(amount)
    if amount <= 0:
        raise ValueError("مبلغ بازگشت باید مثبت باشد.")
    if sale.paid_amount < amount:
        raise ValueError("مبلغ بازگشت بیش از پرداخت‌شده فاکتور است.")

    sale.paid_amount -= amount
    sale.payment_status = _payment_status_from_paid(sale.final_amount, sale.paid_amount)
    sale.save(update_fields=["paid_amount", "payment_status"])

    _sync_receivable_entry(sale)
    _reverse_purchase_from_customer(sale.customer, amount)
    recalculate_customer_rfm(
        sale.customer,
        user=user,
        send_level_up_sms=False,
    )

    return sale


@transaction.atomic
def confirm_pre_invoice(sale, recorded_by=None):
    """تایید پیش‌فاکتور — تبدیل به فروش قطعی با ثبت درآمد و مطالبات."""
    if sale.order_kind != Sale.ORDER_KIND_PRE_INVOICE:
        raise ValueError("فقط پیش‌فاکتور قابل تایید است.")
    if sale.order_status != Sale.ORDER_STATUS_PENDING:
        raise ValueError("این پیش‌فاکتور قبلاً تایید یا لغو شده است.")

    sale.order_status = Sale.ORDER_STATUS_CONFIRMED
    sale.save(update_fields=["order_status"])

    outstanding = balance_due(sale)
    _create_sale_accounting(sale, outstanding)
    _sync_receivable_entry(sale)
    return sale


@transaction.atomic
def cancel_order(sale, recorded_by=None):
    """لغو پیش‌فاکتور یا بیعانیه."""
    if sale.order_status == Sale.ORDER_STATUS_CANCELLED:
        raise ValueError("این سفارش قبلاً لغو شده است.")
    if sale.order_kind not in (Sale.ORDER_KIND_PRE_INVOICE, Sale.ORDER_KIND_DEPOSIT):
        raise ValueError("فقط پیش‌فاکتور یا بیعانیه قابل لغو از این مسیر است.")
    if sale.order_status != Sale.ORDER_STATUS_PENDING:
        raise ValueError("فقط سفارش‌های در انتظار قابل لغو هستند.")

    paid = sale.paid_amount
    customer = sale.customer

    for inst in sale.installments.filter(is_deleted=False):
        if inst.status == "pending":
            inst.status = "cancelled"
            inst.save(update_fields=["status"])

    if paid > 0:
        create_accounting_entry(
            entry_type="refund",
            debit=paid,
            amount=paid,
            description=f"بازگشت بیعانه — فاکتور {sale.invoice_number or sale.pk}",
            sale=sale,
        )
        _reverse_purchase_from_customer(customer, paid)
        JournalEntry.objects.filter(
            order_links__order=sale, entry_type_ref_id="payment"
        ).delete()

    if sale.order_kind == Sale.ORDER_KIND_PRE_INVOICE:
        JournalEntry.objects.filter(
            order_links__order=sale, entry_type_ref_id__in=("sale", "receivable")
        ).delete()
    elif sale.order_kind == Sale.ORDER_KIND_DEPOSIT:
        JournalEntry.objects.filter(
            order_links__order=sale, entry_type_ref_id__in=("sale", "receivable")
        ).delete()

    sale.order_status = Sale.ORDER_STATUS_CANCELLED
    sale.save(update_fields=["order_status"])
    from logic.products import restore_variant_stock_for_sale

    restore_variant_stock_for_sale(sale, recorded_by=recorded_by)
    from logic.cashback import reverse_sale_cashback

    reverse_sale_cashback(customer, sale, user=recorded_by)
    recalculate_customer_rfm(customer, user=recorded_by, send_level_up_sms=False)
    return sale


def _replace_sale_line_items(sale, line_items):
    """جایگزینی اقلام فاکتور — مبلغ جدید از جمع ردیف‌ها."""
    from backend.models import SaleLineItem
    from logic.products import (
        deduct_variant_stock_for_sale,
        resolve_line_item_from_catalog,
        restore_variant_stock_for_sale,
    )

    resolved_items = []
    amount = Decimal(0)
    for item in line_items:
        resolved = resolve_line_item_from_catalog(item)
        if not resolved:
            raise ValueError("هر ردیف فروش باید از کاتالوگ محصولات انتخاب شود.")
        resolved_items.append(resolved)
        amount += Decimal(resolved["unit_price"]) * resolved["quantity"]

    restore_variant_stock_for_sale(sale, recorded_by=sale.recorded_by)
    sale.line_items.all().delete()
    for resolved in resolved_items:
        qty = resolved["quantity"]
        price = resolved["unit_price"]
        SaleLineItem.objects.create(
            sale=sale,
            product=resolved["product"],
            variant=resolved["variant"],
            product_name=resolved["product_name"],
            product_model=resolved["product_model"],
            fabric=resolved["fabric"],
            color_name=resolved["color_name"],
            color_hex=resolved["color_hex"],
            quantity=qty,
            unit_price=price,
            line_total=price * qty,
        )
    deduct_variant_stock_for_sale(sale, recorded_by=sale.recorded_by)
    return amount


def _replace_sale_installments(sale, installments):
    """جایگزینی اقساط در انتظار — اقساط پرداخت‌شده دست‌نخورده می‌مانند."""
    if installments is None:
        return
    for inst in sale.installments.filter(is_deleted=False, status="pending"):
        inst.soft_delete()
    if installments:
        from logic.installments import create_installments

        create_installments(sale, installments)


@transaction.atomic
def update_sale(
    sale,
    *,
    amount=None,
    discount=None,
    discount_type=None,
    discount_value=None,
    paid_amount=None,
    line_items=None,
    installments=None,
    payment_status=None,
    order_kind=None,
    delivery_date=None,
    recorded_by=None,
    **meta_fields,
):
    """ویرایش فروش — مبلغ، تخفیف، اقلام، اقساط و فیلدهای متنی."""
    old_paid = sale.paid_amount
    old_wallet = sale.discount if sale.discount_type == "wallet" else Decimal(0)
    old_cashback = sale.discount if sale.discount_type == "cashback" else Decimal(0)
    customer = sale.customer

    if line_items is not None:
        if recorded_by is not None:
            from logic.sale_attendance import assert_user_can_record_sale

            assert_user_can_record_sale(recorded_by)
        amount = _replace_sale_line_items(sale, line_items)

    if order_kind is not None:
        sale.order_kind = normalize_order_kind(order_kind)
    if payment_status is not None:
        sale.payment_status = normalize_payment_status(payment_status)
    if delivery_date is not None:
        sale.delivery_date = delivery_date or None

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
    if old_cashback > 0:
        from logic.cashback import apply_cashback_spend

        apply_cashback_spend(customer, sale, Decimal(0), user=recorded_by)

    sale.discount = resolve_discount_amount(
        sale.amount,
        sale.discount_type,
        sale.discount_value,
        customer=customer,
        exclude_sale_id=sale.pk,
    )
    if sale.discount_type == "wallet" and sale.discount > 0:
        _apply_wallet_discount(customer, sale.discount, sale)
    if sale.discount_type == "cashback" and sale.discount > 0:
        from logic.cashback import apply_cashback_spend

        apply_cashback_spend(customer, sale, sale.discount, user=recorded_by)

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
            value = (meta_fields[field] or "").strip()
            if field == "payment_method":
                value = normalize_payment_method(value)
            setattr(sale, field, value)

    sale.save()

    _replace_sale_installments(sale, installments)

    sale_journal = JournalEntry.objects.filter(
        order_links__order=sale, entry_type_ref_id="sale"
    ).exclude(status_ref_id=JournalEntry.STATUS_VOID).order_by("-id").first()
    if sale_journal:
        if sale_journal.status == JournalEntry.STATUS_POSTED:
            create_journal(
                lines=[
                    {
                        "account": line.account,
                        "debit": line.credit,
                        "credit": line.debit,
                        "description": f"برگشت سند {sale_journal.document_code}",
                    }
                    for line in sale_journal.lines.select_related("account")
                ],
                entry_type="adjustment",
                description=f"برگشت اصلاحی فروش {sale.invoice_number or sale.pk}",
                sale=sale,
                is_approved=True,
            )
            _create_sale_accounting(sale, balance_due(sale), is_approved=True, force=True)
        else:
            sale_journal.delete()
            _create_sale_accounting(sale, balance_due(sale), is_approved=False, force=True)

    paid_delta = sale.paid_amount - old_paid
    if paid_delta > 0:
        _apply_purchase_to_customer(
            sale.customer,
            paid_delta,
            sale.sold_at,
            reason="اصلاح مبلغ پرداخت‌شده فاکتور",
            sale=sale,
            user=recorded_by,
        )
    else:
        recalculate_customer_rfm(
            sale.customer,
            send_level_up_sms=False,
        )
        from logic.cashback import accrue_cashback

        accrue_cashback(sale.customer, sale=sale, user=recorded_by)

    return sale


def sales_summary(queryset):
    total = Decimal(0)
    count = 0
    for sale in queryset:
        total += sale.final_amount
        count += 1
    return {"count": count, "total_amount": int(total)}
