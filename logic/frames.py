"""منطق کلاف — CRUD و سریال‌سازی."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from backend.models import (
    Frame,
    FrameComponentMaterialRule,
    FrameModel,
    FrameServiceComponent,
    FrameServiceTemplate,
    FrameWoodRequirement,
    Material,
    Product,
)
from logic.materials import approved_materials_filter, material_to_dict


DESIGN_STYLE_LABELS = dict(Frame.DESIGN_STYLE_CHOICES)
WOOD_TYPE_LABELS = dict(Frame.WOOD_TYPE_CHOICES)
COMPONENT_TYPE_LABELS = dict(FrameServiceComponent.COMPONENT_TYPE_CHOICES)
RULE_KEY_LABELS = dict(FrameComponentMaterialRule.RULE_KEY_CHOICES)

DEFAULT_SERVICE_COMPONENTS = [
    (FrameServiceComponent.TYPE_THREE_SEATER, 1, 0),
    (FrameServiceComponent.TYPE_ARMCHAIR, 2, 1),
    (FrameServiceComponent.TYPE_SIDE_TABLE, 2, 2),
    (FrameServiceComponent.TYPE_COFFEE_TABLE, 1, 3),
]


def _parse_decimal(value, default=Decimal(1)):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def _resolve_material(material_id):
    if not material_id:
        return None
    return Material.objects.filter(
        pk=material_id,
        is_deleted=False,
        is_active=True,
        **approved_materials_filter(),
    ).first()


def wood_requirement_to_dict(req):
    material = req.material
    return {
        "id": req.id,
        "label": req.label or "",
        "quantity": float(req.quantity or 0),
        "unit": req.unit,
        "material_id": material.id if material else None,
        "material": material_to_dict(material) if material else None,
        "sort_order": req.sort_order,
    }


def material_rule_to_dict(rule):
    material = rule.material
    return {
        "id": rule.id,
        "rule_key": rule.rule_key,
        "rule_key_display": RULE_KEY_LABELS.get(rule.rule_key, rule.rule_key),
        "material_id": material.id if material else None,
        "material": material_to_dict(material) if material else None,
        "quantity": float(rule.quantity or 0),
        "unit": rule.unit,
        "is_default": rule.is_default,
        "sort_order": rule.sort_order,
    }


def service_component_to_dict(component):
    return {
        "id": component.id,
        "component_type": component.component_type,
        "component_type_display": COMPONENT_TYPE_LABELS.get(
            component.component_type, component.component_type
        ),
        "default_quantity": component.default_quantity,
        "sort_order": component.sort_order,
        "material_rules": [
            material_rule_to_dict(rule)
            for rule in component.material_rules.select_related("material").order_by("sort_order", "id")
        ],
    }


def frame_model_to_dict(model):
    return {
        "id": model.id,
        "name": model.name,
        "sort_order": model.sort_order,
        "is_active": model.is_active,
        "wood_requirements": [
            wood_requirement_to_dict(req)
            for req in model.wood_requirements.select_related("material").order_by("sort_order", "id")
        ],
    }


def service_template_to_dict(template):
    return {
        "id": template.id,
        "name": template.name,
        "default_seat_count": template.default_seat_count,
        "components": [
            service_component_to_dict(component)
            for component in template.components.prefetch_related("material_rules__material").order_by(
                "sort_order", "id"
            )
        ],
    }


def frame_to_dict(frame, *, include_nested=True):
    data = {
        "id": frame.id,
        "name": frame.name,
        "design_style": frame.design_style,
        "design_style_display": DESIGN_STYLE_LABELS.get(frame.design_style, frame.design_style),
        "wood_type": frame.wood_type,
        "wood_type_display": WOOD_TYPE_LABELS.get(frame.wood_type, frame.wood_type),
        "product_id": frame.product_id,
        "is_active": frame.is_active,
        "created_at": frame.created_at.isoformat() if frame.created_at else None,
        "updated_at": frame.updated_at.isoformat() if getattr(frame, "updated_at", None) else None,
    }
    if not include_nested:
        return data

    data["models"] = [
        frame_model_to_dict(model)
        for model in frame.models.filter(is_active=True).order_by("sort_order", "id")
    ]
    template = getattr(frame, "service_template", None)
    if template is None:
        try:
            template = frame.service_template
        except FrameServiceTemplate.DoesNotExist:
            template = None
    data["service_template"] = service_template_to_dict(template) if template else None
    return data


def default_frame_config(frame):
    """پیکربندی پیش‌فرض سرویس برای فروش."""
    template = getattr(frame, "service_template", None)
    if template is None:
        try:
            template = frame.service_template
        except FrameServiceTemplate.DoesNotExist:
            template = None
    components = []
    if template:
        for component in template.components.order_by("sort_order", "id"):
            entry = {
                "type": component.component_type,
                "qty": component.default_quantity,
            }
            if component.component_type in {
                FrameServiceComponent.TYPE_THREE_SEATER,
                FrameServiceComponent.TYPE_ARMCHAIR,
            }:
                entry["back_type"] = "fabric"
            else:
                entry["extra_materials"] = []
            components.append(entry)
        seat_count = template.default_seat_count
    else:
        for component_type, qty, _ in DEFAULT_SERVICE_COMPONENTS:
            entry = {"type": component_type, "qty": qty}
            if component_type in {
                FrameServiceComponent.TYPE_THREE_SEATER,
                FrameServiceComponent.TYPE_ARMCHAIR,
            }:
                entry["back_type"] = "fabric"
            else:
                entry["extra_materials"] = []
            components.append(entry)
        seat_count = 8
    return {"seat_count": seat_count, "components": components}


def filter_frames(queryset, *, search="", active_only=True):
    if active_only:
        queryset = queryset.filter(is_active=True)
    if search:
        q = Q(name__icontains=search)
        q |= Q(models__name__icontains=search)
        queryset = queryset.filter(q).distinct()
    return queryset.select_related("product", "service_template").prefetch_related(
        "models__wood_requirements__material",
        "service_template__components__material_rules__material",
    )


def _sync_wood_requirements(frame_model, items):
    keep_ids = []
    for idx, item in enumerate(items or []):
        material = _resolve_material(item.get("material_id"))
        if item.get("material_id") and not material:
            raise ValueError("متریال چوب انتخاب‌شده یافت نشد یا تایید نشده است.")
        req_id = item.get("id")
        if req_id:
            req = FrameWoodRequirement.objects.filter(pk=req_id, frame_model=frame_model).first()
            if not req:
                req = FrameWoodRequirement(frame_model=frame_model)
        else:
            req = FrameWoodRequirement(frame_model=frame_model)
        req.label = (item.get("label") or "").strip()
        req.quantity = _parse_decimal(item.get("quantity"))
        req.unit = item.get("unit") or FrameWoodRequirement.UNIT_METER
        req.material = material
        req.sort_order = idx
        req.save()
        keep_ids.append(req.id)
    frame_model.wood_requirements.exclude(id__in=keep_ids).delete()


def _sync_material_rules(component, items):
    keep_ids = []
    for idx, item in enumerate(items or []):
        material = _resolve_material(item.get("material_id"))
        if item.get("material_id") and not material:
            raise ValueError("متریال قطعه انتخاب‌شده یافت نشد یا تایید نشده است.")
        rule_id = item.get("id")
        if rule_id:
            rule = FrameComponentMaterialRule.objects.filter(pk=rule_id, component=component).first()
            if not rule:
                rule = FrameComponentMaterialRule(component=component)
        else:
            rule = FrameComponentMaterialRule(component=component)
        rule.rule_key = item.get("rule_key") or FrameComponentMaterialRule.RULE_EXTRA
        rule.material = material
        rule.quantity = _parse_decimal(item.get("quantity"))
        rule.unit = item.get("unit") or "متر"
        rule.is_default = bool(item.get("is_default"))
        rule.sort_order = idx
        rule.save()
        keep_ids.append(rule.id)
    component.material_rules.exclude(id__in=keep_ids).delete()


def _sync_service_template(frame, data):
    if data is None:
        return
    template, _ = FrameServiceTemplate.objects.get_or_create(frame=frame)
    template.name = (data.get("name") or "سرویس ۸ نفره").strip()
    template.default_seat_count = int(data.get("default_seat_count") or 8)
    template.save()

    incoming_components = data.get("components") or []
    if not incoming_components:
        if not template.components.exists():
            for component_type, qty, sort_order in DEFAULT_SERVICE_COMPONENTS:
                FrameServiceComponent.objects.create(
                    template=template,
                    component_type=component_type,
                    default_quantity=qty,
                    sort_order=sort_order,
                )
        return

    keep_component_ids = []
    for idx, item in enumerate(incoming_components):
        component_type = item.get("component_type")
        if not component_type:
            continue
        component_id = item.get("id")
        if component_id:
            component = FrameServiceComponent.objects.filter(pk=component_id, template=template).first()
            if not component:
                component = FrameServiceComponent(template=template, component_type=component_type)
        else:
            component, _ = FrameServiceComponent.objects.get_or_create(
                template=template,
                component_type=component_type,
            )
        component.default_quantity = max(1, int(item.get("default_quantity") or 1))
        component.sort_order = idx
        component.save()
        keep_component_ids.append(component.id)
        _sync_material_rules(component, item.get("material_rules") or [])
    template.components.exclude(id__in=keep_component_ids).delete()


def _sync_frame_models(frame, items):
    keep_ids = []
    for idx, item in enumerate(items or []):
        name = (item.get("name") or "").strip()
        if not name:
            continue
        model_id = item.get("id")
        if model_id:
            frame_model = FrameModel.objects.filter(pk=model_id, frame=frame).first()
            if not frame_model:
                frame_model = FrameModel(frame=frame)
        else:
            frame_model = FrameModel(frame=frame)
        frame_model.name = name
        frame_model.sort_order = idx
        frame_model.is_active = item.get("is_active", True) is not False
        frame_model.save()
        keep_ids.append(frame_model.id)
        _sync_wood_requirements(frame_model, item.get("wood_requirements") or [])
    frame.models.exclude(id__in=keep_ids).delete()


def _sync_product_link(frame, product_id):
    Product.objects.filter(frame_id=frame.id).exclude(pk=product_id).update(frame_id=None)
    if product_id:
        product = Product.objects.filter(pk=product_id, is_deleted=False).first()
        if not product:
            raise ValueError("محصول انتخاب‌شده یافت نشد.")
        product.frame = frame
        product.save(update_fields=["frame"])
        frame.product = product
        frame.save(update_fields=["product", "updated_at"])


@transaction.atomic
def create_frame(data):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("نام کلاف الزامی است.")
    frame = Frame.objects.create(
        name=name,
        design_style=data.get("design_style") or Frame.DESIGN_MODERN,
        wood_type=data.get("wood_type") or Frame.WOOD_ASH_GEORGIAN_G1,
        is_active=data.get("is_active", True) is not False,
    )
    _sync_frame_models(frame, data.get("models"))
    _sync_service_template(frame, data.get("service_template") or {})
    if data.get("product_id"):
        _sync_product_link(frame, data.get("product_id"))
    return frame


@transaction.atomic
def update_frame(frame, data):
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("نام کلاف الزامی است.")
        frame.name = name
    if "design_style" in data:
        frame.design_style = data.get("design_style") or Frame.DESIGN_MODERN
    if "wood_type" in data:
        frame.wood_type = data.get("wood_type") or Frame.WOOD_ASH_GEORGIAN_G1
    if "is_active" in data:
        frame.is_active = data.get("is_active", True) is not False
    frame.save()
    if "models" in data:
        _sync_frame_models(frame, data.get("models"))
    if "service_template" in data:
        _sync_service_template(frame, data.get("service_template"))
    if "product_id" in data:
        _sync_product_link(frame, data.get("product_id"))
    return frame


def delete_frame(frame):
    frame.soft_delete()
    Product.objects.filter(frame_id=frame.id).update(frame_id=None)
    return frame
