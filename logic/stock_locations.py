"""منطق مکان موجودی — انبار و شعبه."""

from decimal import Decimal

from django.db.models import Sum

from backend.models import Branch, InventoryTransaction, ProductVariant, Warehouse

LOCATION_WAREHOUSE = InventoryTransaction.LOCATION_WAREHOUSE
LOCATION_BRANCH = InventoryTransaction.LOCATION_BRANCH
CENTRAL_WAREHOUSE_CODE = "central"
TRANSFER_REASON = "stock_transfer"


def ensure_central_warehouse():
    warehouse, _ = Warehouse.objects.get_or_create(
        code=CENTRAL_WAREHOUSE_CODE,
        defaults={"label": "انبار مرکزی", "sort_order": 0, "is_active": True},
    )
    return warehouse


def default_warehouse():
    warehouse = Warehouse.objects.filter(is_active=True).order_by("sort_order", "id").first()
    if warehouse:
        return warehouse
    return ensure_central_warehouse()


def list_stock_locations():
    warehouses = list(Warehouse.objects.filter(is_active=True).order_by("sort_order", "label"))
    if not warehouses:
        warehouses = [ensure_central_warehouse()]
    branches = list(Branch.objects.filter(is_active=True).order_by("sort_order", "label"))
    locations = []
    for warehouse in warehouses:
        locations.append(
            {
                "key": f"warehouse:{warehouse.id}",
                "kind": LOCATION_WAREHOUSE,
                "warehouse_id": warehouse.id,
                "branch": "",
                "label": warehouse.label,
            }
        )
    for branch in branches:
        locations.append(
            {
                "key": f"branch:{branch.code}",
                "kind": LOCATION_BRANCH,
                "warehouse_id": None,
                "branch": branch.code,
                "label": branch.label,
            }
        )
    return locations


def parse_location(data, *, required=True):
    if data is None:
        data = {}
    kind = (data.get("kind") or data.get("stock_source_kind") or data.get("location_kind") or "").strip()
    warehouse_id = data.get("warehouse_id") or data.get("stock_source_warehouse_id")
    branch = (data.get("branch") or data.get("stock_source_branch") or "").strip()
    if kind == LOCATION_WAREHOUSE:
        if warehouse_id in (None, ""):
            warehouse_id = default_warehouse().id
        warehouse = Warehouse.objects.filter(pk=warehouse_id, is_active=True).first()
        if warehouse is None:
            raise ValueError("انبار انتخاب‌شده یافت نشد.")
        return {
            "kind": LOCATION_WAREHOUSE,
            "warehouse": warehouse,
            "warehouse_id": warehouse.id,
            "branch": None,
            "label": warehouse.label,
        }
    if kind == LOCATION_BRANCH:
        if not branch:
            raise ValueError("شعبه منبع موجودی را انتخاب کنید.")
        row = Branch.objects.filter(code=branch, is_active=True).first()
        if row is None:
            raise ValueError("شعبه منبع موجودی یافت نشد.")
        return {
            "kind": LOCATION_BRANCH,
            "warehouse": None,
            "warehouse_id": None,
            "branch": row,
            "branch_id": row.code,
            "label": row.label,
        }
    if required:
        raise ValueError("منبع موجودی باید انبار یا شعبه باشد.")
    return None


def location_transaction_kwargs(location):
    if not location:
        return {}
    return {
        "location_kind": location["kind"],
        "warehouse": location.get("warehouse"),
        "branch": location.get("branch") if location["kind"] == LOCATION_BRANCH else None,
    }


def location_from_sale(sale):
    kind = (sale.stock_source_kind or "").strip()
    if kind == LOCATION_WAREHOUSE and sale.stock_source_warehouse_id:
        warehouse = sale.stock_source_warehouse
        if warehouse is None:
            warehouse = Warehouse.objects.filter(pk=sale.stock_source_warehouse_id).first()
        if warehouse is None:
            return None
        return {
            "kind": LOCATION_WAREHOUSE,
            "warehouse": warehouse,
            "warehouse_id": warehouse.id,
            "branch": None,
            "label": warehouse.label,
        }
    if kind == LOCATION_BRANCH and sale.stock_source_branch_id:
        branch = sale.stock_source_branch
        return {
            "kind": LOCATION_BRANCH,
            "warehouse": None,
            "warehouse_id": None,
            "branch": branch,
            "branch_id": branch.code,
            "label": branch.label,
        }
    return None


