"""ارزیابی موجودی مواد: میانگین موزون، FIFO و سرشکن حمل."""

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from backend.models import InventoryCostLayer, InventoryTransaction, Material
from logic.accounting import create_journal
from logic.accounting_accounts import get_account
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.ledger import OFFICE_LEDGER


def _rial(value):
    return Decimal(value or 0).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _qty(value):
    return Decimal(str(value or 0))


def ensure_opening_layer(material):
    if material.valuation_method != Material.VALUATION_FIFO:
        return
    if material.cost_layers.filter(qty_remaining__gt=0).exists():
        return
    stock = _qty(material.stock)
    if stock <= 0:
        return
    InventoryCostLayer.objects.create(
        material=material,
        unit_cost=_rial(material.unit_cost),
        qty_remaining=stock,
    )


def _refresh_fifo_unit_cost(material):
    layers = list(material.cost_layers.filter(qty_remaining__gt=0))
    total_qty = sum(_qty(layer.qty_remaining) for layer in layers)
    if total_qty <= 0:
        return
    total_value = sum(_qty(layer.qty_remaining) * Decimal(layer.unit_cost or 0) for layer in layers)
    material.unit_cost = _rial(total_value / total_qty)
    material.save(update_fields=["unit_cost", "updated_at"])


def inventory_value(material):
    if material.valuation_method == Material.VALUATION_FIFO:
        ensure_opening_layer(material)
        total = Decimal(0)
        for layer in material.cost_layers.filter(qty_remaining__gt=0):
            total += _qty(layer.qty_remaining) * Decimal(layer.unit_cost or 0)
        return int(_rial(total))
    stock = material.stock
    if stock is None:
        return 0
    return int(_rial(Decimal(stock) * Decimal(material.unit_cost or 0)))


def set_valuation_method(material, method):
    method = (method or Material.VALUATION_WEIGHTED).strip()
    if method not in {Material.VALUATION_WEIGHTED, Material.VALUATION_FIFO}:
        raise ValueError("روش ارزیابی نامعتبر است.")
    if material.valuation_method == method:
        return material
    if method == Material.VALUATION_FIFO:
        material.valuation_method = method
        material.save(update_fields=["valuation_method", "updated_at"])
        ensure_opening_layer(material)
        return material
    layers = list(material.cost_layers.filter(qty_remaining__gt=0))
    total_qty = sum(_qty(layer.qty_remaining) for layer in layers)
    if total_qty > 0:
        total_value = sum(_qty(layer.qty_remaining) * Decimal(layer.unit_cost or 0) for layer in layers)
        material.unit_cost = _rial(total_value / total_qty)
    material.cost_layers.all().delete()
    material.valuation_method = method
    material.save(update_fields=["valuation_method", "unit_cost", "updated_at"])
    return material


def issue_cost(material, quantity):
    """بهای خروج. برای FIFO لایه‌ها مصرف می‌شوند."""
    qty = _qty(quantity)
    if qty <= 0:
        return Decimal(material.unit_cost or 0)
    if material.valuation_method != Material.VALUATION_FIFO:
        return Decimal(material.unit_cost or 0)
    ensure_opening_layer(material)
    remaining = qty
    value = Decimal(0)
    layers = material.cost_layers.select_for_update().filter(qty_remaining__gt=0).order_by("id")
    for layer in layers:
        take = min(_qty(layer.qty_remaining), remaining)
        value += take * Decimal(layer.unit_cost or 0)
        layer.qty_remaining = _qty(layer.qty_remaining) - take
        layer.save(update_fields=["qty_remaining"])
        remaining -= take
        if remaining <= 0:
            break
    if remaining > 0:
        value += remaining * Decimal(material.unit_cost or 0)
    _refresh_fifo_unit_cost(material)
    return _rial(value / qty)


def _post_period_freight(material, freight, user=None):
    amount = int(_rial(freight))
    if amount <= 0:
        return None
    expense = get_account(ACCOUNT_SLUGS.DISTRIBUTION_SALES_EXPENSE, ledger=OFFICE_LEDGER)
    payable = get_account(ACCOUNT_SLUGS.ACCOUNTS_PAYABLE, ledger=OFFICE_LEDGER)
    label = material.name
    return create_journal(
        lines=[
            {"account": expense, "debit": amount, "credit": 0, "description": f"حمل {label}"},
            {"account": payable, "debit": 0, "credit": amount, "description": f"حمل {label}"},
        ],
        entry_type="adjustment",
        description=f"هزینه حمل دوره — {label}",
        is_approved=False,
        ledger=OFFICE_LEDGER,
        user=user,
    )


@transaction.atomic
def receive_stock(
    material,
    quantity,
    unit_cost,
    *,
    freight_amount=0,
    freight_treatment="capitalize",
    previous_unit_cost=None,
    reason="receipt",
    reference="",
    recorded_by=None,
):
    qty = _qty(quantity)
    if qty <= 0:
        raise ValueError("مقدار رسید باید بزرگ‌تر از صفر باشد.")
    cost = _rial(unit_cost)
    freight = _rial(freight_amount)
    if freight < 0 or cost < 0:
        raise ValueError("بهای رسید نامعتبر است.")
    treatment = (freight_treatment or "capitalize").strip()
    if treatment not in {"capitalize", "period_expense"}:
        raise ValueError("نحوه ثبت حمل نامعتبر است.")
    goods = qty * cost
    if treatment == "capitalize":
        inbound_value = goods + freight
    else:
        inbound_value = goods
        if freight > 0:
            _post_period_freight(material, freight, user=recorded_by)
    effective = _rial(inbound_value / qty)
    on_hand = _qty(material.stock)
    prior = Decimal(previous_unit_cost if previous_unit_cost is not None else material.unit_cost or 0)
    if material.valuation_method == Material.VALUATION_FIFO:
        material.unit_cost = effective if on_hand <= 0 else material.unit_cost
        material.save(update_fields=["unit_cost", "updated_at"])
        txn = InventoryTransaction.objects.create(
            material=material,
            quantity=qty,
            unit_cost=effective,
            reason=reason,
            reference=reference or f"material:{material.pk}",
            recorded_by=recorded_by,
        )
        InventoryCostLayer.objects.create(
            material=material,
            source_transaction=txn,
            unit_cost=effective,
            qty_remaining=qty,
        )
        _refresh_fifo_unit_cost(material)
        return txn
    new_qty = on_hand + qty
    if new_qty > 0:
        material.unit_cost = _rial((on_hand * prior + inbound_value) / new_qty)
    else:
        material.unit_cost = effective
    material.save(update_fields=["unit_cost", "updated_at"])
    return InventoryTransaction.objects.create(
        material=material,
        quantity=qty,
        unit_cost=effective,
        reason=reason,
        reference=reference or f"material:{material.pk}",
        recorded_by=recorded_by,
    )
