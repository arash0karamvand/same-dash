"""گزارش انبار متریال کارخانه — موجودی، تعهد صف، ظرفیت و گردش."""

from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import F, Max, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from backend.models import (
    InventoryTransaction,
    Material,
    Product,
    ProductMaterial,
    WorkshopRecipe,
    WorkshopRecipeMaterial,
)
from logic.materials import committed_material_demand
from logic.workshop_recipes import KIND_TO_PRODUCT_FIELD, RECIPE_KINDS

REASON_LABELS = {
    "initial_stock": "موجودی اولیه",
    "manual_adjustment": "تعدیل دستی",
    "production_consumption": "مصرف تولید",
    "production_rollback": "برگشت تولید",
}
CONSUMPTION_REASONS = ("production_consumption", "production_rollback")
MOVEMENT_LIMIT = 500
COVERAGE_DAYS = 30
DEFAULT_CONSUMPTION_DAYS = 30
DEFAULT_IDLE_DAYS = 90
CAPACITY_NOTE = (
    "هر ردیف فرض می‌کند فقط همان محصول ساخته شود. "
    "مصرف از دستور محصول و دستور رنگ، پارچه، اسفنج، تسمه و کوسن پیش‌فرض است. "
    "چوب کلاف در این محاسبه نیست."
)


def warehouse_report(params):
    key = (params.get("report") or "summary").strip() or "summary"
    builder = _REPORTS.get(key)
    if builder is None:
        raise ValueError("گزارش نامعتبر است.")
    payload = builder(params)
    payload["report"] = key
    return payload


def _dec(value):
    if value is None or value == "":
        return Decimal(0)
    return Decimal(str(value))


def _num(value):
    number = _dec(value)
    if number == number.to_integral():
        return int(number)
    return float(number)


def _rial(qty, unit_cost):
    return int(_dec(qty) * _dec(unit_cost))


def _text(params, key):
    return (params.get(key) or "").strip()


def _parse_day(value):
    text = (value or "").strip()
    if not text:
        return None
    parsed = parse_date(text)
    if parsed is None:
        raise ValueError("تاریخ نامعتبر است.")
    return parsed


def _day_start(day):
    moment = datetime.combine(day, time.min)
    if timezone.is_naive(moment):
        return timezone.make_aware(moment)
    return moment


def _period(params, *, default_days=None):
    start = _parse_day(params.get("date_from"))
    end = _parse_day(params.get("date_to"))
    if default_days and start is None and end is None:
        end = timezone.localdate()
        start = end - timedelta(days=default_days - 1)
    if start and end and end < start:
        raise ValueError("بازه تاریخ نامعتبر است.")
    return start, end


def _apply_period(qs, start, end):
    if start:
        qs = qs.filter(created_at__gte=_day_start(start))
    if end:
        qs = qs.filter(created_at__lt=_day_start(end + timedelta(days=1)))
    return qs


def _usage_kind(params):
    kind = _text(params, "usage_kind")
    if not kind:
        return ""
    allowed = {code for code, _ in Material.USAGE_KIND_CHOICES}
    if kind not in allowed:
        raise ValueError("نوع مصرف متریال نامعتبر است.")
    return kind


def _material_id(params):
    raw = _text(params, "material_id")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise ValueError("متریال نامعتبر است.")


def _idle_days(params):
    raw = _text(params, "idle_days")
    if not raw:
        return DEFAULT_IDLE_DAYS
    try:
        days = int(raw)
    except ValueError:
        raise ValueError("بازه رکود نامعتبر است.")
    if days < 1 or days > 3650:
        raise ValueError("بازه رکود نامعتبر است.")
    return days


def _label(material):
    if material.color_name:
        return f"{material.name} ({material.color_name})"
    return material.name


def _usage_label(kind):
    return dict(Material.USAGE_KIND_CHOICES).get(kind or Material.USAGE_OTHER, "سایر")


def _materials(params):
    kind = _usage_kind(params)
    search = _text(params, "search")
    qs = Material.objects.filter(approval_status_ref_id=Material.APPROVAL_APPROVED)
    if kind:
        qs = qs.filter(usage_kind=kind)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search) | Q(color_name__icontains=search))
    return qs.order_by("name")


