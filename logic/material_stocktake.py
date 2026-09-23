"""برگه انبارگردانی متریال — مغایرت شمارش با موجودی، بدون تغییر موجودی."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from backend.models import InventoryTransaction, Material, MaterialStocktake, MaterialStocktakeLine
from logic.accounting_accounts import get_account
from logic.accounting_events import issue_event_draft, register_event
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.ledger import LEGAL_LEDGER
from logic.material_reports import _dec, _num, _positions, _rial, report_abc, report_idle

DEAD_STOCK_DAYS = 180
ACCURACY_FLOOR = Decimal("95")
CLASS_A_FLOOR = Decimal("99")
CAUSE_LABELS = dict(MaterialStocktakeLine.CAUSE_CHOICES)
CONDITION_LABELS = dict(MaterialStocktakeLine.CONDITION_CHOICES)
TYPE_LABELS = dict(MaterialStocktake.TYPE_CHOICES)
STATUS_LABELS = {
    "shortage": "کسری",
    "overage": "سرریز",
    "match": "تطابق",
}
COUNT_PLAN = (
    ("A", "ماهانه"),
    ("B", "فصلی"),
    ("C", "سالانه"),
)


def list_stocktakes():
    rows = []
    for sheet in MaterialStocktake.objects.all()[:40]:
        rows.append(_header(sheet))
    return {"results": rows}


@transaction.atomic
def create_stocktake(data, user=None):
    sheet = MaterialStocktake.objects.create(
        count_type=_count_type(data.get("count_type")),
        scope_note=_clip(data.get("scope_note"), 200),
        supervisor_name=_clip(data.get("supervisor_name"), 120),
        counter_names=_clip(data.get("counter_names"), 240),
        observer_name=_clip(data.get("observer_name"), 120),
        started_at=timezone.now(),
        created_by=user if getattr(user, "pk", None) else None,
    )
    return stocktake_sheet(sheet)


@transaction.atomic
def update_stocktake(sheet, data):
    sheet = MaterialStocktake.objects.select_for_update().get(pk=sheet.pk)
    if sheet.status != MaterialStocktake.STATUS_DRAFT:
        raise ValueError("برگه بسته شده و قابل ویرایش نیست.")
    if "count_type" in data:
        sheet.count_type = _count_type(data.get("count_type"))
    if "scope_note" in data:
        sheet.scope_note = _clip(data.get("scope_note"), 200)
    if "supervisor_name" in data:
        sheet.supervisor_name = _clip(data.get("supervisor_name"), 120)
    if "counter_names" in data:
        sheet.counter_names = _clip(data.get("counter_names"), 240)
    if "observer_name" in data:
        sheet.observer_name = _clip(data.get("observer_name"), 120)
    sheet.save()
    if "lines" in data:
        _save_lines(sheet, data.get("lines") or [])
    return stocktake_sheet(sheet)


@transaction.atomic
def close_stocktake(sheet, user=None):
    sheet = MaterialStocktake.objects.select_for_update().get(pk=sheet.pk)
    if sheet.status == MaterialStocktake.STATUS_CLOSED:
        return stocktake_sheet(sheet)

    inventory = get_account(ACCOUNT_SLUGS.RAW_MATERIALS_INVENTORY, ledger=LEGAL_LEDGER)
    shortage_expense = get_account(ACCOUNT_SLUGS.ADMIN_OVERHEAD, ledger=LEGAL_LEDGER)
    overage_income = get_account(ACCOUNT_SLUGS.OTHER_REVENUE, ledger=LEGAL_LEDGER)
    shortage = Decimal(0)
    overage = Decimal(0)
    for line in sheet.lines.select_related("material"):
        if line.condition == MaterialStocktakeLine.CONDITION_CONSIGNMENT:
            continue
        variance = Decimal(line.physical_qty or 0) - Decimal(line.system_qty or 0)
        if variance == 0:
            continue
        value = abs(variance * Decimal(line.unit_cost or 0)).quantize(Decimal("1"))
        if variance < 0:
            shortage += value
        else:
            overage += value
        InventoryTransaction.objects.create(
            material=line.material,
            quantity=variance,
            unit_cost=line.unit_cost,
            reason="stocktake_adjustment",
            reference=f"stocktake:{sheet.pk}:material:{line.material_id}",
            recorded_by=user if getattr(user, "is_authenticated", False) else None,
        )

    lines = []
    if shortage > 0:
        lines.extend([
            {"account": shortage_expense, "debit": shortage, "credit": 0, "description": f"کسری انبارگردانی {sheet.pk}"},
            {"account": inventory, "debit": 0, "credit": shortage, "description": f"کسری انبارگردانی {sheet.pk}"},
        ])
    if overage > 0:
        lines.extend([
            {"account": inventory, "debit": overage, "credit": 0, "description": f"اضافه انبارگردانی {sheet.pk}"},
            {"account": overage_income, "debit": 0, "credit": overage, "description": f"اضافه انبارگردانی {sheet.pk}"},
        ])
    journal = None
    if lines:
        event, _created = register_event(
            source_module="warehouse",
            source_type="MaterialStocktake",
            source=sheet.pk,
            event_type="stocktake_closed",
            payload={"shortage": str(shortage), "overage": str(overage)},
        )
        journal = issue_event_draft(
            event,
            lines=lines,
            entry_type="adjustment",
            description=f"مغایرت انبارگردانی {sheet.pk}",
            user=user,
        )
    sheet.status = MaterialStocktake.STATUS_CLOSED
    sheet.finished_at = timezone.now()
    sheet.journal = journal
    sheet.save(update_fields=["status", "finished_at", "journal", "updated_at"])
    return stocktake_sheet(sheet)


def stocktake_sheet(sheet):
    sheet = MaterialStocktake.objects.prefetch_related("lines__material").get(pk=sheet.pk)
    stored = {line.material_id: line for line in sheet.lines.all()}
    positions = _positions({})
    classes = {row["material_id"]: row["abc_class"] for row in report_abc({})["rows"]}
    rows = []
    seen = set()
    for position in positions:
        material_id = position["material_id"]
        seen.add(material_id)
        rows.append(_row_from_position(position, stored.get(material_id), classes.get(material_id, "")))
    for material_id, line in stored.items():
        if material_id in seen:
            continue
        rows.append(_row_from_line(line, classes.get(material_id, "")))
    metrics = _metrics(rows)
    idle = report_idle({"idle_days": str(DEAD_STOCK_DAYS)})
    damaged = [row for row in rows if row["condition"] in {MaterialStocktakeLine.CONDITION_DAMAGED, MaterialStocktakeLine.CONDITION_EXPIRED} and row["counted"]]
    consignment = [row for row in rows if row["condition"] == MaterialStocktakeLine.CONDITION_CONSIGNMENT and row["counted"]]
    adjustments = [row for row in rows if row["counted"] and row["variance_qty"] not in (0, None)]
    return {
        **_header(sheet),
        "rows": rows,
        "metrics": metrics,
        "damaged": damaged,
        "consignment": consignment,
        "adjustments": adjustments,
        "dead_stock": idle["idle"],
        "dead_stock_days": DEAD_STOCK_DAYS,
        "count_plan": _count_plan(report_abc({})),
        "suggestions": _suggestions(metrics, idle["idle"]),
    }


def _header(sheet):
    return {
        "id": sheet.id,
        "count_type": sheet.count_type,
        "count_type_display": TYPE_LABELS.get(sheet.count_type, sheet.count_type),
        "status": sheet.status,
        "status_display": dict(MaterialStocktake.STATUS_CHOICES).get(sheet.status, sheet.status),
        "scope_note": sheet.scope_note or "",
        "supervisor_name": sheet.supervisor_name or "",
        "counter_names": sheet.counter_names or "",
        "observer_name": sheet.observer_name or "",
        "started_at": sheet.started_at.isoformat() if sheet.started_at else None,
        "finished_at": sheet.finished_at.isoformat() if sheet.finished_at else None,
        "updated_at": sheet.updated_at.isoformat() if sheet.updated_at else None,
        "document_code": sheet.journal.document_code if sheet.journal_id else "",
        "editable": sheet.status == MaterialStocktake.STATUS_DRAFT,
    }


def _row_from_position(position, line, abc_class):
    if line is not None:
        return _measured_row(
            material_id=position["material_id"],
            label=position["label"],
            sku=position["sku"],
            unit=position["unit"],
            usage_kind_display=position["usage_kind_display"],
            system_qty=line.system_qty,
            unit_cost=line.unit_cost,
            physical_qty=line.physical_qty,
            condition=line.condition,
            root_cause=line.root_cause,
            abc_class=abc_class,
        )
    return _measured_row(
        material_id=position["material_id"],
        label=position["label"],
        sku=position["sku"],
        unit=position["unit"],
        usage_kind_display=position["usage_kind_display"],
        system_qty=position["_stock"],
        unit_cost=position["unit_cost"],
        physical_qty=None,
        condition=MaterialStocktakeLine.CONDITION_SOUND,
        root_cause="",
        abc_class=abc_class,
    )


def _row_from_line(line, abc_class):
    material = line.material
    label = material.name
    if material.color_name:
        label = f"{label} ({material.color_name})"
    return _measured_row(
        material_id=material.id,
        label=label,
        sku=material.sku or "",
        unit=material.unit,
        usage_kind_display=dict(Material.USAGE_KIND_CHOICES).get(material.usage_kind, "سایر"),
        system_qty=line.system_qty,
        unit_cost=line.unit_cost,
        physical_qty=line.physical_qty,
        condition=line.condition,
        root_cause=line.root_cause,
        abc_class=abc_class,
    )


def _measured_row(*, material_id, label, sku, unit, usage_kind_display, system_qty, unit_cost, physical_qty, condition, root_cause, abc_class):
    system = _dec(system_qty)
    cost = int(_dec(unit_cost))
    counted = physical_qty is not None
    physical = _dec(physical_qty) if counted else None
    variance = (physical - system) if counted else None
    variance_value = _rial(variance, cost) if counted else None
    if not counted:
        status = ""
    elif variance < 0:
        status = "shortage"
    elif variance > 0:
        status = "overage"
    else:
        status = "match"
    return {
        "material_id": material_id,
        "label": label,
        "sku": sku,
        "unit": unit,
        "usage_kind_display": usage_kind_display,
        "abc_class": abc_class or "",
        "system_qty": _num(system),
        "physical_qty": _num(physical) if counted else None,
        "variance_qty": _num(variance) if counted else None,
        "unit_cost": cost,
        "system_value": _rial(system, cost),
        "variance_value": variance_value,
        "status": status,
        "status_label": STATUS_LABELS.get(status, ""),
        "condition": condition or MaterialStocktakeLine.CONDITION_SOUND,
        "condition_label": CONDITION_LABELS.get(condition, "سالم"),
        "root_cause": root_cause or "",
        "root_cause_label": CAUSE_LABELS.get(root_cause, ""),
        "counted": counted,
    }


def _metrics(rows):
    owned_value = 0
    shortage_value = 0
    overage_value = 0
    counted_owned = 0
    matched_owned = 0
    counted_a = 0
    matched_a = 0
    for row in rows:
        if row["condition"] == MaterialStocktakeLine.CONDITION_CONSIGNMENT:
            continue
        owned_value += row["system_value"]
        if not row["counted"]:
            continue
        counted_owned += 1
        if row["variance_qty"] == 0:
            matched_owned += 1
        if row["abc_class"] == "A":
            counted_a += 1
            if row["variance_qty"] == 0:
                matched_a += 1
        value = row["variance_value"] or 0
        if value < 0:
            shortage_value += -value
        elif value > 0:
            overage_value += value
    accuracy = _percent(matched_owned, counted_owned)
    class_a = _percent(matched_a, counted_a)
    shrinkage = _percent(shortage_value, owned_value) if owned_value and counted_owned else None
    return {
        "accuracy_percent": accuracy,
        "class_a_accuracy_percent": class_a,
        "shrinkage_percent": shrinkage,
        "owned_value": owned_value,
        "shortage_value": shortage_value,
        "overage_value": overage_value,
        "counted_owned": counted_owned,
        "matched_owned": matched_owned,
    }


def _count_plan(abc):
    counts = abc.get("counts") or {}
    return [
        {"abc_class": klass, "frequency": frequency, "item_count": counts.get(klass, 0)}
        for klass, frequency in COUNT_PLAN
    ]


def _suggestions(metrics, dead_stock):
    notes = [
        "کلاس A ماهانه، کلاس B فصلی و کلاس C سالانه شمرده شود.",
        "بستن برگه موجودی انبار را عوض نمی‌کند. کسر و اضافه فقط با مجوز مدیریت ثبت می‌شود.",
    ]
    accuracy = metrics["accuracy_percent"]
    class_a = metrics["class_a_accuracy_percent"]
    if accuracy is not None and Decimal(str(accuracy)) < ACCURACY_FLOOR:
        notes.append("دقت موجودی زیر ۹۵٪ است. شمارش سالانه را با شمارش دوره‌ای عوض کنید.")
    if class_a is not None and Decimal(str(class_a)) < CLASS_A_FLOOR:
        notes.append("دقت کلاس A زیر ۹۹٪ است. کالاهای کلاس A را ماهانه بشمارید.")
    if dead_stock:
        notes.append("اقلام راکد را از نقاط پرترافیک انبار دور کنید تا جای کالاهای پرگردش باز شود.")
    return notes


def _save_lines(sheet, rows):
    if not isinstance(rows, list):
        raise ValueError("ردیف‌های شمارش نامعتبر است.")
    material_ids = []
    parsed = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        material_id = _int(raw.get("material_id"))
        if not material_id:
            continue
        material_ids.append(material_id)
        parsed.append((material_id, raw))
    materials = {
        item.id: item
        for item in Material.objects.filter(pk__in=material_ids, approval_status_ref_id=Material.APPROVAL_APPROVED)
    }
    stocks = _stock_of(material_ids)
    existing = {line.material_id: line for line in sheet.lines.filter(material_id__in=material_ids)}
    for material_id, raw in parsed:
        material = materials.get(material_id)
        if material is None:
            raise ValueError("متریال شمارش یافت نشد یا تایید نشده است.")
        physical = _optional_qty(raw.get("physical_qty"))
        line = existing.get(material_id)
        if physical is None:
            if line is not None:
                line.delete()
            continue
        condition = _condition(raw.get("condition"))
        system_qty = line.system_qty if line is not None else stocks.get(material_id, Decimal(0))
        unit_cost = line.unit_cost if line is not None else material.unit_cost
        cause = _cause(raw.get("root_cause"))
        if physical == _dec(system_qty):
            cause = ""
        if line is None:
            MaterialStocktakeLine.objects.create(
                stocktake=sheet,
                material=material,
                system_qty=system_qty,
                physical_qty=physical,
                unit_cost=unit_cost,
                condition=condition,
                root_cause=cause,
            )
        else:
            line.physical_qty = physical
            line.condition = condition
            line.root_cause = cause
            line.save(update_fields=["physical_qty", "condition", "root_cause"])


def _stock_of(material_ids):
    if not material_ids:
        return {}
    totals = {}
    for row in (
        InventoryTransaction.objects.filter(material_id__in=material_ids)
        .values("material_id")
        .annotate(total=Sum("quantity"))
    ):
        totals[row["material_id"]] = _dec(row["total"])
    return totals


def _percent(part, whole):
    if not whole:
        return None
    return float((Decimal(part) / Decimal(whole) * Decimal(100)).quantize(Decimal("0.1")))


def _count_type(value):
    kind = (value or MaterialStocktake.TYPE_CYCLE).strip()
    if kind not in TYPE_LABELS:
        raise ValueError("نوع شمارش نامعتبر است.")
    return kind


def _condition(value):
    kind = (value or MaterialStocktakeLine.CONDITION_SOUND).strip()
    if kind not in CONDITION_LABELS:
        raise ValueError("وضعیت کیفی نامعتبر است.")
    return kind


def _cause(value):
    kind = (value or "").strip()
    if not kind:
        return ""
    if kind not in CAUSE_LABELS:
        raise ValueError("علت مغایرت نامعتبر است.")
    return kind


def _optional_qty(value):
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except Exception:
        raise ValueError("موجودی فیزیکی نامعتبر است.")
    if number < 0:
        raise ValueError("موجودی فیزیکی نمی‌تواند منفی باشد.")
    return number


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clip(value, limit):
    return str(value or "").strip()[:limit]
