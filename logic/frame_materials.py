"""محاسبه متریال/چوب مورد نیاز کلاف برای سفارش کارخانه."""

from collections import defaultdict
from decimal import Decimal

from backend.models import (
    FrameComponentMaterialRule,
    FrameServiceComponent,
    FrameWoodRequirement,
    Material,
)
from logic.materials import approved_materials_filter, material_to_dict


def _add_requirement(bucket, material_id, qty, *, source="frame", label=""):
    if not material_id or qty <= 0:
        return
    bucket[material_id]["required_quantity"] += qty
    if source not in bucket[material_id]["sources"]:
        bucket[material_id]["sources"].append(source)
    if label and label not in bucket[material_id]["labels"]:
        bucket[material_id]["labels"].append(label)


def _component_rules_by_type(frame):
    template = getattr(frame, "service_template", None)
    if template is None:
        try:
            template = frame.service_template
        except Exception:
            return {}
    rules_map = {}
    for component in template.components.prefetch_related("material_rules").all():
        rules_map[component.component_type] = list(component.material_rules.all())
    return rules_map


def _rule_for_back(rules, back_type):
    key = (
        FrameComponentMaterialRule.RULE_BACK_WOOD
        if back_type == "wood"
        else FrameComponentMaterialRule.RULE_BACK_FABRIC
    )
    for rule in rules:
        if rule.rule_key == key and rule.material_id:
            return rule
    return None


def compute_frame_line_requirements(line_item):
    """محاسبه نیاز متریال یک ردیف فاکتور با کلاف."""
    if not getattr(line_item, "frame_id", None):
        return []

    line_qty = Decimal(line_item.quantity or 0)
    if line_qty <= 0:
        return []

    bucket = defaultdict(
        lambda: {
            "required_quantity": Decimal(0),
            "sources": [],
            "labels": [],
        }
    )

    frame_model = getattr(line_item, "frame_model", None)
    if frame_model:
        wood_reqs = FrameWoodRequirement.objects.filter(frame_model=frame_model).select_related("material")
        for req in wood_reqs:
            if not req.material_id:
                continue
            qty = Decimal(req.quantity or 0) * line_qty
            label = req.label or "چوب کلاف"
            _add_requirement(bucket, req.material_id, qty, source="frame_wood", label=label)

    frame = line_item.frame
    config = line_item.frame_config or {}
    components = config.get("components") or []
    rules_map = _component_rules_by_type(frame)

    for component_cfg in components:
        component_type = component_cfg.get("type")
        component_qty = Decimal(component_cfg.get("qty") or 0)
        if not component_type or component_qty <= 0:
            continue
        total_component_qty = component_qty * line_qty
        rules = rules_map.get(component_type, [])

        back_type = component_cfg.get("back_type")
        if back_type in {"fabric", "wood"}:
            rule = _rule_for_back(rules, back_type)
            if rule:
                label = COMPONENT_LABELS.get(component_type, component_type)
                _add_requirement(
                    bucket,
                    rule.material_id,
                    Decimal(rule.quantity or 0) * total_component_qty,
                    source="frame_component",
                    label=label,
                )

        for extra in component_cfg.get("extra_materials") or []:
            material_id = extra.get("material_id")
            extra_qty = Decimal(extra.get("qty") or 0) * total_component_qty
            _add_requirement(
                bucket,
                material_id,
                extra_qty,
                source="frame_extra",
                label=COMPONENT_LABELS.get(component_type, component_type),
            )

    results = []
    for material_id, data in bucket.items():
        material = Material.objects.filter(pk=material_id, is_deleted=False).first()
        if not material:
            continue
        req_qty = data["required_quantity"]
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
                "source": "frame",
                "source_labels": data["labels"],
            }
        )
    results.sort(key=lambda item: item["material"]["name"])
    return results


COMPONENT_LABELS = dict(FrameServiceComponent.COMPONENT_TYPE_CHOICES)


def merge_material_requirements(base_items, extra_items):
    """ادغام لیست متریال — مقادیر جمع و منبع frame حفظ می‌شود."""
    merged = {}
    for item in base_items:
        mid = item["material_id"]
        merged[mid] = dict(item)
        merged[mid]["sources"] = [item.get("source") or "product"]

    for item in extra_items:
        mid = item["material_id"]
        if mid in merged:
            merged[mid]["required_quantity"] = float(
                Decimal(str(merged[mid]["required_quantity"])) + Decimal(str(item["required_quantity"]))
            )
            merged[mid]["line_cost"] = int(merged[mid]["line_cost"] or 0) + int(item.get("line_cost") or 0)
            if item.get("source") not in merged[mid]["sources"]:
                merged[mid]["sources"].append(item.get("source"))
            for label in item.get("source_labels") or []:
                labels = merged[mid].setdefault("source_labels", [])
                if label not in labels:
                    labels.append(label)
            if item.get("sufficient") is False:
                merged[mid]["sufficient"] = False
                base_short = Decimal(str(merged[mid].get("shortage") or 0))
                extra_short = Decimal(str(item.get("shortage") or 0))
                merged[mid]["shortage"] = float(max(base_short, extra_short))
        else:
            merged[mid] = dict(item)
            merged[mid]["sources"] = [item.get("source") or "frame"]
    out = list(merged.values())
    for row in out:
        if len(row.get("sources") or []) > 1:
            row["source"] = "mixed"
        elif row.get("sources"):
            row["source"] = row["sources"][0]
    out.sort(key=lambda item: item["material"]["name"])
    return out


def preview_frame_requirements(frame, *, frame_model_id=None, frame_config=None, quantity=1):
    """پیش‌نمایش محاسبه برای API."""
    from types import SimpleNamespace

    frame_model = None
    if frame_model_id:
        frame_model = frame.models.filter(pk=frame_model_id).first()
    line = SimpleNamespace(
        frame=frame,
        frame_id=frame.id,
        frame_model=frame_model,
        frame_model_id=frame_model.id if frame_model else None,
        frame_config=frame_config or {},
        quantity=quantity,
    )
    return compute_frame_line_requirements(line)
