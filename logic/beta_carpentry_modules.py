"""زیرماژول‌های نجاری بتا — ابزار، چوب، خدمات، باربری، تردد."""

from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from backend.models import (
    BetaCarpentryAttendance,
    BetaCarpentryExternalService,
    BetaCarpentryFreight,
    BetaCarpentryOrder,
    BetaCarpentryTool,
    BetaCarpentryWoodPurchase,
    BetaCarpentryWorkshop,
)
from logic import beta_workshops as base

TOOL_STATUS_LABELS = dict(BetaCarpentryTool.STATUS_CHOICES)


def _workshop_qs(workshop_id=None, workshop_kind=None):
    qs = BetaCarpentryWorkshop.objects.all()
    if workshop_id:
        qs = qs.filter(pk=workshop_id)
    elif workshop_kind:
        qs = qs.filter(kind=workshop_kind)
    return qs


def _order_qs(workshop_id=None, workshop_kind=None):
    qs = BetaCarpentryOrder.objects.all()
    if workshop_id:
        qs = qs.filter(workshop_id=workshop_id)
    elif workshop_kind:
        qs = qs.filter(workshop__kind=workshop_kind)
    return qs


def _scoped(model, workshop_id=None, workshop_kind=None, workshop_field="workshop_id"):
    qs = model.objects.all()
    if workshop_id:
        qs = qs.filter(**{workshop_field: workshop_id})
    elif workshop_kind:
        qs = qs.filter(**{f"{workshop_field.replace('_id', '')}__kind": workshop_kind})
    return qs


def carpentry_dashboard(workshop_id=None, workshop_kind=None):
    orders = _order_qs(workshop_id, workshop_kind)
    tools = _scoped(BetaCarpentryTool, workshop_id, workshop_kind)
    wood = _scoped(BetaCarpentryWoodPurchase, workshop_id, workshop_kind)
    services = _scoped(BetaCarpentryExternalService, workshop_id, workshop_kind)
    freight = _scoped(BetaCarpentryFreight, workshop_id, workshop_kind)
    attendance = _scoped(BetaCarpentryAttendance, workshop_id, workshop_kind)

    satellite_freight = int(
        BetaCarpentryFreight.objects.filter(workshop__kind=BetaCarpentryWorkshop.KIND_SATELLITE).aggregate(
            total=Sum("cost")
        )["total"]
        or 0
    )
    if workshop_kind == BetaCarpentryWorkshop.KIND_SATELLITE or workshop_id:
        satellite_freight = int(freight.aggregate(total=Sum("cost"))["total"] or 0)

    build_count = orders.filter(kind=BetaCarpentryOrder.KIND_BUILD).count()
    repair_count = orders.filter(kind=BetaCarpentryOrder.KIND_REPAIR).count()

    return {
        "summary": {
            "frames_in_progress": orders.filter(status=BetaCarpentryOrder.STATUS_IN_PROGRESS).count(),
            "delivered_to_warehouse": orders.filter(status=BetaCarpentryOrder.STATUS_DELIVERED).count(),
            "satellite_freight_cost": satellite_freight,
            "tools_count": tools.aggregate(total=Sum("quantity"))["total"] or 0,
            "wood_purchase_total": int(wood.aggregate(total=Sum("total_cost"))["total"] or 0),
        },
        "modules": {
            "production": build_count,
            "tools": tools.count(),
            "wood": wood.count(),
            "services": services.count(),
            "freight": freight.count(),
            "repair": repair_count,
            "attendance": attendance.count(),
        },
    }


# --- ابزار ---

def tool_to_dict(item):
    workshop = item.workshop
    return {
        "id": item.id,
        "code": item.code,
        "name": item.name,
        "category": item.category,
        "workshop_id": workshop.id if workshop else None,
        "workshop_name": workshop.name if workshop else "",
        "status": item.status,
        "status_display": TOOL_STATUS_LABELS.get(item.status, item.status),
        "quantity": item.quantity,
        "purchase_date": item.purchase_date.isoformat() if item.purchase_date else None,
        "value": int(item.value or 0),
        "note": item.note,
    }