def _stock_map(material_ids):
    if not material_ids:
        return {}
    rows = (
        InventoryTransaction.objects.filter(material_id__in=material_ids)
        .values("material_id")
        .annotate(total=Sum("quantity"))
    )
    return {row["material_id"]: _dec(row["total"]) for row in rows}


def _positions(params):
    materials = list(_materials(params))
    ids = [item.id for item in materials]
    stocks = _stock_map(ids)
    committed = committed_material_demand()
    rows = []
    for material in materials:
        stock = stocks.get(material.id, Decimal(0))
        held = _dec(committed.get(material.id, 0))
        unit_cost = int(material.unit_cost or 0)
        rows.append(
            {
                "material_id": material.id,
                "name": material.name,
                "color_name": material.color_name or "",
                "label": _label(material),
                "sku": material.sku or "",
                "unit": material.unit,
                "usage_kind": material.usage_kind or Material.USAGE_OTHER,
                "usage_kind_display": _usage_label(material.usage_kind),
                "unit_cost": unit_cost,
                "on_hand": _num(stock),
                "committed": _num(held),
                "available": _num(stock - held),
                "inventory_value": _rial(stock, unit_cost),
                "_stock": stock,
                "_committed": held,
            }
        )
    return rows


def _public_position(row):
    data = dict(row)
    data.pop("_stock", None)
    data.pop("_committed", None)
    return data


def _used_material_ids():
    ids = set(
        ProductMaterial.objects.filter(material__is_deleted=False).values_list("material_id", flat=True)
    )
    ids.update(
        WorkshopRecipeMaterial.objects.filter(
            recipe__is_deleted=False,
            material__is_deleted=False,
        ).values_list("material_id", flat=True)
    )
    return ids


def report_summary(params):
    rows = _positions(params)
    start, end = _period(params, default_days=DEFAULT_CONSUMPTION_DAYS)
    ids = [row["material_id"] for row in rows]
    consumption = _consumption_totals(ids, start, end)
    by_kind = defaultdict(lambda: {"item_count": 0, "inventory_value": 0, "shortage_count": 0})
    inventory_value = 0
    zero_count = 0
    shortage_count = 0
    shortage_value = 0
    for row in rows:
        inventory_value += row["inventory_value"]
        bucket = by_kind[row["usage_kind"]]
        bucket["item_count"] += 1
        bucket["inventory_value"] += row["inventory_value"]
        if row["_stock"] <= 0:
            zero_count += 1
        if row["_committed"] > row["_stock"]:
            shortage_count += 1
            bucket["shortage_count"] += 1
            shortage_value += _rial(row["_committed"] - row["_stock"], row["unit_cost"])
    return {
        "item_count": len(rows),
        "inventory_value": inventory_value,
        "zero_count": zero_count,
        "shortage_count": shortage_count,
        "shortage_value": shortage_value,
        "date_from": start.isoformat() if start else None,
        "date_to": end.isoformat() if end else None,
        "consumption_value": consumption["value"],
        "consumption_by_unit": consumption["by_unit"],
        "by_usage_kind": [
            {
                "usage_kind": kind,
                "usage_kind_display": _usage_label(kind),
                "item_count": bucket["item_count"],
                "inventory_value": bucket["inventory_value"],
                "shortage_count": bucket["shortage_count"],
            }
            for kind, bucket in sorted(by_kind.items(), key=lambda item: item[0])
        ],
    }


def report_stock(params):
    return {"rows": [_public_position(row) for row in _positions(params)]}


def report_shortage(params):
    used = _used_material_ids()
    purchase = []
    zero_used = []
    purchase_value = 0
    for row in _positions(params):
        gap = row["_committed"] - row["_stock"]
        if gap > 0:
            value = _rial(gap, row["unit_cost"])
            purchase_value += value
            item = _public_position(row)
            item["suggested_quantity"] = _num(gap)
            item["suggested_value"] = value
            purchase.append(item)
        elif row["_stock"] <= 0 and row["material_id"] in used:
            zero_used.append(_public_position(row))
    purchase.sort(key=lambda item: item["suggested_value"], reverse=True)
    return {
        "purchase_value": purchase_value,
        "purchase": purchase,
        "zero_used": zero_used,
    }


