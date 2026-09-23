"""ثبت حسابداری متریال — موجودی و مصرف در تولید."""

from decimal import Decimal

from logic.accounting import create_journal
from logic.ledger import LEGAL_LEDGER, OFFICE_LEDGER
from logic.posting import build_journal_lines


def _material_label(material):
    name = material.name
    if material.color_name:
        name = f"{name} ({material.color_name})"
    return name


def material_inventory_value(material):
    stock = material.stock
    if stock is None:
        return 0
    return int(Decimal(stock) * Decimal(material.unit_cost or 0))


def post_material_inventory_receipt(material):
    """ثبت ورود موجودی متریال پس از تایید اداری — بدهکار مواد اولیه / بستانکار پرداختنی (دفتر اداری)."""
    if getattr(material, "inventory_accounted_at", None):
        return
    value = material_inventory_value(material)
    if value <= 0:
        return

    label = _material_label(material)
    stock = material.stock
    unit_cost = int(material.unit_cost or 0)
    detail = f"{label} — {stock} {material.unit} × {unit_cost:,}"

    lines = build_journal_lines(
        "material_receipt",
        amounts={"value": value},
        description=f"ورود موجودی متریال — {detail}",
        ledger=OFFICE_LEDGER,
    )
    create_journal(
        lines=lines,
        entry_type="adjustment",
        description=f"ثبت موجودی {label}",
        ledger=OFFICE_LEDGER,
        is_approved=False,
    )

    from django.utils import timezone

    material.inventory_accounted_at = timezone.now()
    material.save(update_fields=["inventory_accounted_at", "updated_at"])


def post_factory_material_consumption(factory_order, requirements):
    """انتقال بهای متریال مصرف‌شده — بدهکار WIP / بستانکار مواد اولیه (دفتر کارخانه)."""
    invoice = factory_order.invoice_number or factory_order.pk

    for item in requirements:
        cost = int(item.get("line_cost") or 0)
        if cost <= 0:
            continue
        mat = item.get("material") or {}
        name = mat.get("name") or "متریال"
        qty = item.get("required_quantity")
        unit = item.get("unit") or ""
        unit_cost = mat.get("unit_cost") or 0
        detail = f"{name} — {qty} {unit} × {unit_cost:,}"

        lines = build_journal_lines(
            "material_consumption",
            amounts={"cost": cost},
            description=f"مصرف متریال (WIP) — سفارش {invoice} — {detail}",
            ledger=LEGAL_LEDGER,
        )
        create_journal(
            lines=lines,
            entry_type="adjustment",
            description=f"مصرف متریال سفارش {invoice}",
            factory_order=factory_order,
            is_approved=False,
            ledger=LEGAL_LEDGER,
        )


def reverse_factory_material_consumption(factory_order, requirements):
    """برگشت سند مصرف — برای بازگشت سفارش از آماده باربری به ساخت (دفتر کارخانه)."""
    invoice = factory_order.invoice_number or factory_order.pk

    for item in requirements:
        cost = int(item.get("line_cost") or 0)
        if cost <= 0:
            continue
        mat = item.get("material") or {}
        name = mat.get("name") or "متریال"
        detail = f"{name} — {item.get('required_quantity')} {item.get('unit') or ''}"

        lines = build_journal_lines(
            "material_consumption_reverse",
            amounts={"cost": cost},
            description=f"برگشت موجودی مواد اولیه — سفارش {invoice} — {detail}",
            ledger=LEGAL_LEDGER,
        )
        create_journal(
            lines=lines,
            entry_type="adjustment",
            description=f"برگشت مصرف سفارش {invoice}",
            factory_order=factory_order,
            is_approved=False,
            ledger=LEGAL_LEDGER,
        )

