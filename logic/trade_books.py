"""چرخه خرید و فروش سیستم دائمی.

بهای تمام‌شده خرید = قیمت پس از تخفیف تجاری + حمل + بیمه + سایر مخارج.
مالیات بر ارزش افزوده جزو بهای کالا نیست.
تخفیف نقدی به روش ناخالص، هنگام پرداخت زودهنگام از موجودی (یا بهای فروش‌رفته) کم می‌شود.
"""

from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
from django.db import transaction

from backend.models import InventoryCostLayer, InventoryTransaction, Material, TradeDocument
from logic.accounting_accounts import get_account, get_posting_account
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.giant_books.money import money_int, rial
from logic.inventory_costing import issue_cost, receive_stock
from logic.ledger import OFFICE_LEDGER
from logic.vat_engine import parse_rate, vat_on

DEFAULT_VAT_RATE = Decimal("10")


def _int(value):
    return money_int(rial(value))


def _portion(amount, qty, remaining):
    """سهم مقداری از مبلغ سند؛ برگشت کامل، مانده را دقیق برمی‌گرداند."""
    left = Decimal(remaining or 0)
    if left <= 0:
        raise ValueError("مانده این سند صفر است.")
    if Decimal(qty) == left:
        return _int(amount)
    return _int(Decimal(amount or 0) * Decimal(qty) / left)


def _qty(value, label):
    try:
        qty = Decimal(str(value if value not in (None, "") else 0))
    except Exception as exc:
        raise ValueError(f"{label} نامعتبر است.") from exc
    if qty <= 0:
        raise ValueError(f"{label} باید بزرگ‌تر از صفر باشد.")
    return qty


def _settlement(value):
    kind = (value or TradeDocument.SETTLEMENT_CREDIT).strip()
    if kind not in {TradeDocument.SETTLEMENT_CASH, TradeDocument.SETTLEMENT_CREDIT}:
        raise ValueError("نحوه تسویه باید نقد یا نسیه باشد.")
    return kind


def purchase_amounts(*, quantity, unit_price, trade_discount=0, freight=0, insurance=0, other_cost=0, vat_rate=DEFAULT_VAT_RATE):
    qty = _qty(quantity, "تعداد")
    price = _int(unit_price)
    if price < 0:
        raise ValueError("نرخ خرید نامعتبر است.")
    gross = _int(Decimal(qty) * price)
    discount = _int(trade_discount)
    if discount > gross:
        raise ValueError("تخفیف تجاری از مبلغ کالا بیشتر است.")
    goods_net = gross - discount
    charges = _int(freight) + _int(insurance) + _int(other_cost)
    if _int(freight) < 0 or _int(insurance) < 0 or _int(other_cost) < 0:
        raise ValueError("مخارج خرید نمی‌تواند منفی باشد.")
    rate = parse_rate(vat_rate)
    vat = vat_on(goods_net, rate)
    inventory = goods_net + charges
    return {
        "quantity": qty,
        "unit_price": price,
        "trade_discount": discount,
        "freight": _int(freight),
        "insurance": _int(insurance),
        "other_cost": _int(other_cost),
        "goods_net": goods_net,
        "charges": charges,
        "inventory_amount": inventory,
        "vat_rate": rate,
        "vat_amount": vat,
        "payable": inventory + vat,
        "unit_cost": _int(Decimal(inventory) / qty) if qty else 0,
    }


def _accounts():
    return {
        "inventory": get_account(ACCOUNT_SLUGS.RAW_MATERIALS_INVENTORY),
        "vat_in": get_account(ACCOUNT_SLUGS.VAT_RECEIVABLE),
        "vat_out": get_account(ACCOUNT_SLUGS.VAT_PAYABLE),
        "payable": get_posting_account(
            ACCOUNT_SLUGS.ACCOUNTS_PAYABLE,
            leaf_slug="trade-payables-general",
        ),
        "receivable": get_account(ACCOUNT_SLUGS.RECEIVABLES),
        "cash": get_account(ACCOUNT_SLUGS.CASH_DOCUMENTS),
        "sales": get_account(ACCOUNT_SLUGS.PRODUCT_SALES),
        "allowances": get_account(ACCOUNT_SLUGS.SALES_ALLOWANCES),
        "cogs": get_account(ACCOUNT_SLUGS.COGS),
    }