def _piece_factor(piece):
    try:
        qty = int(piece.get("quantity") or 1)
    except (TypeError, ValueError):
        qty = 1
    return Decimal(qty if qty > 0 else 1)


def _material_key(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _add_line(bucket, material_id, qty, via):
    material_id = _material_key(material_id)
    amount = _dec(qty)
    if not material_id or amount <= 0:
        return
    bucket[material_id][via] += amount


def _recipe_lines(recipe, factor, via, bucket):
    if recipe is None or not recipe.is_active:
        return
    for row in recipe.materials.all():
        _add_line(bucket, row.material_id, _dec(row.quantity) * factor, via)


def _linked_recipe(product, field):
    if not getattr(product, f"{field}_id", None):
        return None
    try:
        recipe = getattr(product, field)
    except WorkshopRecipe.DoesNotExist:
        return None
    if recipe is None or not recipe.is_active:
        return None
    return recipe


def _product_lines(product):
    """مصرف یک عدد محصول: دستور مستقیم و دستورهای پیش‌فرض دست‌کار."""
    bucket = defaultdict(lambda: defaultdict(Decimal))
    for link in product.product_materials.all():
        _add_line(bucket, link.material_id, link.quantity, "دستور محصول")
    pieces = list(product.suite_config or [])
    if pieces:
        for piece in pieces:
            if not isinstance(piece, dict):
                continue
            factor = _piece_factor(piece)
            piece_label = piece.get("piece_label") or "قطعه"
            for kind, kind_label in RECIPE_KINDS.items():
                block = piece.get(kind) or {}
                if not isinstance(block, dict):
                    continue
                via = f"{kind_label} {piece_label}"
                for row in block.get("materials") or []:
                    if isinstance(row, dict):
                        _add_line(
                            bucket,
                            row.get("material_id"),
                            _dec(row.get("quantity")) * factor,
                            via,
                        )
        return bucket
    for kind, field in KIND_TO_PRODUCT_FIELD.items():
        _recipe_lines(_linked_recipe(product, field), Decimal(1), RECIPE_KINDS[kind], bucket)
    return bucket


def _product_queryset():
    return Product.objects.filter(is_active=True).prefetch_related(
        "product_materials",
        "paint_recipe__materials",
        "fabric_recipe__materials",
        "foam_recipe__materials",
        "cushion_recipe__materials",
        "webbing_recipe__materials",
    )


def _units(stock, qty):
    if qty <= 0:
        return 0
    if stock <= 0:
        return 0
    return int(stock // qty)


def report_capacity(params):
    kind = _usage_kind(params)
    search = _text(params, "search").casefold()
    products = []
    for product in _product_queryset():
        if search and search not in (product.name or "").casefold() and search not in (product.sku or "").casefold():
            continue
        products.append((product, _product_lines(product)))
    needed = set()
    for _, lines in products:
        needed.update(lines)
    materials = {item.id: item for item in Material.objects.filter(pk__in=needed)} if needed else {}
    stocks = _stock_map(needed)
    committed = committed_material_demand()
    rows = []
    for product, lines in products:
        if kind and not any(
            (materials.get(material_id).usage_kind if materials.get(material_id) else "") == kind
            for material_id in lines
        ):
            continue
        if not lines:
            rows.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "sku": product.sku or "",
                    "has_bom": False,
                    "buildable_on_hand": None,
                    "buildable_after_queue": None,
                    "bottleneck_material_id": None,
                    "bottleneck_name": "",
                    "bottleneck_unit": "",
                }
            )
            continue
        on_hand_units = None
        free_units = None
        bottleneck = None
        for material_id, vias in lines.items():
            qty = sum(vias.values(), Decimal(0))
            material = materials.get(material_id)
            stock = stocks.get(material_id, Decimal(0))
            free = stock - _dec(committed.get(material_id, 0))
            raw_units = _units(stock, qty)
            queue_units = _units(free, qty)
            if on_hand_units is None or raw_units < on_hand_units:
                on_hand_units = raw_units
            if free_units is None or queue_units < free_units:
                free_units = queue_units
            ratio = (free / qty) if qty else Decimal(0)
            if bottleneck is None or queue_units < bottleneck[0] or (
                queue_units == bottleneck[0] and ratio < bottleneck[1]
            ):
                bottleneck = (
                    queue_units,
                    ratio,
                    material_id,
                    _label(material) if material else "متریال",
                    material.unit if material else "",
                )
        rows.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "sku": product.sku or "",
                "has_bom": True,
                "buildable_on_hand": on_hand_units or 0,
                "buildable_after_queue": free_units or 0,
                "bottleneck_material_id": bottleneck[2] if bottleneck else None,
                "bottleneck_name": bottleneck[3] if bottleneck else "",
                "bottleneck_unit": bottleneck[4] if bottleneck else "",
            }
        )
    rows.sort(key=lambda row: (0 if row["has_bom"] else 1, row["buildable_after_queue"] if row["has_bom"] else 0, row["product_name"]))
    return {"note": CAPACITY_NOTE, "rows": rows}


