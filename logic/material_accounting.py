"""ثبت حسابداری متریال — موجودی و مصرف در تولید."""

from decimal import Decimal

from logic.accounting import create_accounting_entry, generate_document_code, next_document_number


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
    """ثبت ورود موجودی متریال پس از تایید اداری — بدهکار مواد اولیه / بستانکار پرداختنی."""
    if getattr(material, "inventory_accounted_at", None):
        return
    value = material_inventory_value(material)
    if value <= 0:
        return

    doc = generate_document_code()
    doc_num = next_document_number()
    label = _material_label(material)
    stock = material.stock
    unit_cost = int(material.unit_cost or 0)
    detail = f"{label} — {stock} {material.unit} × {unit_cost:,}"

    create_accounting_entry(
        entry_type="adjustment",
        account_slug="raw_materials_inventory",
        debit=value,
        amount=value,
        description=f"ورود موجودی متریال — {detail}",
        document_code=doc,
        document_number=doc_num,
    )
    create_accounting_entry(
        entry_type="adjustment",
        account_slug="accounts_payable",
        credit=value,
        amount=value,
        description=f"بابت خرید/ثبت متریال — {detail}",
        document_code=doc,
        document_number=doc_num,
    )

    from django.utils import timezone

    material.inventory_accounted_at = timezone.now()
    material.save(update_fields=["inventory_accounted_at", "updated_at"])


def post_factory_material_consumption(factory_order, requirements):
    """انتقال بهای متریال مصرف‌شده — بدهکار WIP / بستانکار مواد اولیه."""
    sale = getattr(factory_order, "source_sale", None)
    invoice = factory_order.invoice_number or factory_order.pk

    for item in requirements:
        cost = int(item.get("line_cost") or 0)
        if cost <= 0:
            continue
        doc = generate_document_code()
        doc_num = next_document_number()
        mat = item.get("material") or {}
        name = mat.get("name") or "متریال"
        qty = item.get("required_quantity")
        unit = item.get("unit") or ""
        unit_cost = mat.get("unit_cost") or 0
        detail = f"{name} — {qty} {unit} × {unit_cost:,}"

        create_accounting_entry(
            entry_type="adjustment",
            account_slug="wip_inventory",
            debit=cost,
            amount=cost,
            description=f"مصرف متریال (WIP) — سفارش {invoice} — {detail}",
            sale=sale,
            document_code=doc,
            document_number=doc_num,
            is_approved=True,
        )
        create_accounting_entry(
            entry_type="adjustment",
            account_slug="raw_materials_inventory",
            credit=cost,
            amount=cost,
            description=f"کسر موجودی مواد اولیه — سفارش {invoice} — {detail}",
            sale=sale,
            document_code=doc,
            document_number=doc_num,
            is_approved=True,
        )


def reverse_factory_material_consumption(factory_order, requirements):
    """برگشت سند مصرف — برای بازگشت سفارش از آماده باربری به ساخت."""
    sale = getattr(factory_order, "source_sale", None)
    invoice = factory_order.invoice_number or factory_order.pk

    for item in requirements:
        cost = int(item.get("line_cost") or 0)
        if cost <= 0:
            continue
        doc = generate_document_code()
        doc_num = next_document_number()
        mat = item.get("material") or {}
        name = mat.get("name") or "متریال"
        detail = f"{name} — {item.get('required_quantity')} {item.get('unit') or ''}"

        create_accounting_entry(
            entry_type="adjustment",
            account_slug="raw_materials_inventory",
            debit=cost,
            amount=cost,
            description=f"برگشت موجودی مواد اولیه — سفارش {invoice} — {detail}",
            sale=sale,
            document_code=doc,
            document_number=doc_num,
            is_approved=True,
        )
        create_accounting_entry(
            entry_type="adjustment",
            account_slug="wip_inventory",
            credit=cost,
            amount=cost,
            description=f"برگشت مصرف WIP — سفارش {invoice} — {detail}",
            sale=sale,
            document_code=doc,
            document_number=doc_num,
            is_approved=True,
        )