def filter_tools(qs, params):
    search = base._text(params.get("search"))
    workshop_id = base._optional_int(params.get("workshop_id"))
    if search:
        qs = qs.filter(Q(code__icontains=search) | Q(name__icontains=search) | Q(category__icontains=search))
    if workshop_id:
        qs = qs.filter(workshop_id=workshop_id)
    return qs.select_related("workshop")


def create_tool(data):
    tool = BetaCarpentryTool(
        code=base._text(data.get("code")) or base._next_code(BetaCarpentryTool, "TL"),
        name=base._text(data.get("name")),
    )
    if not tool.name:
        raise ValueError("نام ابزار را وارد کنید.")
    _apply_tool_fields(tool, data, creating=True)
    tool.save()
    return tool


def update_tool(tool, data):
    _apply_tool_fields(tool, data, creating=False)
    tool.save()
    return tool


def _apply_tool_fields(tool, data, *, creating):
    if "name" in data or creating:
        name = base._text(data.get("name"))
        if name:
            tool.name = name
    if "category" in data or creating:
        tool.category = base._text(data.get("category"))
    if "workshop_id" in data or creating:
        wid = base._optional_int(data.get("workshop_id"))
        tool.workshop = BetaCarpentryWorkshop.objects.filter(pk=wid).first() if wid else None
    if "status" in data:
        tool.status = base._choice(
            data.get("status"),
            {k for k, _ in BetaCarpentryTool.STATUS_CHOICES},
            "وضعیت",
            BetaCarpentryTool.STATUS_ACTIVE,
        )
    if "quantity" in data or creating:
        tool.quantity = base._positive_int(data.get("quantity"), default=1)
    if "purchase_date" in data or creating:
        tool.purchase_date = base._date(data.get("purchase_date"))
    if "value" in data or creating:
        tool.value = base._money(data.get("value"), 0)
    if "note" in data or creating:
        tool.note = base._text(data.get("note"))


# --- خرید چوب ---

def wood_purchase_to_dict(item):
    workshop = item.workshop
    return {
        "id": item.id,
        "code": item.code,
        "supplier": item.supplier,
        "material_type": item.material_type,
        "wood_type": item.wood_type,
        "quantity": float(item.quantity or 0),
        "unit": item.unit,
        "unit_cost": int(item.unit_cost or 0),
        "total_cost": int(item.total_cost or 0),
        "purchase_date": item.purchase_date.isoformat() if item.purchase_date else None,
        "workshop_id": workshop.id if workshop else None,
        "workshop_name": workshop.name if workshop else "",
        "invoice_ref": item.invoice_ref,
        "note": item.note,
    }


def filter_wood_purchases(qs, params):
    search = base._text(params.get("search"))
    workshop_id = base._optional_int(params.get("workshop_id"))
    if search:
        qs = qs.filter(
            Q(code__icontains=search)
            | Q(supplier__icontains=search)
            | Q(material_type__icontains=search)
            | Q(wood_type__icontains=search)
        )
    if workshop_id:
        qs = qs.filter(workshop_id=workshop_id)
    return qs.select_related("workshop")


def create_wood_purchase(data):
    item = BetaCarpentryWoodPurchase(code=base._text(data.get("code")) or base._next_code(BetaCarpentryWoodPurchase, "WD"))
    _apply_wood_fields(item, data, creating=True)
    item.save()
    return item


def update_wood_purchase(item, data):
    _apply_wood_fields(item, data, creating=False)
    item.save()
    return item