def report_movements(params):
    materials = list(_materials(params))
    ids = [item.id for item in materials]
    selected = _material_id(params)
    if selected is not None:
        ids = [item for item in ids if item == selected]
    options = [{"id": item.id, "label": _label(item)} for item in materials]
    base = InventoryTransaction.objects.filter(material_id__in=ids).select_related("material")
    start, end = _period(params)
    window = _apply_period(base, start, end).order_by("created_at", "id")
    total = window.count()
    truncated = total > MOVEMENT_LIMIT
    kept = list(window.reverse()[:MOVEMENT_LIMIT]) if truncated else list(window)
    if truncated:
        kept.reverse()
    if kept:
        first = kept[0]
        prior = base.filter(Q(created_at__lt=first.created_at) | Q(created_at=first.created_at, id__lt=first.id))
    elif start:
        prior = base.filter(created_at__lt=_day_start(start))
    else:
        prior = base.none()
    balances = defaultdict(Decimal)
    for row in prior.values("material_id").annotate(total=Sum("quantity")):
        balances[row["material_id"]] = _dec(row["total"])
    opening = balances.get(selected, Decimal(0)) if selected is not None else None
    rows = []
    for tx in kept:
        qty = _dec(tx.quantity)
        balances[tx.material_id] += qty
        material = tx.material
        rows.append(
            {
                "id": tx.id,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
                "material_id": tx.material_id,
                "material_name": _label(material) if material else "",
                "unit": material.unit if material else "",
                "reason": tx.reason,
                "reason_label": REASON_LABELS.get(tx.reason, tx.reason),
                "reference": tx.reference or "",
                "in_quantity": _num(qty) if qty > 0 else 0,
                "out_quantity": _num(-qty) if qty < 0 else 0,
                "balance": _num(balances[tx.material_id]),
                "line_value": _rial(abs(qty), tx.unit_cost),
            }
        )
    closing = balances.get(selected, Decimal(0)) if selected is not None else None
    return {
        "date_from": start.isoformat() if start else None,
        "date_to": end.isoformat() if end else None,
        "truncated": truncated,
        "opening_balance": _num(opening) if opening is not None else None,
        "closing_balance": _num(closing) if closing is not None else None,
        "material_options": options,
        "rows": rows,
    }


def _consumption_buckets(material_ids, start, end):
    if not material_ids:
        return {}
    qs = InventoryTransaction.objects.filter(material_id__in=material_ids, reason__in=CONSUMPTION_REASONS)
    qs = _apply_period(qs, start, end)
    buckets = defaultdict(lambda: {"consumed": Decimal(0), "returned": Decimal(0), "value": Decimal(0)})
    rows = qs.values("material_id", "reason").annotate(
        qty=Sum("quantity"),
        value=Sum(F("quantity") * F("unit_cost")),
    )
    for row in rows:
        bucket = buckets[row["material_id"]]
        qty = _dec(row["qty"])
        value = _dec(row["value"])
        if row["reason"] == "production_consumption":
            bucket["consumed"] += -qty
        else:
            bucket["returned"] += qty
        bucket["value"] += -value
    return buckets