def _lines(pairs):
    rows = []
    for account, debit, credit, text in pairs:
        if debit == 0 and credit == 0:
            continue
        rows.append({"account": account, "debit": debit, "credit": credit, "description": text})
    return rows


def _post(lines, *, entry_type, description, user):
    from logic.document_issuance import DocumentIssuanceService

    service = DocumentIssuanceService()
    submit = service.receive_sales_request if entry_type in {"sale", "refund"} else service.receive_warehouse_request
    return submit(
        lines=lines,
        entry_type=entry_type,
        description=description,
        finalize=False,
        ledger=OFFICE_LEDGER,
        user=user,
    )


def _require_sources(invoice_number, warehouse_receipt, *, need_receipt):
    invoice = (invoice_number or "").strip()
    receipt = (warehouse_receipt or "").strip()
    if not invoice:
        raise ValueError("شماره فاکتور، سند مثبته است و باید وارد شود.")
    if need_receipt and not receipt:
        raise ValueError("شماره رسید انبار برای ثبت خرید لازم است.")
    return invoice, receipt


def _reorder_warning(material):
    point = Decimal(material.reorder_point or 0)
    stock = Decimal(material.stock or 0)
    if point > 0 and stock <= point:
        return f"موجودی {material.name} به نقطه سفارش رسیده است."
    return ""


def document_to_dict(doc):
    return {
        "id": doc.id,
        "kind": doc.kind,
        "kind_label": doc.get_kind_display(),
        "settlement": doc.settlement,
        "material_id": doc.material_id,
        "material_name": doc.material.name,
        "quantity": str(doc.quantity),
        "remaining_qty": str(doc.remaining_qty),
        "goods_net": int(doc.goods_net or 0),
        "charges": int(doc.charges or 0),
        "inventory_amount": int(doc.inventory_amount or 0),
        "vat_rate": str(doc.vat_rate),
        "vat_amount": int(doc.vat_amount or 0),
        "cogs_amount": int(doc.cogs_amount or 0),
        "cash_discount": int(doc.cash_discount or 0),
        "invoice_number": doc.invoice_number,
        "warehouse_receipt": doc.warehouse_receipt,
        "description": doc.description,
        "document_code": doc.journal.document_code if doc.journal_id else "",
        "created_at": doc.created_at.isoformat(),
    }


def list_trade_documents():
    docs = TradeDocument.objects.select_related("material", "journal").order_by("-id")[:80]
    return [document_to_dict(doc) for doc in docs]