def _apply_wood_fields(item, data, *, creating):
    if "supplier" in data or creating:
        item.supplier = base._text(data.get("supplier"))
    if "material_type" in data or creating:
        item.material_type = base._text(data.get("material_type"))
    if "wood_type" in data or creating:
        item.wood_type = base._text(data.get("wood_type"))
    if "quantity" in data or creating:
        item.quantity = base._qty(data.get("quantity"), 0)
    if "unit" in data or creating:
        item.unit = base._text(data.get("unit")) or "متر"
    if "unit_cost" in data or creating:
        item.unit_cost = base._money(data.get("unit_cost"), 0)
    if "total_cost" in data or creating:
        item.total_cost = base._money(data.get("total_cost"), 0)
    elif "quantity" in data or "unit_cost" in data or creating:
        item.total_cost = Decimal(item.quantity or 0) * Decimal(item.unit_cost or 0)
    if "purchase_date" in data or creating:
        item.purchase_date = base._date(data.get("purchase_date")) or (timezone.localdate() if creating else item.purchase_date)
    if "workshop_id" in data or creating:
        wid = base._optional_int(data.get("workshop_id"))
        item.workshop = BetaCarpentryWorkshop.objects.filter(pk=wid).first() if wid else None
    if "invoice_ref" in data or creating:
        item.invoice_ref = base._text(data.get("invoice_ref"))
    if "note" in data or creating:
        item.note = base._text(data.get("note"))


# --- خدمات برون‌سازمانی ---

def external_service_to_dict(item):
    workshop = item.workshop
    order = item.carpentry_order
    return {
        "id": item.id,
        "code": item.code,
        "service_type": item.service_type,
        "provider": item.provider,
        "workshop_id": workshop.id if workshop else None,
        "workshop_name": workshop.name if workshop else "",
        "carpentry_order_id": order.id if order else None,
        "carpentry_order_code": order.code if order else "",
        "amount": int(item.amount or 0),
        "service_date": item.service_date.isoformat() if item.service_date else None,
        "description": item.description,
    }


def filter_external_services(qs, params):
    search = base._text(params.get("search"))
    workshop_id = base._optional_int(params.get("workshop_id"))
    if search:
        qs = qs.filter(
            Q(code__icontains=search)
            | Q(service_type__icontains=search)
            | Q(provider__icontains=search)
            | Q(description__icontains=search)
        )
    if workshop_id:
        qs = qs.filter(workshop_id=workshop_id)
    return qs.select_related("workshop", "carpentry_order")


def create_external_service(data):
    item = BetaCarpentryExternalService(
        code=base._text(data.get("code")) or base._next_code(BetaCarpentryExternalService, "SRV"),
    )
    _apply_service_fields(item, data, creating=True)
    item.save()
    return item


def update_external_service(item, data):
    _apply_service_fields(item, data, creating=False)
    item.save()
    return item


def _apply_service_fields(item, data, *, creating):
    if "service_type" in data or creating:
        item.service_type = base._text(data.get("service_type"))
    if "provider" in data or creating:
        item.provider = base._text(data.get("provider"))
    if "workshop_id" in data or creating:
        wid = base._optional_int(data.get("workshop_id"))
        item.workshop = BetaCarpentryWorkshop.objects.filter(pk=wid).first() if wid else None
    if "carpentry_order_id" in data or creating:
        oid = base._optional_int(data.get("carpentry_order_id"))
        item.carpentry_order = BetaCarpentryOrder.objects.filter(pk=oid).first() if oid else None
    if "amount" in data or creating:
        item.amount = base._money(data.get("amount"), 0)
    if "service_date" in data or creating:
        item.service_date = base._date(data.get("service_date")) or (timezone.localdate() if creating else item.service_date)
    if "description" in data or creating:
        item.description = base._text(data.get("description"))


# --- باربری ---

def freight_to_dict(item):
    workshop = item.workshop
    order = item.carpentry_order
    return {
        "id": item.id,
        "code": item.code,
        "carpentry_order_id": order.id if order else None,
        "carpentry_order_code": order.code if order else "",
        "workshop_id": workshop.id if workshop else None,
        "workshop_name": workshop.name if workshop else "",
        "destination": item.destination,
        "driver_name": item.driver_name,
        "cost": int(item.cost or 0),
        "sent_date": item.sent_date.isoformat() if item.sent_date else None,
        "note": item.note,
    }


def filter_freight(qs, params):
    search = base._text(params.get("search"))
    workshop_id = base._optional_int(params.get("workshop_id"))
    if search:
        qs = qs.filter(
            Q(code__icontains=search)
            | Q(destination__icontains=search)
            | Q(driver_name__icontains=search)
        )
    if workshop_id:
        qs = qs.filter(workshop_id=workshop_id)
    return qs.select_related("workshop", "carpentry_order")