def _consumption_totals(material_ids, start, end):
    materials = {item.id: item for item in Material.objects.filter(pk__in=material_ids)} if material_ids else {}
    by_unit = defaultdict(Decimal)
    total_value = Decimal(0)
    rows = []
    for material_id, bucket in _consumption_buckets(material_ids, start, end).items():
        net = bucket["consumed"] - bucket["returned"]
        if net == 0 and bucket["value"] == 0:
            continue
        material = materials.get(material_id)
        unit = material.unit if material else ""
        by_unit[unit] += net
        total_value += bucket["value"]
        rows.append(
            {
                "material_id": material_id,
                "label": _label(material) if material else "",
                "unit": unit,
                "usage_kind": material.usage_kind if material else "",
                "usage_kind_display": _usage_label(material.usage_kind) if material else "",
                "consumed_quantity": _num(bucket["consumed"]),
                "returned_quantity": _num(bucket["returned"]),
                "net_quantity": _num(net),
                "net_value": int(bucket["value"]),
                "_net": net,
            }
        )
    rows.sort(key=lambda item: item["net_value"], reverse=True)
    return {
        "value": int(total_value),
        "by_unit": [
            {"unit": unit or "—", "quantity": _num(qty)}
            for unit, qty in sorted(by_unit.items(), key=lambda item: item[0])
            if qty != 0
        ],
        "rows": rows,
    }


def report_consumption(params):
    start, end = _period(params, default_days=DEFAULT_CONSUMPTION_DAYS)
    ids = [item.id for item in _materials(params)]
    totals = _consumption_totals(ids, start, end)
    rows = []
    for row in totals["rows"]:
        item = dict(row)
        item.pop("_net", None)
        rows.append(item)
    by_kind = defaultdict(lambda: {"net_value": 0, "item_count": 0})
    for row in rows:
        bucket = by_kind[row["usage_kind"] or Material.USAGE_OTHER]
        bucket["net_value"] += row["net_value"]
        bucket["item_count"] += 1
    return {
        "date_from": start.isoformat() if start else None,
        "date_to": end.isoformat() if end else None,
        "consumption_value": totals["value"],
        "by_unit": totals["by_unit"],
        "by_usage_kind": [
            {
                "usage_kind": kind,
                "usage_kind_display": _usage_label(kind),
                "item_count": bucket["item_count"],
                "net_value": bucket["net_value"],
            }
            for kind, bucket in sorted(by_kind.items(), key=lambda item: item[0])
        ],
        "rows": rows,
    }


def report_coverage(params):
    end = timezone.localdate()
    start = end - timedelta(days=COVERAGE_DAYS - 1)
    positions = {row["material_id"]: row for row in _positions(params)}
    buckets = _consumption_buckets(list(positions), start, end)
    window = Decimal(COVERAGE_DAYS)
    rows = []
    for material_id, bucket in buckets.items():
        net = bucket["consumed"] - bucket["returned"]
        if net <= 0:
            continue
        position = positions[material_id]
        stock = position["_stock"]
        daily = net / window
        days = Decimal(0) if stock <= 0 else (stock / daily).quantize(Decimal("0.1"))
        rows.append(
            {
                "material_id": material_id,
                "label": position["label"],
                "unit": position["unit"],
                "usage_kind_display": position["usage_kind_display"],
                "on_hand": position["on_hand"],
                "net_quantity": _num(net),
                "daily_consumption": _num(daily),
                "days_of_cover": float(days),
            }
        )
    rows.sort(key=lambda item: (item["days_of_cover"], item["label"]))
    return {
        "days": COVERAGE_DAYS,
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "rows": rows,
    }