def apply_sale_stock_source(sale, location):
    if not location:
        sale.stock_source_kind = ""
        sale.stock_source_warehouse = None
        sale.stock_source_branch = None
        return
    sale.stock_source_kind = location["kind"]
    sale.stock_source_warehouse = location.get("warehouse")
    sale.stock_source_branch = location.get("branch") if location["kind"] == LOCATION_BRANCH else None


def movements_for_location(variant, location):
    qs = variant.inventory_movements.all()
    if not location:
        return qs
    qs = qs.filter(location_kind=location["kind"])
    if location["kind"] == LOCATION_WAREHOUSE:
        warehouse_id = location.get("warehouse_id") or getattr(location.get("warehouse"), "id", None)
        return qs.filter(warehouse_id=warehouse_id)
    branch_code = location.get("branch_id")
    if not branch_code:
        branch = location.get("branch")
        branch_code = branch.code if hasattr(branch, "code") else branch
    return qs.filter(branch_id=branch_code)


def stock_for_variant_at(variant, location):
    total = movements_for_location(variant, location).aggregate(total=Sum("quantity"))["total"]
    return total or Decimal("0")


def variant_has_tracked_stock(variant):
    return variant.inventory_movements.exists()


def stock_breakdown_for_variant(variant, locations=None):
    locations = locations or list_stock_locations()
    totals = {}
    for tx in variant.inventory_movements.all():
        if tx.location_kind == LOCATION_WAREHOUSE and tx.warehouse_id:
            key = f"warehouse:{tx.warehouse_id}"
        elif tx.location_kind == LOCATION_BRANCH and tx.branch_id:
            key = f"branch:{tx.branch_id}"
        else:
            continue
        totals[key] = totals.get(key, Decimal("0")) + Decimal(tx.quantity or 0)
    rows = []
    for loc in locations:
        rows.append(
            {
                "key": loc["key"],
                "kind": loc["kind"],
                "warehouse_id": loc.get("warehouse_id"),
                "branch": loc.get("branch") or "",
                "label": loc["label"],
                "quantity": totals.get(loc["key"], Decimal("0")),
            }
        )
    return rows


def format_stock_summary(breakdown):
    parts = []
    for row in breakdown:
        qty = Decimal(row.get("quantity") or 0)
        if qty == 0:
            continue
        if qty == qty.to_integral_value():
            qty_text = str(int(qty))
        else:
            qty_text = format(qty.normalize(), "f")
        parts.append(f"{row['label']} {qty_text}")
    return " · ".join(parts)


def transfer_variant_stock(variant, source, destination, quantity, *, recorded_by=None, product_id=None):
    qty = Decimal(str(quantity or 0))
    if qty <= 0:
        raise ValueError("مقدار انتقال باید مثبت باشد.")
    if source["kind"] == destination["kind"] and source.get("warehouse_id") == destination.get("warehouse_id") and (
        (source.get("branch") or source.get("branch_id")) == (destination.get("branch") or destination.get("branch_id"))
    ):
        raise ValueError("مبدأ و مقصد انتقال یکسان است.")
    locked = ProductVariant.objects.select_for_update().get(pk=variant.pk)
    available = stock_for_variant_at(locked, source)
    if available < qty:
        raise ValueError("موجودی مبدأ برای انتقال کافی نیست.")
    reference = f"transfer:variant:{locked.pk}"
    InventoryTransaction.objects.create(
        variant=locked,
        quantity=-qty,
        reason=TRANSFER_REASON,
        reference=reference,
        recorded_by=recorded_by,
        **location_transaction_kwargs(source),
    )
    InventoryTransaction.objects.create(
        variant=locked,
        quantity=qty,
        reason=TRANSFER_REASON,
        reference=reference,
        recorded_by=recorded_by,
        **location_transaction_kwargs(destination),
    )
    return locked