def create_freight(data):
    item = BetaCarpentryFreight(code=base._text(data.get("code")) or base._next_code(BetaCarpentryFreight, "FR"))
    _apply_freight_fields(item, data, creating=True)
    item.save()
    return item


def update_freight(item, data):
    _apply_freight_fields(item, data, creating=False)
    item.save()
    return item


def _apply_freight_fields(item, data, *, creating):
    if "destination" in data or creating:
        dest = base._text(data.get("destination"))
        if creating and not dest:
            raise ValueError("مقصد را وارد کنید.")
        if dest:
            item.destination = dest
    if "driver_name" in data or creating:
        item.driver_name = base._text(data.get("driver_name"))
    if "workshop_id" in data or creating:
        wid = base._optional_int(data.get("workshop_id"))
        item.workshop = BetaCarpentryWorkshop.objects.filter(pk=wid).first() if wid else None
    if "carpentry_order_id" in data or creating:
        oid = base._optional_int(data.get("carpentry_order_id"))
        item.carpentry_order = BetaCarpentryOrder.objects.filter(pk=oid).first() if oid else None
    if "cost" in data or creating:
        item.cost = base._money(data.get("cost"), 0)
    if "sent_date" in data or creating:
        item.sent_date = base._date(data.get("sent_date")) or (timezone.localdate() if creating else item.sent_date)
    if "note" in data or creating:
        item.note = base._text(data.get("note"))


# --- تردد ---

def attendance_to_dict(item):
    workshop = item.workshop
    return {
        "id": item.id,
        "workshop_id": workshop.id if workshop else None,
        "workshop_name": workshop.name if workshop else "",
        "person_name": item.person_name,
        "visit_date": item.visit_date.isoformat() if item.visit_date else None,
        "check_in": item.check_in.isoformat() if item.check_in else None,
        "check_out": item.check_out.isoformat() if item.check_out else None,
        "note": item.note,
    }


def filter_attendance(qs, params):
    search = base._text(params.get("search"))
    workshop_id = base._optional_int(params.get("workshop_id"))
    if search:
        qs = qs.filter(Q(person_name__icontains=search) | Q(note__icontains=search))
    if workshop_id:
        qs = qs.filter(workshop_id=workshop_id)
    return qs.select_related("workshop")


def create_attendance(data):
    wid = base._optional_int(data.get("workshop_id"))
    workshop = BetaCarpentryWorkshop.objects.filter(pk=wid, is_active=True).first()
    if not workshop:
        raise ValueError("واحد نجاری را انتخاب کنید.")
    name = base._text(data.get("person_name"))
    if not name:
        raise ValueError("نام پرسنل را وارد کنید.")
    visit_date = base._date(data.get("visit_date")) or timezone.localdate()
    item = BetaCarpentryAttendance(workshop=workshop, person_name=name, visit_date=visit_date)
    _apply_attendance_fields(item, data, creating=True)
    item.save()
    return item


def update_attendance(item, data):
    if "workshop_id" in data:
        wid = base._optional_int(data.get("workshop_id"))
        workshop = BetaCarpentryWorkshop.objects.filter(pk=wid, is_active=True).first()
        if not workshop:
            raise ValueError("واحد نجاری را انتخاب کنید.")
        item.workshop = workshop
    _apply_attendance_fields(item, data, creating=False)
    item.save()
    return item


def _apply_attendance_fields(item, data, *, creating):
    if "person_name" in data:
        name = base._text(data.get("person_name"))
        if name:
            item.person_name = name
    if "visit_date" in data:
        item.visit_date = base._date(data.get("visit_date")) or item.visit_date
    if "check_in" in data or creating:
        item.check_in = _parse_time(data.get("check_in"))
    if "check_out" in data or creating:
        item.check_out = _parse_time(data.get("check_out"))
    if "note" in data or creating:
        item.note = base._text(data.get("note"))


def _parse_time(value):
    if not value:
        return None
    from django.utils.dateparse import parse_time

    parsed = parse_time(str(value))
    if parsed is None:
        raise ValueError("ساعت نامعتبر است.")
    return parsed