def report_idle(params):
    days = _idle_days(params)
    cutoff = timezone.now() - timedelta(days=days)
    positions = [row for row in _positions(params) if row["_stock"] > 0]
    ids = [row["material_id"] for row in positions]
    recent = set(
        InventoryTransaction.objects.filter(
            material_id__in=ids,
            quantity__lt=0,
            created_at__gte=cutoff,
        ).values_list("material_id", flat=True)
    ) if ids else set()
    last_out = {}
    if ids:
        for row in (
            InventoryTransaction.objects.filter(material_id__in=ids, quantity__lt=0)
            .values("material_id")
            .annotate(last_at=Max("created_at"))
        ):
            last_out[row["material_id"]] = row["last_at"]
    used = _used_material_ids()
    idle = []
    unused = []
    for row in positions:
        item = _public_position(row)
        last = last_out.get(row["material_id"])
        item["last_out_at"] = last.isoformat() if last else None
        if row["material_id"] not in recent:
            idle.append(item)
        if row["material_id"] not in used:
            unused.append(dict(item))
    idle.sort(key=lambda item: item["inventory_value"], reverse=True)
    unused.sort(key=lambda item: item["inventory_value"], reverse=True)
    return {"idle_days": days, "idle": idle, "unused": unused}


def report_abc(params):
    ranked = [row for row in _positions(params) if row["inventory_value"] > 0]
    ranked.sort(key=lambda row: row["inventory_value"], reverse=True)
    total = sum(row["inventory_value"] for row in ranked)
    running = Decimal(0)
    rows = []
    counts = {"A": 0, "B": 0, "C": 0}
    values = {"A": 0, "B": 0, "C": 0}
    for row in ranked:
        value = Decimal(row["inventory_value"])
        before = (running / Decimal(total)) if total else Decimal(0)
        running += value
        if value <= 0:
            klass = "C"
        elif before < Decimal("0.80"):
            klass = "A"
        elif before < Decimal("0.95"):
            klass = "B"
        else:
            klass = "C"
        counts[klass] += 1
        values[klass] += row["inventory_value"]
        share = (value / Decimal(total) * Decimal(100)) if total else Decimal(0)
        cumulative = (running / Decimal(total) * Decimal(100)) if total else Decimal(0)
        item = _public_position(row)
        item["abc_class"] = klass
        item["share_percent"] = float(share.quantize(Decimal("0.1")))
        item["cumulative_percent"] = float(cumulative.quantize(Decimal("0.1")))
        rows.append(item)
    return {
        "inventory_value": int(total),
        "counts": counts,
        "values": values,
        "rows": rows,
    }


def report_where_used(params):
    search = _text(params, "search")
    materials = {item.id: item for item in _materials(params)}
    usages = defaultdict(list)
    for product in _product_queryset():
        for material_id, vias in _product_lines(product).items():
            if material_id not in materials:
                continue
            for via, qty in vias.items():
                usages[material_id].append(
                    {
                        "place": product.name,
                        "via": via,
                        "quantity": _num(qty),
                        "kind": "product",
                    }
                )
    for recipe in WorkshopRecipe.objects.filter(is_active=True).prefetch_related("materials"):
        via = RECIPE_KINDS.get(recipe.kind, recipe.kind)
        for row in recipe.materials.all():
            if row.material_id not in materials:
                continue
            usages[row.material_id].append(
                {
                    "place": recipe.name,
                    "via": via,
                    "quantity": _num(row.quantity),
                    "kind": "recipe",
                }
            )
    rows = []
    for material in materials.values():
        links = usages.get(material.id) or []
        if not links and not search:
            continue
        rows.append(
            {
                "material_id": material.id,
                "label": _label(material),
                "unit": material.unit,
                "usage_kind_display": _usage_label(material.usage_kind),
                "usages": links,
            }
        )
    rows.sort(key=lambda item: item["label"])
    return {"rows": rows}


_REPORTS = {
    "summary": report_summary,
    "stock": report_stock,
    "shortage": report_shortage,
    "capacity": report_capacity,
    "movements": report_movements,
    "consumption": report_consumption,
    "coverage": report_coverage,
    "idle": report_idle,
    "abc": report_abc,
    "where_used": report_where_used,
}
