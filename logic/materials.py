"""منطق متریال و ارتباط محصول–متریال."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from backend.models import InventoryTransaction, Material, Product, ProductMaterial

MATERIAL_APPROVAL_LABELS = {
    Material.APPROVAL_PENDING: "در انتظار تایید اداری",
    Material.APPROVAL_APPROVED: "تایید شده",
    Material.APPROVAL_REJECTED: "رد شده",
}


def approved_materials_filter(prefix=""):
    field = f"{prefix}approval_status" if prefix else "approval_status"
    return {field: Material.APPROVAL_APPROVED}


def material_to_dict(m):
    submitted_by = getattr(m, "submitted_by", None)
    approved_by = getattr(m, "approved_by", None)
    stock = m.stock
    unit_cost = int(m.unit_cost or 0)
    inventory_value = int(Decimal(stock) * Decimal(unit_cost)) if stock is not None else None
    return {
        "id": m.id,
        "name": m.name,
        "color_name": m.color_name or "",
        "color_hex": m.color_hex,
        "sku": m.sku or "",
        "unit": m.unit,
        "unit_cost": unit_cost,
        "stock": float(stock) if stock is not None else None,
        "inventory_value": inventory_value,
        "description": m.description or "",
        "is_active": m.is_active,
        "approval_status": getattr(m, "approval_status", Material.APPROVAL_APPROVED),
        "approval_status_display": MATERIAL_APPROVAL_LABELS.get(
            getattr(m, "approval_status", Material.APPROVAL_APPROVED),
            getattr(m, "approval_status", Material.APPROVAL_APPROVED),
        ),
        "submitted_by": submitted_by.username if submitted_by else None,
        "approved_by": approved_by.username if approved_by else None,
        "approved_at": m.approved_at.isoformat() if getattr(m, "approved_at", None) else None,
        "rejection_reason": getattr(m, "rejection_reason", "") or "",
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if getattr(m, "updated_at", None) else None,
    }


def product_material_to_dict(pm):
    material = pm.material
    qty = Decimal(pm.quantity or 0)
    unit_cost = Decimal(material.unit_cost or 0)
    line_cost = qty * unit_cost
    return {
        "id": f"{pm.product_id}:{pm.material_id}",
        "material_id": material.id,
        "material": material_to_dict(material),
        "quantity": float(qty),
        "line_cost": int(line_cost),
        "sort_order": pm.sort_order,
    }


def compute_product_material_cost(product):
    total = Decimal(0)
    for pm in product.product_materials.select_related("material").filter(
        material__is_deleted=False,
        material__approval_status_ref_id=Material.APPROVAL_APPROVED,
    ):
        qty = Decimal(pm.quantity or 0)
        unit_cost = Decimal(pm.material.unit_cost or 0)
        total += qty * unit_cost
    return total


def filter_materials(queryset, *, search="", active_only=True, approved_only=False, approval_status=None):
    if active_only:
        queryset = queryset.filter(is_active=True, is_deleted=False)
    if approved_only:
        queryset = queryset.filter(**approved_materials_filter())
    if approval_status:
        queryset = queryset.filter(approval_status=approval_status)
    if search:
        q = Q(name__icontains=search) | Q(sku__icontains=search) | Q(color_name__icontains=search)
        queryset = queryset.filter(q)
    return queryset.order_by("name")


@transaction.atomic
def create_material(data, *, user=None, auto_approve=False):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("نام متریال الزامی است.")
    try:
        unit_cost = Decimal(str(data.get("unit_cost") or 0))
    except (InvalidOperation, TypeError):
        raise ValueError("قیمت متریال نامعتبر است.")
    stock = _parse_stock(data.get("stock"))
    if auto_approve:
        from django.utils import timezone

        approval_status = Material.APPROVAL_APPROVED
        is_active = bool(data.get("is_active", True))
        approved_at = timezone.now()
        approved_by = user
    else:
        approval_status = Material.APPROVAL_PENDING
        is_active = False
        approved_at = None
        approved_by = None
    material = Material.objects.create(
        name=name,
        color_name=(data.get("color_name") or "").strip(),
        color_hex=(data.get("color_hex") or "#cccccc").strip()[:7],
        sku=(data.get("sku") or "").strip(),
        unit=(data.get("unit") or "متر").strip() or "متر",
        unit_cost=unit_cost,
        description=(data.get("description") or "").strip(),
        is_active=is_active,
        approval_status=approval_status,
        submitted_by=user,
        approved_at=approved_at,
        approved_by=approved_by,
    )
    if stock not in (None, 0):
        InventoryTransaction.objects.create(
            material=material,
            quantity=stock,
            unit_cost=unit_cost,
            reason="initial_stock",
            reference=f"material:{material.pk}",
            recorded_by=user,
        )
    if auto_approve:
        from logic.material_accounting import post_material_inventory_receipt

        post_material_inventory_receipt(material)
    return material


@transaction.atomic
def update_material(material, data):
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("نام متریال الزامی است.")
        material.name = name
    if "color_name" in data:
        material.color_name = (data.get("color_name") or "").strip()
    if "color_hex" in data:
        material.color_hex = (data.get("color_hex") or "#cccccc").strip()[:7]
    if "sku" in data:
        material.sku = (data.get("sku") or "").strip()
    if "unit" in data:
        material.unit = (data.get("unit") or "متر").strip() or "متر"
    if "unit_cost" in data:
        try:
            material.unit_cost = Decimal(str(data.get("unit_cost") or 0))
        except (InvalidOperation, TypeError):
            raise ValueError("قیمت متریال نامعتبر است.")
    if "stock" in data:
        _apply_stock_update(material, _parse_stock(data.get("stock")))
    if "description" in data:
        material.description = (data.get("description") or "").strip()
    if "is_active" in data:
        material.is_active = bool(data.get("is_active"))
    material.save()
    return material


@transaction.atomic
def approve_material(material, user):
    if material.approval_status == Material.APPROVAL_APPROVED:
        return material
    from django.utils import timezone

    material.approval_status = Material.APPROVAL_APPROVED
    material.is_active = True
    material.approved_at = timezone.now()
    material.approved_by = user
    material.rejection_reason = ""
    material.save(
        update_fields=[
            "approval_status",
            "is_active",
            "approved_at",
            "approved_by_id",
            "rejection_reason",
            "updated_at",
        ]
    )
    from logic.material_accounting import post_material_inventory_receipt

    post_material_inventory_receipt(material)
    return material


@transaction.atomic
def reject_material(material, user, reason=""):
    material.approval_status = Material.APPROVAL_REJECTED
    material.is_active = False
    material.rejection_reason = (reason or "").strip()
    material.save(update_fields=["approval_status", "is_active", "rejection_reason", "updated_at"])
    return material


def _parse_stock(raw):
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError):
        raise ValueError("موجودی نامعتبر است.")


def _apply_stock_update(material, new_stock):
    """Represent an absolute-stock edit as an append-only adjustment."""
    if new_stock is None:
        return
    current = Decimal(material.stock or 0)
    if Decimal(new_stock) < current:
        raise ValueError("کاهش موجودی فقط با پایان ساخت سفارش در کارخانه امکان‌پذیر است.")
    delta = Decimal(new_stock) - current
    if delta:
        InventoryTransaction.objects.create(
            material=material,
            quantity=delta,
            unit_cost=material.unit_cost,
            reason="manual_adjustment",
            reference=f"material:{material.pk}",
        )


def _parse_product_materials(raw_items):
    if not raw_items:
        return []
    parsed = []
    for idx, item in enumerate(raw_items):
        material_id = item.get("material_id")
        if not material_id:
            continue
        try:
            quantity = Decimal(str(item.get("quantity") or 1))
        except (InvalidOperation, TypeError):
            raise ValueError("مقدار مصرف متریال نامعتبر است.")
        if quantity <= 0:
            raise ValueError("مقدار مصرف متریال باید بزرگ‌تر از صفر باشد.")
        parsed.append(
            {
                "material_id": int(material_id),
                "quantity": quantity,
                "sort_order": int(item.get("sort_order") if item.get("sort_order") is not None else idx),
            }
        )
    return parsed


@transaction.atomic
def sync_product_materials(product, raw_items):
    items = _parse_product_materials(raw_items)
    keep_material_ids = []
    for item in items:
        material = Material.objects.filter(
            pk=item["material_id"],
            is_deleted=False,
            **approved_materials_filter(),
        ).first()
        if not material:
            raise ValueError("متریال انتخاب‌شده یافت نشد یا هنوز تایید اداری نشده است.")
        pm, _ = ProductMaterial.objects.get_or_create(product=product, material=material)
        pm.quantity = item["quantity"]
        pm.sort_order = item["sort_order"]
        pm.save()
        keep_material_ids.append(material.pk)
    product.product_materials.exclude(material_id__in=keep_material_ids).delete()
    return product


def compute_factory_order_material_requirements(factory_order):
    """محاسبه متریال مورد نیاز سفارش — تجمیع از ردیف‌های محصول."""
    from collections import defaultdict

    from backend.models import ProductMaterial

    required = defaultdict(lambda: Decimal(0))
    line_items = factory_order.line_items.select_related("product").all()
    for line in line_items:
        if not line.product_id:
            continue
        product_qty = Decimal(line.quantity or 0)
        if product_qty <= 0:
            continue
        product_materials = ProductMaterial.objects.filter(
            product_id=line.product_id,
            material__is_deleted=False,
            material__is_active=True,
            material__approval_status_ref_id=Material.APPROVAL_APPROVED,
        ).select_related("material")
        for pm in product_materials:
            required[pm.material_id] += product_qty * Decimal(pm.quantity or 0)

    results = []
    for material_id, req_qty in required.items():
        material = Material.objects.filter(pk=material_id, is_deleted=False).first()
        if not material:
            continue
        stock = material.stock
        stock_val = Decimal(stock) if stock is not None else None
        sufficient = True
        shortage = None
        if stock_val is not None:
            shortage = max(Decimal(0), req_qty - stock_val)
            sufficient = stock_val >= req_qty
        results.append(
            {
                "material_id": material.id,
                "material": material_to_dict(material),
                "required_quantity": float(req_qty),
                "unit_cost": int(material.unit_cost or 0),
                "line_cost": int(req_qty * Decimal(material.unit_cost or 0)),
                "available_stock": float(stock_val) if stock_val is not None else None,
                "shortage": float(shortage) if shortage is not None else None,
                "sufficient": sufficient,
                "unit": material.unit,
            }
        )
    results.sort(key=lambda item: item["material"]["name"])
    return results


def factory_order_materials_summary(factory_order):
    requirements = compute_factory_order_material_requirements(factory_order)
    tracked = [item for item in requirements if item["available_stock"] is not None]
    material_cost_total = sum(int(item.get("line_cost") or 0) for item in requirements)
    return {
        "material_requirements": requirements,
        "material_cost_total": material_cost_total,
        "materials_deducted": bool(getattr(factory_order, "materials_deducted_at", None)),
        "materials_deducted_at": (
            factory_order.materials_deducted_at.isoformat()
            if getattr(factory_order, "materials_deducted_at", None)
            else None
        ),
        "materials_all_sufficient": all(item["sufficient"] for item in tracked) if tracked else True,
        "has_material_shortage": any(not item["sufficient"] for item in tracked),
    }


def _format_material_shortages(requirements):
    parts = []
    for item in requirements:
        if item["available_stock"] is None or item["sufficient"]:
            continue
        name = item["material"]["name"]
        if item["material"].get("color_name"):
            name = f"{name} ({item['material']['color_name']})"
        parts.append(
            f"«{name}»: نیاز {item['required_quantity']} {item['unit']}، موجود {item['available_stock']}"
        )
    return parts


@transaction.atomic
def deduct_materials_for_factory_order(factory_order):
    from backend.models import Material, Sale

    factory_order = Sale.objects.select_for_update().get(pk=factory_order.pk)
    if getattr(factory_order, "materials_deducted_at", None):
        return factory_order

    requirements = compute_factory_order_material_requirements(factory_order)
    tracked = [item for item in requirements if item["available_stock"] is not None]
    material_ids = sorted({item["material_id"] for item in tracked})
    locked = {}
    if material_ids:
        locked = {
            material.pk: material
            for material in Material.objects.select_for_update().filter(pk__in=material_ids).order_by("pk")
        }
    for item in tracked:
        material = locked[item["material_id"]]
        stock = Decimal(material.stock or 0)
        req_qty = Decimal(str(item["required_quantity"]))
        shortage = max(Decimal(0), req_qty - stock)
        item["available_stock"] = float(stock)
        item["shortage"] = float(shortage)
        item["sufficient"] = stock >= req_qty

    shortages = _format_material_shortages(requirements)
    if shortages:
        raise ValueError("موجودی متریال کافی نیست — " + "؛ ".join(shortages))

    for item in tracked:
        material = locked[item["material_id"]]
        InventoryTransaction.objects.create(
            material=material,
            quantity=-Decimal(str(item["required_quantity"])),
            unit_cost=material.unit_cost,
            reason="production_consumption",
            reference=f"sale:{factory_order.pk}",
        )

    from logic.material_accounting import post_factory_material_consumption

    post_factory_material_consumption(factory_order, requirements)

    from django.utils import timezone

    factory_order.materials_deducted_at = timezone.now()
    factory_order.save(update_fields=["materials_deducted_at"])
    return factory_order


@transaction.atomic
def restore_materials_for_factory_order(factory_order):
    from backend.models import Material, Sale

    factory_order = Sale.objects.select_for_update().get(pk=factory_order.pk)
    if not getattr(factory_order, "materials_deducted_at", None):
        return factory_order

    requirements = compute_factory_order_material_requirements(factory_order)
    tracked = [item for item in requirements if item["available_stock"] is not None]
    material_ids = sorted({item["material_id"] for item in tracked})
    locked = {}
    if material_ids:
        locked = {
            material.pk: material
            for material in Material.objects.select_for_update().filter(pk__in=material_ids).order_by("pk")
        }
    for item in tracked:
        material = locked[item["material_id"]]
        InventoryTransaction.objects.create(
            material=material,
            quantity=Decimal(str(item["required_quantity"])),
            unit_cost=material.unit_cost,
            reason="production_rollback",
            reference=f"sale:{factory_order.pk}",
        )

    from logic.material_accounting import reverse_factory_material_consumption

    reverse_factory_material_consumption(factory_order, requirements)

    factory_order.materials_deducted_at = None
    factory_order.save(update_fields=["materials_deducted_at"])
    return factory_order