@transaction.atomic
def post_purchase(data, *, user=None):
    material = Material.objects.select_for_update().get(pk=data.get("material_id"))
    amounts = purchase_amounts(
        quantity=data.get("quantity"),
        unit_price=data.get("unit_price"),
        trade_discount=data.get("trade_discount") or 0,
        freight=data.get("freight") or 0,
        insurance=data.get("insurance") or 0,
        other_cost=data.get("other_cost") or 0,
        vat_rate=data.get("vat_rate", DEFAULT_VAT_RATE),
    )
    if amounts["inventory_amount"] <= 0:
        raise ValueError("بهای تمام‌شده خرید باید بزرگ‌تر از صفر باشد.")
    unit = _int(Decimal(amounts["inventory_amount"]) / amounts["quantity"])
    stored = _int(Decimal(unit) * amounts["quantity"])
    amounts["unit_cost"] = unit
    amounts["inventory_amount"] = stored
    amounts["payable"] = stored + amounts["vat_amount"]
    invoice, receipt = _require_sources(
        data.get("invoice_number"), data.get("warehouse_receipt"), need_receipt=True,
    )
    settlement = _settlement(data.get("settlement"))
    accounts = _accounts()
    credit = accounts["cash"] if settlement == TradeDocument.SETTLEMENT_CASH else accounts["payable"]
    label = material.name
    journal = _post(
        _lines([
            (accounts["inventory"], amounts["inventory_amount"], 0, f"خرید {label}"),
            (accounts["vat_in"], amounts["vat_amount"], 0, f"مالیات خرید {label}"),
            (credit, 0, amounts["payable"], f"فاکتور {invoice}"),
        ]),
        entry_type="adjustment",
        description=f"خرید کالا — {label} — فاکتور {invoice}",
        user=user,
    )
    unit_cost = amounts["unit_cost"]
    move = receive_stock(
        material,
        amounts["quantity"],
        unit_cost,
        freight_amount=0,
        previous_unit_cost=material.unit_cost,
        reason="purchase",
        reference=f"invoice:{invoice}",
        recorded_by=user,
    )
    doc = TradeDocument.objects.create(
        material=material,
        kind=TradeDocument.KIND_PURCHASE,
        settlement=settlement,
        quantity=amounts["quantity"],
        remaining_qty=amounts["quantity"],
        unit_price=amounts["unit_price"],
        trade_discount=amounts["trade_discount"],
        freight=amounts["freight"],
        insurance=amounts["insurance"],
        other_cost=amounts["other_cost"],
        goods_net=amounts["goods_net"],
        charges=amounts["charges"],
        inventory_amount=amounts["inventory_amount"],
        vat_rate=amounts["vat_rate"],
        vat_amount=amounts["vat_amount"],
        invoice_number=invoice,
        warehouse_receipt=receipt,
        description=(data.get("description") or "").strip(),
        journal=journal,
        inventory_move=move,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    payload = document_to_dict(doc)
    payload["amounts"] = {key: (str(value) if isinstance(value, Decimal) else value) for key, value in amounts.items()}
    payload["warning"] = _reorder_warning(material)
    return payload


def _locked_source(document_id, kind):
    try:
        return TradeDocument.objects.select_for_update().select_related("material", "inventory_move").get(
            pk=document_id, kind=kind,
        )
    except TradeDocument.DoesNotExist as exc:
        raise LookupError("سند مبنا پیدا نشد.") from exc


@transaction.atomic
def post_purchase_return(data, *, user=None):
    source = _locked_source(data.get("document_id"), TradeDocument.KIND_PURCHASE)
    qty = _qty(data.get("quantity"), "تعداد برگشت")
    if qty > source.remaining_qty:
        raise ValueError("تعداد برگشت از مانده این فاکتور بیشتر است.")
    material = Material.objects.select_for_update().get(pk=source.material_id)
    if Decimal(material.stock or 0) < qty:
        raise ValueError("موجودی انبار برای برگشت این تعداد کافی نیست.")
    invoice, receipt = _require_sources(
        data.get("invoice_number") or f"R-{source.invoice_number}",
        data.get("warehouse_receipt"),
        need_receipt=True,
    )
    inventory_credit, move = _remove_purchase_qty(source, material, qty, invoice, user)
    vat_credit = _portion(source.vat_amount, qty, source.remaining_qty)
    accounts = _accounts()
    debit = accounts["cash"] if source.settlement == TradeDocument.SETTLEMENT_CASH else accounts["payable"]
    journal = _post(
        _lines([
            (debit, inventory_credit + vat_credit, 0, f"برگشت خرید {material.name}"),
            (accounts["inventory"], 0, inventory_credit, f"برگشت موجودی {material.name}"),
            (accounts["vat_in"], 0, vat_credit, f"برگشت مالیات {material.name}"),
        ]),
        entry_type="refund",
        description=f"برگشت از خرید — {material.name} — {invoice}",
        user=user,
    )
    source.remaining_qty = Decimal(source.remaining_qty) - qty
    source.inventory_amount = _int(source.inventory_amount) - inventory_credit
    source.vat_amount = _int(source.vat_amount) - vat_credit
    source.save(update_fields=["remaining_qty", "inventory_amount", "vat_amount"])
    doc = TradeDocument.objects.create(
        material=material,
        kind=TradeDocument.KIND_PURCHASE_RETURN,
        settlement=source.settlement,
        quantity=qty,
        remaining_qty=0,
        inventory_amount=inventory_credit,
        vat_rate=source.vat_rate,
        vat_amount=vat_credit,
        invoice_number=invoice,
        warehouse_receipt=receipt,
        description=(data.get("description") or "").strip(),
        journal=journal,
        inventory_move=move,
        source=source,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    return document_to_dict(doc)


def _remove_purchase_qty(source, material, qty, invoice, user):
    if material.valuation_method == Material.VALUATION_FIFO and source.inventory_move_id:
        layer = InventoryCostLayer.objects.select_for_update().filter(
            source_transaction_id=source.inventory_move_id, qty_remaining__gt=0,
        ).first()
        if layer is None or Decimal(layer.qty_remaining) < qty:
            raise ValueError("از این رسید به اندازه برگشت در کارت حساب باقی نمانده است.")
        unit = Decimal(layer.unit_cost or 0)
        layer.qty_remaining = Decimal(layer.qty_remaining) - qty
        layer.save(update_fields=["qty_remaining"])
        from logic.inventory_costing import _refresh_fifo_unit_cost
        _refresh_fifo_unit_cost(material)
        total = _int(unit * qty)
    else:
        unit = issue_cost(material, qty)
        total = _int(unit * qty)
    move = InventoryTransaction.objects.create(
        material=material,
        quantity=-qty,
        unit_cost=_int(unit),
        reason="purchase_return",
        reference=f"return:{invoice}",
        recorded_by=user if getattr(user, "is_authenticated", False) else None,
    )
    return total, move


@transaction.atomic
def post_sale(data, *, user=None):
    material = Material.objects.select_for_update().get(pk=data.get("material_id"))
    qty = _qty(data.get("quantity"), "تعداد")
    if Decimal(material.stock or 0) < qty:
        raise ValueError("موجودی کالا برای این فروش کافی نیست.")
    price = _int(data.get("unit_price"))
    if price < 0:
        raise ValueError("نرخ فروش نامعتبر است.")
    gross = _int(Decimal(qty) * price)
    discount = _int(data.get("trade_discount") or 0)
    if discount > gross:
        raise ValueError("تخفیف تجاری از مبلغ فروش بیشتر است.")
    goods_net = gross - discount
    rate = parse_rate(data.get("vat_rate", DEFAULT_VAT_RATE))
    vat = _int(Decimal(goods_net) * rate / Decimal(100))
    invoice, _receipt = _require_sources(data.get("invoice_number"), "", need_receipt=False)
    settlement = _settlement(data.get("settlement"))
    unit = issue_cost(material, qty)
    cogs = _int(Decimal(unit) * qty)
    move = InventoryTransaction.objects.create(
        material=material,
        quantity=-qty,
        unit_cost=_int(unit),
        reason="sale",
        reference=f"sale:{invoice}",
        recorded_by=user if getattr(user, "is_authenticated", False) else None,
    )
    accounts = _accounts()
    debit = accounts["cash"] if settlement == TradeDocument.SETTLEMENT_CASH else accounts["receivable"]
    journal = _post(
        _lines([
            (debit, goods_net + vat, 0, f"فروش {material.name}"),
            (accounts["sales"], 0, goods_net, f"فروش {material.name}"),
            (accounts["vat_out"], 0, vat, f"مالیات فروش {material.name}"),
            (accounts["cogs"], cogs, 0, f"بهای فروش {material.name}"),
            (accounts["inventory"], 0, cogs, f"خروج موجودی {material.name}"),
        ]),
        entry_type="sale",
        description=f"فروش کالا — {material.name} — فاکتور {invoice}",
        user=user,
    )
    doc = TradeDocument.objects.create(
        material=material,
        kind=TradeDocument.KIND_SALE,
        settlement=settlement,
        quantity=qty,
        remaining_qty=qty,
        unit_price=price,
        trade_discount=discount,
        goods_net=goods_net,
        inventory_amount=cogs,
        vat_rate=rate,
        vat_amount=vat,
        cogs_amount=cogs,
        invoice_number=invoice,
        description=(data.get("description") or "").strip(),
        journal=journal,
        inventory_move=move,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    payload = document_to_dict(doc)
    payload["warning"] = _reorder_warning(material)
    return payload


@transaction.atomic
def post_sale_return(data, *, user=None):
    source = _locked_source(data.get("document_id"), TradeDocument.KIND_SALE)
    qty = _qty(data.get("quantity"), "تعداد برگشت")
    if qty > source.remaining_qty:
        raise ValueError("تعداد برگشت از مانده این فروش بیشتر است.")
    material = Material.objects.select_for_update().get(pk=source.material_id)
    invoice, _receipt = _require_sources(
        data.get("invoice_number") or f"SR-{source.invoice_number}", "", need_receipt=False,
    )
    goods = _portion(source.goods_net, qty, source.remaining_qty)
    vat = _portion(source.vat_amount, qty, source.remaining_qty)
    cogs = _portion(source.cogs_amount, qty, source.remaining_qty)
    unit = _int(Decimal(cogs) / qty) if qty else 0
    move = receive_stock(
        material,
        qty,
        unit or material.unit_cost or 0,
        previous_unit_cost=material.unit_cost,
        reason="sale_return",
        reference=f"sale-return:{invoice}",
        recorded_by=user,
    )
    accounts = _accounts()
    credit = accounts["cash"] if source.settlement == TradeDocument.SETTLEMENT_CASH else accounts["receivable"]
    journal = _post(
        _lines([
            (accounts["allowances"], goods, 0, f"برگشت فروش {material.name}"),
            (accounts["vat_out"], vat, 0, f"برگشت مالیات فروش {material.name}"),
            (credit, 0, goods + vat, f"برگشت {invoice}"),
            (accounts["inventory"], cogs, 0, f"برگشت کالا {material.name}"),
            (accounts["cogs"], 0, cogs, f"برگشت بهای فروش {material.name}"),
        ]),
        entry_type="refund",
        description=f"برگشت از فروش — {material.name} — {invoice}",
        user=user,
    )
    source.remaining_qty = Decimal(source.remaining_qty) - qty
    source.goods_net = _int(source.goods_net) - goods
    source.vat_amount = _int(source.vat_amount) - vat
    source.cogs_amount = _int(source.cogs_amount) - cogs
    source.save(update_fields=["remaining_qty", "goods_net", "vat_amount", "cogs_amount"])
    doc = TradeDocument.objects.create(
        material=material,
        kind=TradeDocument.KIND_SALE_RETURN,
        settlement=source.settlement,
        quantity=qty,
        remaining_qty=0,
        goods_net=goods,
        inventory_amount=cogs,
        vat_rate=source.vat_rate,
        vat_amount=vat,
        cogs_amount=cogs,
        invoice_number=invoice,
        journal=journal,
        inventory_move=move,
        source=source,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    return document_to_dict(doc)


@transaction.atomic
def take_purchase_discount(data, *, user=None):
    source = _locked_source(data.get("document_id"), TradeDocument.KIND_PURCHASE)
    if source.settlement != TradeDocument.SETTLEMENT_CREDIT:
        raise ValueError("تخفیف نقدی فقط برای خرید نسیه است.")
    discount = _int(data.get("amount"))
    if discount <= 0:
        raise ValueError("مبلغ تخفیف نقدی باید بزرگ‌تر از صفر باشد.")
    goods_left = _int(source.goods_net) - _int(source.cash_discount)
    if discount > goods_left:
        raise ValueError("تخفیف نقدی از مانده بهای کالا بیشتر است.")
    material = Material.objects.select_for_update().get(pk=source.material_id)
    vat_cut = _int(Decimal(discount) * Decimal(source.vat_rate) / Decimal(100))
    inventory_credit, cogs_credit = _apply_discount_to_stock(source, material, discount)
    accounts = _accounts()
    journal = _post(
        _lines([
            (accounts["payable"], discount + vat_cut, 0, f"تخفیف نقدی {material.name}"),
            (accounts["inventory"], 0, inventory_credit, f"کاهش بهای موجودی {material.name}"),
            (accounts["cogs"], 0, cogs_credit, f"کاهش بهای فروش‌رفته {material.name}"),
            (accounts["vat_in"], 0, vat_cut, f"کاهش مالیات خرید {material.name}"),
        ]),
        entry_type="adjustment",
        description=f"تخفیف نقدی خرید — {material.name} — فاکتور {source.invoice_number}",
        user=user,
    )
    source.cash_discount = _int(source.cash_discount) + discount
    source.inventory_amount = _int(source.inventory_amount) - inventory_credit
    source.vat_amount = _int(source.vat_amount) - vat_cut
    source.save(update_fields=["cash_discount", "inventory_amount", "vat_amount"])
    doc = TradeDocument.objects.create(
        material=material,
        kind=TradeDocument.KIND_PURCHASE_DISCOUNT,
        settlement=source.settlement,
        quantity=0,
        remaining_qty=0,
        cash_discount=discount,
        inventory_amount=inventory_credit,
        cogs_amount=cogs_credit,
        vat_amount=vat_cut,
        vat_rate=source.vat_rate,
        invoice_number=source.invoice_number,
        journal=journal,
        source=source,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    return document_to_dict(doc)


@transaction.atomic
def take_sale_discount(data, *, user=None):
    source = _locked_source(data.get("document_id"), TradeDocument.KIND_SALE)
    if source.settlement != TradeDocument.SETTLEMENT_CREDIT:
        raise ValueError("تخفیف نقدی فقط برای فروش نسیه است.")
    discount = _int(data.get("amount"))
    if discount <= 0:
        raise ValueError("مبلغ تخفیف نقدی باید بزرگ‌تر از صفر باشد.")
    remaining = _int(source.goods_net) - _int(source.cash_discount)
    if discount > remaining:
        raise ValueError("تخفیف از مانده فروش بیشتر است.")
    vat_cut = _int(Decimal(discount) * Decimal(source.vat_rate) / Decimal(100))
    accounts = _accounts()
    journal = _post(
        _lines([
            (accounts["allowances"], discount, 0, f"تخفیف نقدی فروش {source.material.name}"),
            (accounts["vat_out"], vat_cut, 0, f"کاهش مالیات فروش {source.material.name}"),
            (accounts["receivable"], 0, discount + vat_cut, f"کاهش دریافتنی فاکتور {source.invoice_number}"),
        ]),
        entry_type="adjustment",
        description=f"تخفیف نقدی فروش — {source.material.name} — فاکتور {source.invoice_number}",
        user=user,
    )
    source.cash_discount = _int(source.cash_discount) + discount
    source.vat_amount = max(0, _int(source.vat_amount) - vat_cut)
    source.save(update_fields=["cash_discount", "vat_amount"])
    doc = TradeDocument.objects.create(
        material=source.material,
        kind=TradeDocument.KIND_SALE_DISCOUNT,
        settlement=source.settlement,
        quantity=0,
        remaining_qty=0,
        cash_discount=discount,
        vat_amount=vat_cut,
        vat_rate=source.vat_rate,
        invoice_number=source.invoice_number,
        journal=journal,
        source=source,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    return document_to_dict(doc)


def take_cash_discount(data, *, user=None):
    try:
        source = TradeDocument.objects.get(pk=int(data.get("document_id") or 0))
    except (TradeDocument.DoesNotExist, TypeError, ValueError) as exc:
        raise ValueError("سند مبنا یافت نشد.") from exc
    if source.kind == TradeDocument.KIND_PURCHASE:
        return take_purchase_discount(data, user=user)
    if source.kind == TradeDocument.KIND_SALE:
        return take_sale_discount(data, user=user)
    raise ValueError("تخفیف نقدی برای این نوع سند مجاز نیست.")


def _apply_discount_to_stock(source, material, discount):
    if material.valuation_method == Material.VALUATION_FIFO and source.inventory_move_id:
        layer = InventoryCostLayer.objects.select_for_update().filter(
            source_transaction_id=source.inventory_move_id,
        ).first()
        remaining_value = 0
        if layer is not None and Decimal(layer.qty_remaining) > 0:
            remaining_value = _int(Decimal(layer.qty_remaining) * Decimal(layer.unit_cost or 0))
        inventory_credit = min(discount, remaining_value)
        if layer is not None and inventory_credit and Decimal(layer.qty_remaining) > 0:
            new_value = remaining_value - inventory_credit
            layer.unit_cost = _int(Decimal(new_value) / Decimal(layer.qty_remaining))
            layer.save(update_fields=["unit_cost"])
            from logic.inventory_costing import _refresh_fifo_unit_cost
            _refresh_fifo_unit_cost(material)
        return inventory_credit, discount - inventory_credit
    on_hand = Decimal(material.stock or 0)
    on_hand_value = _int(on_hand * Decimal(material.unit_cost or 0)) if on_hand > 0 else 0
    inventory_credit = min(discount, on_hand_value)
    if on_hand > 0 and inventory_credit:
        material.unit_cost = _int((Decimal(on_hand_value) - inventory_credit) / on_hand)
        material.save(update_fields=["unit_cost", "updated_at"])
    return inventory_credit, discount - inventory_credit


def kardex(material_id):
    material = Material.objects.get(pk=material_id)
    moves = material.inventory_movements.order_by("created_at", "id")
    rows = []
    for move in moves:
        qty = Decimal(move.quantity)
        value = _int(abs(qty) * Decimal(move.unit_cost or 0))
        rows.append({
            "date": move.created_at.isoformat(),
            "reference": move.reference,
            "reason": move.reason,
            "in_qty": qty if qty > 0 else Decimal(0),
            "out_qty": -qty if qty < 0 else Decimal(0),
            "unit_cost": int(move.unit_cost or 0),
            "in_value": value if qty > 0 else 0,
            "out_value": value if qty < 0 else 0,
        })
    frame = pd.DataFrame(rows, columns=[
        "date", "reference", "reason", "in_qty", "out_qty", "unit_cost", "in_value", "out_value",
    ])
    if frame.empty:
        lines = []
    else:
        frame["balance_qty"] = (frame["in_qty"] - frame["out_qty"]).cumsum()
        frame["balance_value"] = (frame["in_value"] - frame["out_value"]).cumsum()
        lines = []
        for row in frame.itertuples(index=False):
            lines.append({
                "date": row.date,
                "reference": row.reference,
                "reason": row.reason,
                "in_qty": str(row.in_qty),
                "out_qty": str(row.out_qty),
                "unit_cost": int(row.unit_cost),
                "in_value": int(row.in_value),
                "out_value": int(row.out_value),
                "balance_qty": str(row.balance_qty),
                "balance_value": int(row.balance_value),
            })
    discounts = TradeDocument.objects.filter(
        material=material, kind=TradeDocument.KIND_PURCHASE_DISCOUNT,
    )
    discount_total = sum(int(item.inventory_amount or 0) for item in discounts)
    ending = lines[-1]["balance_value"] - discount_total if lines else 0
    return {
        "material_id": material.id,
        "material_name": material.name,
        "valuation_method": material.valuation_method,
        "reorder_point": str(material.reorder_point or 0),
        "stock": str(material.stock or 0),
        "warning": _reorder_warning(material),
        "lines": lines,
        "discount_adjustments": discount_total,
        "balance_value": ending,
    }
