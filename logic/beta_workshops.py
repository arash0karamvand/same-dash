"""منطق واحدهای کارگاهی بتا — CRUD، سریال‌سازی و آمار."""

from decimal import Decimal, InvalidOperation
from datetime import date

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from backend.models import (
    BetaAssemblyJob,
    BetaCarpentryOrder,
    BetaCarpentryWorkshop,
    BetaClearanceJob,
    BetaCushionJob,
    BetaFabricDispatch,
    BetaFabricNeed,
    BetaFabricRoll,
    BetaFoamJob,
    BetaPaintOrder,
    BetaQcInspection,
    BetaUpholsteryJob,
    Frame,
    Sale,
)
from logic.frames import WOOD_TYPE_LABELS
from logic.lookups import get_lookup_choices
from logic.sale_workflow import WORKFLOW_STAGE_LABELS

CARPENTRY_SALE_STAGES = (
    Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
    Sale.WORKFLOW_STAGE_MERCHANT_ASSIGNED,
    Sale.WORKFLOW_STAGE_IN_PRODUCTION,
    Sale.WORKFLOW_STAGE_PRODUCTION_DONE,
)

CAT_WORKSHOP_KIND = "beta_workshop_kind"
CAT_CARPENTRY_KIND = "beta_carpentry_kind"
CAT_CARPENTRY_STATUS = "beta_carpentry_status"
CAT_PAINT_KIND = "beta_paint_kind"
CAT_PAINT_STAGE = "beta_paint_stage"
CAT_UPHOLSTERY_STAGE = "beta_upholstery_stage"
CAT_QC_STATUS = "beta_qc_status"
CAT_QC_GRADE = "beta_qc_grade"

# اگر گزینه‌ای در دیتابیس نبود، choices مدل فقط به‌عنوان تور نجات استفاده می‌شود.
_FALLBACK_CHOICES = {
    CAT_WORKSHOP_KIND: BetaCarpentryWorkshop.KIND_CHOICES,
    CAT_CARPENTRY_KIND: BetaCarpentryOrder.KIND_CHOICES,
    CAT_CARPENTRY_STATUS: BetaCarpentryOrder.STATUS_CHOICES,
    CAT_PAINT_KIND: BetaPaintOrder.KIND_CHOICES,
    CAT_PAINT_STAGE: BetaPaintOrder.STAGE_CHOICES,
    CAT_UPHOLSTERY_STAGE: BetaUpholsteryJob.STAGE_CHOICES,
    CAT_QC_STATUS: BetaQcInspection.STATUS_CHOICES,
    CAT_QC_GRADE: BetaQcInspection.GRADE_CHOICES,
}


def options(category):
    """گزینه‌های یک دسته — از LookupOption دیتابیس."""
    rows = get_lookup_choices(category)
    if rows:
        return [{"value": row["code"], "label": row["label"], "meta": row.get("meta") or {}} for row in rows]
    return [{"value": code, "label": label, "meta": {}} for code, label in _FALLBACK_CHOICES.get(category, [])]


def codes(category):
    return [opt["value"] for opt in options(category)]


def label_of(category, code):
    for opt in options(category):
        if opt["value"] == code:
            return opt["label"]
    return code or "—"


def default_code(category, preferred=None):
    values = codes(category)
    if preferred and preferred in values:
        return preferred
    return values[0] if values else (preferred or "")


def final_code(category, preferred=None):
    """آخرین گزینه دسته — مرحله پایانی خط."""
    values = codes(category)
    return values[-1] if values else (preferred or "")


def _qc_archive_status():
    """وضعیتی که کار را به آرشیو می‌برد؛ با meta.archive در تنظیمات قابل تغییر است."""
    opts = options(CAT_QC_STATUS)
    for opt in opts:
        if opt["meta"].get("archive"):
            return opt["value"]
    values = [opt["value"] for opt in opts]
    if BetaQcInspection.STATUS_APPROVED in values:
        return BetaQcInspection.STATUS_APPROVED
    return values[-1] if values else BetaQcInspection.STATUS_APPROVED


def _text(value, default=""):
    return str(value).strip() if value is not None else default


def _optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _positive_int(value, default=1, minimum=1):
    parsed = _optional_int(value)
    if parsed is None or parsed < minimum:
        return default
    return parsed


def _clamp_progress(value):
    parsed = _optional_int(value)
    if parsed is None:
        return 0
    return max(0, min(100, parsed))


def _money(value, default=0):
    if value in (None, ""):
        return Decimal(default)
    try:
        parsed = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("مبلغ نامعتبر است.")
    if parsed < 0:
        raise ValueError("مبلغ نمی‌تواند منفی باشد.")
    return parsed


def _qty(value, default=0):
    if value in (None, ""):
        return Decimal(default)
    try:
        parsed = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("مقدار نامعتبر است.")
    if parsed < 0:
        raise ValueError("مقدار نمی‌تواند منفی باشد.")
    return parsed


def _date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    parsed = parse_date(str(value))
    if parsed is None:
        raise ValueError("تاریخ نامعتبر است.")
    return parsed


def _notes_log(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = _text(value)
    return [text] if text else []


def _next_code(model, prefix):
    last = model.all_objects.order_by("-id").values_list("id", flat=True).first()
    nxt = (last or 0) + 1
    code = f"{prefix}-{nxt:04d}"
    while model.all_objects.filter(code=code).exists():
        nxt += 1
        code = f"{prefix}-{nxt:04d}"
    return code


def _resolve_sale(sale_id):
    if not sale_id:
        return None
    sale = Sale.objects.filter(pk=sale_id, is_deleted=False).first()
    if not sale:
        raise ValueError("سفارش یافت نشد.")
    return sale


def _resolve_frame(frame_id):
    if not frame_id:
        return None
    frame = Frame.objects.filter(pk=frame_id, is_deleted=False, is_active=True).first()
    if not frame:
        raise ValueError("کلاف یافت نشد.")
    return frame


def _line_product_label(line):
    frame = line.frame
    if frame:
        model_name = line.frame_model.name if line.frame_model_id else ""
        return " — ".join(part for part in (frame.name, model_name) if part)
    return line.product_name or ""


def carpentry_snapshot_from_sale(sale):
    """اطلاعات پیش‌فرض دستور نجاری از سفارش کارخانه."""
    lines = list(sale.line_items.select_related("frame", "frame_model").all())
    primary = next((line for line in lines if line.frame_id), lines[0] if lines else None)
    frame = primary.frame if primary and primary.frame_id else None
    quantity = sum(int(line.quantity or 0) for line in lines) if lines else 1
    return {
        "sale_id": sale.id,
        "customer_name": sale.customer.full_name if sale.customer_id else "",
        "order_ref": sale.invoice_number or str(sale.id),
        "product_name": _line_product_label(primary) if primary else "",
        "wood_type": WOOD_TYPE_LABELS.get(frame.wood_type, frame.wood_type) if frame else "",
        "frame_id": frame.id if frame else None,
        "quantity": max(quantity, 1),
        "due_date": sale.delivery_date.isoformat() if sale.delivery_date else None,
        "workflow_stage": sale.workflow_stage_id,
        "workflow_stage_display": WORKFLOW_STAGE_LABELS.get(sale.workflow_stage_id, sale.workflow_stage_id),
    }


def _apply_sale_snapshot(order, sale):
    snap = carpentry_snapshot_from_sale(sale)
    order.sale = sale
    order.customer_name = snap["customer_name"]
    order.order_ref = snap["order_ref"]
    order.product_name = snap["product_name"] or order.product_name
    order.wood_type = snap["wood_type"]
    order.quantity = snap["quantity"]
    order.due_date = _date(snap["due_date"]) if snap.get("due_date") else order.due_date
    if snap.get("frame_id"):
        order.frame = _resolve_frame(snap["frame_id"])


def _apply_frame_snapshot(order, frame):
    order.frame = frame
    order.product_name = frame.name
    order.wood_type = WOOD_TYPE_LABELS.get(frame.wood_type, frame.wood_type)


def list_carpentry_source_sales(limit=100):
    linked = set(
        BetaCarpentryOrder.objects.exclude(sale_id__isnull=True).values_list("sale_id", flat=True)
    )
    qs = (
        Sale.objects.filter(
            is_deleted=False,
            fulfillment_route=Sale.FULFILLMENT_ROUTE_FACTORY,
            workflow_stage_id__in=CARPENTRY_SALE_STAGES,
        )
        .select_related("customer")
        .prefetch_related("line_items__frame", "line_items__frame_model")
        .order_by("-id")[: max(1, min(int(limit or 100), 200))]
    )
    results = []
    for sale in qs:
        snap = carpentry_snapshot_from_sale(sale)
        results.append(
            {
                "id": sale.id,
                "label": f"{snap['order_ref']} — {snap['customer_name'] or 'بدون مشتری'}",
                "workflow_stage": snap["workflow_stage"],
                "workflow_stage_display": snap["workflow_stage_display"],
                "has_carpentry_order": sale.id in linked,
                **snap,
            }
        )
    return results


def list_carpentry_frame_options(limit=200):
    qs = Frame.objects.filter(is_deleted=False, is_active=True).order_by("name")[: max(1, min(int(limit or 200), 500))]
    return [
        {
            "id": frame.id,
            "label": f"{frame.name} ({WOOD_TYPE_LABELS.get(frame.wood_type, frame.wood_type)})",
            "name": frame.name,
            "wood_type": frame.wood_type,
            "wood_type_display": WOOD_TYPE_LABELS.get(frame.wood_type, frame.wood_type),
        }
        for frame in qs
    ]


def carpentry_sources(limit_sales=100, limit_frames=200):
    return {
        "sales": list_carpentry_source_sales(limit_sales),
        "frames": list_carpentry_frame_options(limit_frames),
    }


def _choice(value, allowed, label, default=None):
    text = _text(value)
    if not text:
        if default is not None:
            return default
        raise ValueError(f"{label} را انتخاب کنید.")
    if text not in allowed:
        raise ValueError(f"{label} نامعتبر است.")
    return text


def _count_by(qs, field):
    return {row[field]: row["total"] for row in qs.values(field).annotate(total=Count("id"))}


def _distinct_values(model, field):
    """مقادیر ثبت‌شده یک ستون — برای پیشنهاد در فرم‌ها به‌جای نمونه‌های ثابت."""
    return sorted(
        value
        for value in model.objects.values_list(field, flat=True).distinct()
        if (value or "").strip()
    )


def _append_note(existing, note):
    log = list(existing or [])
    text = _text(note)
    if text:
        log.append(text)
    return log


def workshop_to_dict(workshop, current_count=None):
    return {
        "id": workshop.id,
        "name": workshop.name,
        "kind": workshop.kind,
        "kind_display": label_of(CAT_WORKSHOP_KIND, workshop.kind),
        "is_active": workshop.is_active,
        "current_count": current_count if current_count is not None else 0,
    }


def carpentry_order_to_dict(order):
    workshop = order.workshop
    frame = order.frame
    sale = order.sale
    return {
        "id": order.id,
        "code": order.code,
        "workshop_id": workshop.id if workshop else None,
        "workshop_name": workshop.name if workshop else "",
        "workshop_kind": workshop.kind if workshop else "",
        "kind": order.kind,
        "kind_display": label_of(CAT_CARPENTRY_KIND, order.kind),
        "sale_id": order.sale_id,
        "sale_workflow_stage": sale.workflow_stage_id if sale else "",
        "sale_workflow_stage_display": (
            WORKFLOW_STAGE_LABELS.get(sale.workflow_stage_id, sale.workflow_stage_id) if sale else ""
        ),
        "frame_id": frame.id if frame else None,
        "frame_name": frame.name if frame else "",
        "customer_name": order.customer_name,
        "order_ref": order.order_ref,
        "product_name": order.product_name,
        "wood_type": order.wood_type,
        "quantity": order.quantity,
        "due_date": order.due_date.isoformat() if order.due_date else None,
        "freight_cost": int(order.freight_cost or 0),
        "status": order.status,
        "status_display": label_of(CAT_CARPENTRY_STATUS, order.status),
        "notes_log": list(order.notes_log or []),
    }


def paint_order_to_dict(order):
    return {
        "id": order.id,
        "code": order.code,
        "sale_id": order.sale_id,
        "product_name": order.product_name,
        "kind": order.kind,
        "kind_display": label_of(CAT_PAINT_KIND, order.kind),
        "color_name": order.color_name,
        "stage": order.stage,
        "stage_display": label_of(CAT_PAINT_STAGE, order.stage),
        "is_final_stage": order.stage == final_code(CAT_PAINT_STAGE, BetaPaintOrder.STAGE_QC),
        "progress": order.progress,
        "qc_issue": order.qc_issue,
        "notes_log": list(order.notes_log or []),
    }


def upholstery_job_to_dict(job):
    return {
        "id": job.id,
        "code": job.code,
        "order_ref": job.order_ref,
        "sale_id": job.sale_id,
        "product_name": job.product_name,
        "foam_material": job.foam_material,
        "craftsman": job.craftsman,
        "stage": job.stage,
        "stage_display": label_of(CAT_UPHOLSTERY_STAGE, job.stage),
        "progress": job.progress,
        "due_date": job.due_date.isoformat() if job.due_date else None,
        "is_done": job.stage == final_code(CAT_UPHOLSTERY_STAGE, BetaUpholsteryJob.STAGE_QC) and job.progress >= 100,
    }


def fabric_roll_to_dict(roll):
    meters = Decimal(roll.meters or 0)
    unit_cost = Decimal(roll.unit_cost or 0)
    return {
        "id": roll.id,
        "code": roll.code,
        "color_name": roll.color_name,
        "company": roll.company,
        "fabric_type": roll.fabric_type,
        "country": roll.country,
        "unit_cost": int(unit_cost),
        "meters": float(meters),
        "image_url": roll.image_url,
        "min_meters": float(roll.min_meters or 0),
        "value": int(meters * unit_cost),
        "low_stock": meters <= Decimal(roll.min_meters or 0),
    }


def fabric_dispatch_to_dict(dispatch):
    roll = dispatch.roll
    return {
        "id": dispatch.id,
        "code": dispatch.code,
        "roll_id": roll.id if roll else None,
        "roll_code": roll.code if roll else "",
        "destination": dispatch.destination,
        "meters": float(dispatch.meters or 0),
        "sent_date": dispatch.sent_date.isoformat() if dispatch.sent_date else None,
    }


def qc_inspection_to_dict(item):
    return {
        "id": item.id,
        "code": item.code,
        "order_ref": item.order_ref,
        "sale_id": item.sale_id,
        "buyer_name": item.buyer_name,
        "invoice_ref": item.invoice_ref,
        "origin": item.origin,
        "product_name": item.product_name,
        "requirements": item.requirements,
        "quantity": item.quantity,
        "wood_color": item.wood_color,
        "fabric_color": item.fabric_color,
        "status": item.status,
        "status_display": label_of(CAT_QC_STATUS, item.status),
        "grade": item.grade,
        "grade_display": label_of(CAT_QC_GRADE, item.grade) if item.grade else "—",
        "scan_url": item.scan_url,
        "entered_at": item.entered_at.isoformat() if item.entered_at else None,
    }


def list_workshops():
    qs = BetaCarpentryWorkshop.objects.all()
    counts = (
        BetaCarpentryOrder.objects.filter(status=BetaCarpentryOrder.STATUS_IN_PROGRESS)
        .values("workshop_id")
        .annotate(total=Count("id"))
    )
    by_id = {row["workshop_id"]: row["total"] for row in counts}
    return [workshop_to_dict(w, by_id.get(w.id, 0)) for w in qs]


def create_workshop(data):
    name = _text(data.get("name"))
    if not name:
        raise ValueError("نام واحد را وارد کنید.")
    kind = _choice(
        data.get("kind"),
        set(codes(CAT_WORKSHOP_KIND)),
        "نوع واحد",
        default_code(CAT_WORKSHOP_KIND, BetaCarpentryWorkshop.KIND_INTERNAL),
    )
    workshop = BetaCarpentryWorkshop.objects.create(
        name=name,
        kind=kind,
        is_active=bool(data.get("is_active", True)),
    )
    return workshop


def update_workshop(workshop, data):
    if "name" in data:
        name = _text(data.get("name"))
        if not name:
            raise ValueError("نام واحد را وارد کنید.")
        workshop.name = name
    if "kind" in data:
        workshop.kind = _choice(data.get("kind"), set(codes(CAT_WORKSHOP_KIND)), "نوع واحد")
    if "is_active" in data:
        workshop.is_active = bool(data.get("is_active"))
    workshop.save()
    return workshop


def delete_workshop(workshop):
    if workshop.orders.exists():
        raise ValueError("این واحد دستور فعال دارد و قابل حذف نیست.")
    workshop.soft_delete()


def filter_carpentry_orders(qs, params):
    search = _text(params.get("search"))
    kind = _text(params.get("kind"))
    status = _text(params.get("status"))
    workshop_id = _optional_int(params.get("workshop_id"))
    if search:
        qs = qs.filter(
            Q(code__icontains=search)
            | Q(product_name__icontains=search)
            | Q(customer_name__icontains=search)
            | Q(order_ref__icontains=search)
        )
    if kind:
        qs = qs.filter(kind=kind)
    if status:
        qs = qs.filter(status=status)
    if workshop_id:
        qs = qs.filter(workshop_id=workshop_id)
    return qs.select_related("workshop", "sale", "frame")


def _apply_carpentry_fields(order, data, *, creating):
    if creating or "workshop_id" in data:
        workshop = BetaCarpentryWorkshop.objects.filter(pk=data.get("workshop_id"), is_active=True).first()
        if not workshop:
            raise ValueError("واحد نجاری را انتخاب کنید.")
        order.workshop = workshop
    if creating or "kind" in data:
        order.kind = _choice(
            data.get("kind"),
            set(codes(CAT_CARPENTRY_KIND)),
            "نوع دستور",
            default_code(CAT_CARPENTRY_KIND, BetaCarpentryOrder.KIND_BUILD),
        )

    sale_id = data.get("sale_id") if "sale_id" in data else (order.sale_id if not creating else None)
    frame_id = data.get("frame_id") if "frame_id" in data else (order.frame_id if not creating else None)
    sync_sale = "sale_id" in data and _optional_int(data.get("sale_id"))
    sync_frame = "frame_id" in data and _optional_int(data.get("frame_id"))

    if sync_sale:
        sale = _resolve_sale(sale_id)
        _apply_sale_snapshot(order, sale)
    elif "sale_id" in data and not _optional_int(data.get("sale_id")):
        order.sale = None

    if sync_frame:
        _apply_frame_snapshot(order, _resolve_frame(frame_id))
    elif "frame_id" in data and not _optional_int(data.get("frame_id")):
        order.frame = None

    if creating or "product_name" in data:
        name = _text(data.get("product_name"))
        if name:
            order.product_name = name
    if "customer_name" in data and not sync_sale:
        order.customer_name = _text(data.get("customer_name"))
    if "order_ref" in data and not sync_sale:
        order.order_ref = _text(data.get("order_ref"))
    if "wood_type" in data and not sync_sale and not sync_frame:
        order.wood_type = _text(data.get("wood_type"))
    if ("quantity" in data or creating) and not sync_sale:
        order.quantity = _positive_int(data.get("quantity"), default=order.quantity or 1)
    if ("due_date" in data or creating) and not sync_sale:
        order.due_date = _date(data.get("due_date"))
    if "freight_cost" in data or creating:
        order.freight_cost = _money(data.get("freight_cost"), 0)
    if "status" in data:
        order.status = _choice(data.get("status"), set(codes(CAT_CARPENTRY_STATUS)), "وضعیت")
    elif creating:
        order.status = default_code(CAT_CARPENTRY_STATUS, BetaCarpentryOrder.STATUS_IN_PROGRESS)
    if "notes_log" in data:
        order.notes_log = _notes_log(data.get("notes_log"))
    note = _text(data.get("note"))
    if note:
        order.notes_log = _append_note(order.notes_log, note)
    if not _text(order.product_name):
        raise ValueError("نام محصول / مدل کلاف را وارد کنید.")
    return order


def create_carpentry_order(data):
    order = BetaCarpentryOrder(code=_text(data.get("code")) or _next_code(BetaCarpentryOrder, "CRF"))
    _apply_carpentry_fields(order, data, creating=True)
    order.save()
    return order


def update_carpentry_order(order, data):
    _apply_carpentry_fields(order, data, creating=False)
    order.save()
    return order


def carpentry_stats(params=None):
    from logic.beta_carpentry_modules import carpentry_dashboard

    params = params or {}
    workshop_id = _optional_int(params.get("workshop_id"))
    workshop_kind = _text(params.get("workshop_kind"))
    qs = BetaCarpentryOrder.objects.all()
    if workshop_id:
        qs = qs.filter(workshop_id=workshop_id)
    elif workshop_kind:
        qs = qs.filter(workshop__kind=workshop_kind)
    by_status = _count_by(qs, "status")
    by_kind = _count_by(qs, "kind")
    dashboard = carpentry_dashboard(workshop_id=workshop_id, workshop_kind=workshop_kind or None)
    return {
        "workshops": BetaCarpentryWorkshop.objects.filter(is_active=True).count(),
        "total": qs.count(),
        "by_status": {code: by_status.get(code, 0) for code in codes(CAT_CARPENTRY_STATUS)},
        "by_kind": {code: by_kind.get(code, 0) for code in codes(CAT_CARPENTRY_KIND)},
        "statuses": options(CAT_CARPENTRY_STATUS),
        "kinds": options(CAT_CARPENTRY_KIND),
        "workshop_kinds": options(CAT_WORKSHOP_KIND),
        "freight_cost": int(qs.aggregate(total=Sum("freight_cost"))["total"] or 0),
        "wood_type_options": _distinct_values(BetaCarpentryOrder, "wood_type"),
        "summary": dashboard["summary"],
        "modules": dashboard["modules"],
    }


def filter_paint_orders(qs, params):
    search = _text(params.get("search"))
    kind = _text(params.get("kind"))
    stage = _text(params.get("stage"))
    if search:
        qs = qs.filter(Q(code__icontains=search) | Q(product_name__icontains=search) | Q(color_name__icontains=search))
    if kind:
        qs = qs.filter(kind=kind)
    if stage:
        qs = qs.filter(stage=stage)
    return qs


def _apply_paint_fields(order, data, *, creating):
    if creating or "product_name" in data:
        name = _text(data.get("product_name"))
        if not name:
            raise ValueError("نام محصول را وارد کنید.")
        order.product_name = name
    if creating or "kind" in data:
        order.kind = _choice(
            data.get("kind"),
            set(codes(CAT_PAINT_KIND)),
            "نوع سفارش",
            default_code(CAT_PAINT_KIND, BetaPaintOrder.KIND_NORMAL),
        )
    if "sale_id" in data or creating:
        order.sale = _resolve_sale(data.get("sale_id"))
    if "color_name" in data or creating:
        order.color_name = _text(data.get("color_name"))
    if "stage" in data:
        order.stage = _choice(data.get("stage"), set(codes(CAT_PAINT_STAGE)), "مرحله")
    if "progress" in data or creating:
        order.progress = _clamp_progress(data.get("progress") if "progress" in data else 0)
    if "qc_issue" in data or creating:
        order.qc_issue = _text(data.get("qc_issue"))
    if "notes_log" in data:
        order.notes_log = _notes_log(data.get("notes_log"))
    note = _text(data.get("note"))
    if note:
        order.notes_log = _append_note(order.notes_log, note)
    return order


def create_paint_order(data):
    order = BetaPaintOrder(
        code=_text(data.get("code")) or _next_code(BetaPaintOrder, "SO"),
        stage=_choice(
            data.get("stage"),
            set(codes(CAT_PAINT_STAGE)),
            "مرحله",
            default_code(CAT_PAINT_STAGE, BetaPaintOrder.STAGE_RAW),
        ),
    )
    _apply_paint_fields(order, data, creating=True)
    order.save()
    return order


def update_paint_order(order, data):
    _apply_paint_fields(order, data, creating=False)
    order.save()
    return order


def advance_paint_order(order, note=""):
    stages = codes(CAT_PAINT_STAGE)
    idx = stages.index(order.stage) if order.stage in stages else 0
    if idx >= len(stages) - 1:
        raise ValueError("این سفارش در آخرین مرحله خط رنگ است.")
    order.stage = stages[idx + 1]
    order.progress = min(100, ((idx + 1) * 100) // (len(stages) - 1))
    if note:
        order.notes_log = _append_note(order.notes_log, note)
    order.save(update_fields=["stage", "progress", "notes_log", "updated_at"])
    return order


def paint_stats():
    qs = BetaPaintOrder.objects.all()
    by_kind = _count_by(qs, "kind")
    by_stage = _count_by(qs, "stage")
    stage_codes = codes(CAT_PAINT_STAGE)
    return {
        "total": qs.count(),
        "delivered": by_stage.get(final_code(CAT_PAINT_STAGE, BetaPaintOrder.STAGE_QC), 0),
        "by_kind": {code: by_kind.get(code, 0) for code in codes(CAT_PAINT_KIND)},
        "by_stage": {code: by_stage.get(code, 0) for code in stage_codes},
        "stages": options(CAT_PAINT_STAGE),
        "kinds": options(CAT_PAINT_KIND),
        "final_stage": stage_codes[-1] if stage_codes else "",
        "color_options": _distinct_values(BetaPaintOrder, "color_name"),
    }


def filter_upholstery_jobs(qs, params):
    search = _text(params.get("search"))
    stage = _text(params.get("stage"))
    if search:
        qs = qs.filter(
            Q(code__icontains=search)
            | Q(product_name__icontains=search)
            | Q(order_ref__icontains=search)
            | Q(craftsman__icontains=search)
        )
    if stage:
        qs = qs.filter(stage=stage)
    return qs


def _apply_upholstery_fields(job, data, *, creating):
    if creating or "product_name" in data:
        name = _text(data.get("product_name"))
        if not name:
            raise ValueError("مدل مبلمان را وارد کنید.")
        job.product_name = name
    if "sale_id" in data or creating:
        job.sale = _resolve_sale(data.get("sale_id"))
    if "order_ref" in data or creating:
        job.order_ref = _text(data.get("order_ref"))
    if "foam_material" in data or creating:
        job.foam_material = _text(data.get("foam_material"))
    if "craftsman" in data or creating:
        job.craftsman = _text(data.get("craftsman"))
    if "stage" in data:
        job.stage = _choice(data.get("stage"), set(codes(CAT_UPHOLSTERY_STAGE)), "مرحله فنی")
    if "progress" in data or creating:
        job.progress = _clamp_progress(data.get("progress") if "progress" in data else 0)
    if "due_date" in data or creating:
        job.due_date = _date(data.get("due_date"))
    return job


def create_upholstery_job(data):
    job = BetaUpholsteryJob(
        code=_text(data.get("code")) or _next_code(BetaUpholsteryJob, "UPH"),
        stage=_choice(
            data.get("stage"),
            set(codes(CAT_UPHOLSTERY_STAGE)),
            "مرحله فنی",
            default_code(CAT_UPHOLSTERY_STAGE, BetaUpholsteryJob.STAGE_WEBBING),
        ),
    )
    _apply_upholstery_fields(job, data, creating=True)
    job.save()
    return job


def update_upholstery_job(job, data):
    _apply_upholstery_fields(job, data, creating=False)
    job.save()
    return job


def advance_upholstery_job(job):
    stages = codes(CAT_UPHOLSTERY_STAGE)
    idx = stages.index(job.stage) if job.stage in stages else 0
    if idx >= len(stages) - 1:
        job.progress = 100
        job.save(update_fields=["progress", "updated_at"])
        return job
    job.stage = stages[idx + 1]
    job.progress = min(100, ((idx + 1) * 100) // (len(stages) - 1))
    job.save(update_fields=["stage", "progress", "updated_at"])
    return job


def _upholstery_stats_qs(params=None):
    params = params or {}
    qs = BetaUpholsteryJob.objects.all()
    search = _text(params.get("search"))
    if search:
        qs = qs.filter(
            Q(code__icontains=search)
            | Q(product_name__icontains=search)
            | Q(order_ref__icontains=search)
            | Q(craftsman__icontains=search)
        )
    return qs


def upholstery_stats(params=None):
    qs = _upholstery_stats_qs(params)
    final = final_code(CAT_UPHOLSTERY_STAGE, BetaUpholsteryJob.STAGE_QC)
    by_stage = _count_by(qs, "stage")
    return {
        "total": qs.count(),
        "assembling": qs.exclude(stage=final).count(),
        "ready_for_qc": by_stage.get(final, 0),
        "by_stage": {code: by_stage.get(code, 0) for code in codes(CAT_UPHOLSTERY_STAGE)},
        "stages": options(CAT_UPHOLSTERY_STAGE),
        "final_stage": final,
        "foam_options": _distinct_values(BetaUpholsteryJob, "foam_material"),
        "craftsman_options": _distinct_values(BetaUpholsteryJob, "craftsman"),
    }


def filter_fabric_rolls(qs, params):
    search = _text(params.get("search"))
    company = _text(params.get("company"))
    fabric_type = _text(params.get("fabric_type"))
    country = _text(params.get("country"))
    if search:
        qs = qs.filter(
            Q(code__icontains=search)
            | Q(color_name__icontains=search)
            | Q(company__icontains=search)
            | Q(fabric_type__icontains=search)
        )
    if company:
        qs = qs.filter(company=company)
    if fabric_type:
        qs = qs.filter(fabric_type=fabric_type)
    if country:
        qs = qs.filter(country=country)
    return qs


def _apply_roll_fields(roll, data, *, creating):
    if creating or "code" in data:
        code = _text(data.get("code")) or (roll.code if not creating else "")
        if creating and not code:
            code = _next_code(BetaFabricRoll, "FB")
        if not code:
            raise ValueError("کد پارچه را وارد کنید.")
        roll.code = code
    if "color_name" in data or creating:
        roll.color_name = _text(data.get("color_name"))
    if "company" in data or creating:
        roll.company = _text(data.get("company"))
    if "fabric_type" in data or creating:
        roll.fabric_type = _text(data.get("fabric_type"))
    if "country" in data or creating:
        roll.country = _text(data.get("country"))
    if "unit_cost" in data or creating:
        roll.unit_cost = _money(data.get("unit_cost"), 0)
    if "meters" in data or creating:
        roll.meters = _qty(data.get("meters"), 0)
    if "image_url" in data or creating:
        roll.image_url = _text(data.get("image_url"))
    if "min_meters" in data or creating:
        roll.min_meters = _qty(data.get("min_meters"), 0)
    return roll


def create_fabric_roll(data):
    roll = BetaFabricRoll()
    _apply_roll_fields(roll, data, creating=True)
    roll.save()
    return roll


def update_fabric_roll(roll, data):
    _apply_roll_fields(roll, data, creating=False)
    roll.save()
    return roll


@transaction.atomic
def create_fabric_dispatch(data):
    roll = BetaFabricRoll.objects.select_for_update().filter(pk=data.get("roll_id")).first()
    if not roll:
        raise ValueError("طاقه پارچه را انتخاب کنید.")
    meters = _qty(data.get("meters"))
    if meters <= 0:
        raise ValueError("متراژ ارسالی باید بیشتر از صفر باشد.")
    if meters > Decimal(roll.meters or 0):
        raise ValueError("متراژ حواله از موجودی طاقه بیشتر است.")
    destination = _text(data.get("destination"))
    if not destination:
        raise ValueError("کارگاه مقصد را وارد کنید.")
    sent_date = _date(data.get("sent_date")) or timezone.localdate()
    dispatch = BetaFabricDispatch.objects.create(
        code=_text(data.get("code")) or _next_code(BetaFabricDispatch, "DISP"),
        roll=roll,
        destination=destination,
        meters=meters,
        sent_date=sent_date,
    )
    roll.meters = Decimal(roll.meters or 0) - meters
    roll.save(update_fields=["meters", "updated_at"])
    return dispatch


def fabric_stats():
    rolls = BetaFabricRoll.objects.all()
    agg = rolls.aggregate(meters=Sum("meters"), count=Count("id"))
    value = 0
    low = 0
    companies = set()
    for roll in rolls:
        value += int(Decimal(roll.meters or 0) * Decimal(roll.unit_cost or 0))
        if Decimal(roll.meters or 0) <= Decimal(roll.min_meters or 0):
            low += 1
        if roll.company:
            companies.add(roll.company)
    return {
        "meters": float(agg["meters"] or 0),
        "rolls": agg["count"] or 0,
        "value": value,
        "companies": len(companies),
        "low_stock": low,
        "dispatches": BetaFabricDispatch.objects.count(),
        # فهرست فیلترها از خود داده‌های انبار ساخته می‌شود، نه از لیست ثابت.
        "company_options": _distinct_values(BetaFabricRoll, "company"),
        "fabric_type_options": _distinct_values(BetaFabricRoll, "fabric_type"),
        "country_options": _distinct_values(BetaFabricRoll, "country"),
        "destination_options": _distinct_values(BetaFabricDispatch, "destination"),
        "needs_pending": BetaFabricNeed.objects.filter(status=BetaFabricNeed.STATUS_PENDING).count(),
        "needs_total": BetaFabricNeed.objects.count(),
    }


def filter_qc_inspections(qs, params):
    search = _text(params.get("search"))
    status = _text(params.get("status"))
    archive = _text(params.get("archive"))
    if search:
        qs = qs.filter(
            Q(code__icontains=search)
            | Q(order_ref__icontains=search)
            | Q(buyer_name__icontains=search)
            | Q(product_name__icontains=search)
            | Q(wood_color__icontains=search)
            | Q(fabric_color__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)
    elif archive == "1":
        qs = qs.filter(status=_qc_archive_status())
    elif archive == "0":
        qs = qs.exclude(status=_qc_archive_status())
    return qs


def _apply_qc_fields(item, data, *, creating):
    if creating or "product_name" in data:
        name = _text(data.get("product_name"))
        if not name:
            raise ValueError("نام محصول را وارد کنید.")
        item.product_name = name
    if "sale_id" in data or creating:
        item.sale = _resolve_sale(data.get("sale_id"))
    if "order_ref" in data or creating:
        item.order_ref = _text(data.get("order_ref"))
    if "buyer_name" in data or creating:
        item.buyer_name = _text(data.get("buyer_name"))
    if "invoice_ref" in data or creating:
        item.invoice_ref = _text(data.get("invoice_ref"))
    if "origin" in data or creating:
        item.origin = _text(data.get("origin"))
    if "requirements" in data or creating:
        item.requirements = _text(data.get("requirements"))
    if "quantity" in data or creating:
        item.quantity = _positive_int(data.get("quantity"), default=1)
    if "wood_color" in data or creating:
        item.wood_color = _text(data.get("wood_color"))
    if "fabric_color" in data or creating:
        item.fabric_color = _text(data.get("fabric_color"))
    if "status" in data:
        item.status = _choice(data.get("status"), set(codes(CAT_QC_STATUS)), "وضعیت")
    elif creating:
        item.status = default_code(CAT_QC_STATUS, BetaQcInspection.STATUS_PENDING)
    if "grade" in data or creating:
        grade = _text(data.get("grade"))
        if grade and grade not in codes(CAT_QC_GRADE):
            raise ValueError("گرید نامعتبر است.")
        item.grade = grade
    if "scan_url" in data or creating:
        item.scan_url = _text(data.get("scan_url"))
    if "entered_at" in data or creating:
        item.entered_at = _date(data.get("entered_at")) or (timezone.localdate() if creating else item.entered_at)
    return item


def create_qc_inspection(data):
    item = BetaQcInspection(code=_text(data.get("code")) or _next_code(BetaQcInspection, "QC"))
    _apply_qc_fields(item, data, creating=True)
    item.save()
    return item


def update_qc_inspection(item, data):
    _apply_qc_fields(item, data, creating=False)
    item.save()
    return item


def evaluate_qc_inspection(item, data):
    status = _choice(data.get("status"), set(codes(CAT_QC_STATUS)), "وضعیت")
    grade = _text(data.get("grade"))
    if grade and grade not in codes(CAT_QC_GRADE):
        raise ValueError("گرید نامعتبر است.")
    item.status = status
    if grade:
        item.grade = grade
    if "scan_url" in data:
        item.scan_url = _text(data.get("scan_url"))
    if "requirements" in data:
        item.requirements = _text(data.get("requirements"))
    item.save()
    return item


def _qc_stats_qs(params=None):
    params = params or {}
    qs = BetaQcInspection.objects.all()
    search = _text(params.get("search"))
    if search:
        qs = qs.filter(
            Q(code__icontains=search)
            | Q(order_ref__icontains=search)
            | Q(buyer_name__icontains=search)
            | Q(product_name__icontains=search)
            | Q(wood_color__icontains=search)
            | Q(fabric_color__icontains=search)
        )
    return qs


def qc_stats(params=None):
    qs = _qc_stats_qs(params)
    archive = _qc_archive_status()
    by_status = _count_by(qs, "status")
    total = qs.count()
    approved = by_status.get(archive, 0)
    return {
        "approved": approved,
        "current": total - approved,
        "total": total,
        "by_status": {code: by_status.get(code, 0) for code in codes(CAT_QC_STATUS)},
        "statuses": options(CAT_QC_STATUS),
        "grades": options(CAT_QC_GRADE),
        "archive_status": archive,
        "origin_options": _distinct_values(BetaQcInspection, "origin"),
        "wood_color_options": _distinct_values(BetaQcInspection, "wood_color"),
        "fabric_color_options": _distinct_values(BetaQcInspection, "fabric_color"),
    }


def _pipeline_job_to_dict(job, *, name_field, stages):
    return {
        "id": job.id,
        "code": job.code,
        "sale_id": job.sale_id,
        "product_name": job.product_name,
        name_field: getattr(job, name_field, ""),
        "stage": job.stage,
        "stage_display": dict(stages).get(job.stage, job.stage),
        "is_final_stage": job.stage == stages[-1][0] if stages else False,
        "progress": job.progress,
        "notes_log": list(job.notes_log or []),
    }


def _advance_pipeline(job, stage_order):
    idx = stage_order.index(job.stage) if job.stage in stage_order else 0
    if idx >= len(stage_order) - 1:
        job.progress = 100
        job.save(update_fields=["progress", "updated_at"])
        return job
    job.stage = stage_order[idx + 1]
    job.progress = min(100, ((idx + 1) * 100) // (len(stage_order) - 1))
    job.save(update_fields=["stage", "progress", "updated_at"])
    return job


def foam_job_to_dict(job):
    return _pipeline_job_to_dict(job, name_field="foam_name", stages=BetaFoamJob.STAGE_CHOICES)


def filter_foam_jobs(qs, params):
    search = _text(params.get("search"))
    stage = _text(params.get("stage"))
    if search:
        qs = qs.filter(Q(code__icontains=search) | Q(product_name__icontains=search) | Q(foam_name__icontains=search))
    if stage:
        qs = qs.filter(stage=stage)
    return qs


def create_foam_job(data):
    name = _text(data.get("product_name"))
    if not name:
        raise ValueError("نام محصول را وارد کنید.")
    job = BetaFoamJob(
        code=_text(data.get("code")) or _next_code(BetaFoamJob, "FM"),
        sale=_resolve_sale(data.get("sale_id")),
        product_name=name,
        foam_name=_text(data.get("foam_name")),
        stage=_text(data.get("stage")) or BetaFoamJob.STAGE_QUEUE,
        progress=_clamp_progress(data.get("progress")),
    )
    job.save()
    return job


def update_foam_job(job, data):
    if "product_name" in data:
        name = _text(data.get("product_name"))
        if not name:
            raise ValueError("نام محصول را وارد کنید.")
        job.product_name = name
    if "sale_id" in data:
        job.sale = _resolve_sale(data.get("sale_id"))
    if "foam_name" in data:
        job.foam_name = _text(data.get("foam_name"))
    if "stage" in data:
        job.stage = _text(data.get("stage")) or job.stage
    if "progress" in data:
        job.progress = _clamp_progress(data.get("progress"))
    note = _text(data.get("note"))
    if note:
        job.notes_log = _append_note(job.notes_log, note)
    job.save()
    return job


def advance_foam_job(job):
    return _advance_pipeline(job, BetaFoamJob.STAGE_ORDER)


def foam_stats():
    qs = BetaFoamJob.objects.all()
    by_stage = _count_by(qs, "stage")
    return {
        "total": qs.count(),
        "by_stage": {code: by_stage.get(code, 0) for code, _ in BetaFoamJob.STAGE_CHOICES},
        "stages": [{"value": c, "label": l} for c, l in BetaFoamJob.STAGE_CHOICES],
        "final_stage": BetaFoamJob.STAGE_DONE,
    }


def cushion_job_to_dict(job):
    return _pipeline_job_to_dict(job, name_field="cushion_name", stages=BetaCushionJob.STAGE_CHOICES)


def filter_cushion_jobs(qs, params):
    search = _text(params.get("search"))
    stage = _text(params.get("stage"))
    if search:
        qs = qs.filter(Q(code__icontains=search) | Q(product_name__icontains=search) | Q(cushion_name__icontains=search))
    if stage:
        qs = qs.filter(stage=stage)
    return qs


def create_cushion_job(data):
    name = _text(data.get("product_name"))
    if not name:
        raise ValueError("نام محصول را وارد کنید.")
    job = BetaCushionJob(
        code=_text(data.get("code")) or _next_code(BetaCushionJob, "CS"),
        sale=_resolve_sale(data.get("sale_id")),
        product_name=name,
        cushion_name=_text(data.get("cushion_name")),
        stage=_text(data.get("stage")) or BetaCushionJob.STAGE_QUEUE,
        progress=_clamp_progress(data.get("progress")),
    )
    job.save()
    return job


def update_cushion_job(job, data):
    if "product_name" in data:
        name = _text(data.get("product_name"))
        if not name:
            raise ValueError("نام محصول را وارد کنید.")
        job.product_name = name
    if "sale_id" in data:
        job.sale = _resolve_sale(data.get("sale_id"))
    if "cushion_name" in data:
        job.cushion_name = _text(data.get("cushion_name"))
    if "stage" in data:
        job.stage = _text(data.get("stage")) or job.stage
    if "progress" in data:
        job.progress = _clamp_progress(data.get("progress"))
    note = _text(data.get("note"))
    if note:
        job.notes_log = _append_note(job.notes_log, note)
    job.save()
    return job


def advance_cushion_job(job):
    return _advance_pipeline(job, BetaCushionJob.STAGE_ORDER)


def cushion_stats():
    qs = BetaCushionJob.objects.all()
    by_stage = _count_by(qs, "stage")
    return {
        "total": qs.count(),
        "by_stage": {code: by_stage.get(code, 0) for code, _ in BetaCushionJob.STAGE_CHOICES},
        "stages": [{"value": c, "label": l} for c, l in BetaCushionJob.STAGE_CHOICES],
        "final_stage": BetaCushionJob.STAGE_DONE,
    }


def fabric_need_to_dict(need):
    return {
        "id": need.id,
        "code": need.code,
        "sale_id": need.sale_id,
        "product_name": need.product_name,
        "color_name": need.color_name,
        "recipe_name": need.recipe_name,
        "meters": float(need.meters or 0),
        "status": need.status,
        "status_display": dict(BetaFabricNeed.STATUS_CHOICES).get(need.status, need.status),
    }


def filter_fabric_needs(qs, params):
    search = _text(params.get("search"))
    status = _text(params.get("status"))
    if search:
        qs = qs.filter(
            Q(code__icontains=search)
            | Q(product_name__icontains=search)
            | Q(recipe_name__icontains=search)
            | Q(color_name__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)
    return qs


def create_fabric_need(data):
    name = _text(data.get("product_name"))
    if not name:
        raise ValueError("نام محصول را وارد کنید.")
    need = BetaFabricNeed(
        code=_text(data.get("code")) or _next_code(BetaFabricNeed, "FN"),
        sale=_resolve_sale(data.get("sale_id")),
        product_name=name,
        color_name=_text(data.get("color_name")),
        recipe_name=_text(data.get("recipe_name")),
        meters=_qty(data.get("meters"), default=0) if data.get("meters") not in (None, "") else Decimal(0),
        status=_text(data.get("status")) or BetaFabricNeed.STATUS_PENDING,
    )
    need.save()
    return need


def update_fabric_need(need, data):
    if "product_name" in data:
        name = _text(data.get("product_name"))
        if not name:
            raise ValueError("نام محصول را وارد کنید.")
        need.product_name = name
    if "color_name" in data:
        need.color_name = _text(data.get("color_name"))
    if "recipe_name" in data:
        need.recipe_name = _text(data.get("recipe_name"))
    if "meters" in data:
        need.meters = _qty(data.get("meters"), default=0)
    if "status" in data:
        need.status = _text(data.get("status")) or need.status
    need.save()
    return need


def assembly_job_to_dict(job):
    return _pipeline_job_to_dict(job, name_field="assembly_name", stages=BetaAssemblyJob.STAGE_CHOICES)


def filter_assembly_jobs(qs, params):
    search = _text(params.get("search"))
    stage = _text(params.get("stage"))
    if search:
        qs = qs.filter(
            Q(code__icontains=search) | Q(product_name__icontains=search) | Q(assembly_name__icontains=search)
        )
    if stage:
        qs = qs.filter(stage=stage)
    return qs


def create_assembly_job(data):
    name = _text(data.get("product_name"))
    if not name:
        raise ValueError("نام محصول را وارد کنید.")
    job = BetaAssemblyJob(
        code=_text(data.get("code")) or _next_code(BetaAssemblyJob, "AS"),
        sale=_resolve_sale(data.get("sale_id")),
        product_name=name,
        assembly_name=_text(data.get("assembly_name")),
        stage=_text(data.get("stage")) or BetaAssemblyJob.STAGE_QUEUE,
        progress=_clamp_progress(data.get("progress")),
    )
    job.save()
    return job


def update_assembly_job(job, data):
    if "product_name" in data:
        name = _text(data.get("product_name"))
        if not name:
            raise ValueError("نام محصول را وارد کنید.")
        job.product_name = name
    if "sale_id" in data:
        job.sale = _resolve_sale(data.get("sale_id"))
    if "assembly_name" in data:
        job.assembly_name = _text(data.get("assembly_name"))
    if "stage" in data:
        job.stage = _text(data.get("stage")) or job.stage
    if "progress" in data:
        job.progress = _clamp_progress(data.get("progress"))
    note = _text(data.get("note"))
    if note:
        job.notes_log = _append_note(job.notes_log, note)
    job.save()
    return job


def advance_assembly_job(job):
    return _advance_pipeline(job, BetaAssemblyJob.STAGE_ORDER)


def assembly_stats():
    qs = BetaAssemblyJob.objects.all()
    by_stage = _count_by(qs, "stage")
    return {
        "total": qs.count(),
        "by_stage": {code: by_stage.get(code, 0) for code, _ in BetaAssemblyJob.STAGE_CHOICES},
        "stages": [{"value": c, "label": l} for c, l in BetaAssemblyJob.STAGE_CHOICES],
        "final_stage": BetaAssemblyJob.STAGE_DONE,
    }


def clearance_job_to_dict(job):
    data = _pipeline_job_to_dict(job, name_field="destination", stages=BetaClearanceJob.STAGE_CHOICES)
    data["destination"] = job.destination or ""
    return data


def filter_clearance_jobs(qs, params):
    search = _text(params.get("search"))
    stage = _text(params.get("stage"))
    if search:
        qs = qs.filter(
            Q(code__icontains=search) | Q(product_name__icontains=search) | Q(destination__icontains=search)
        )
    if stage:
        qs = qs.filter(stage=stage)
    return qs


def create_clearance_job(data):
    name = _text(data.get("product_name"))
    if not name:
        raise ValueError("نام محصول را وارد کنید.")
    job = BetaClearanceJob(
        code=_text(data.get("code")) or _next_code(BetaClearanceJob, "CL"),
        sale=_resolve_sale(data.get("sale_id")),
        product_name=name,
        destination=_text(data.get("destination")),
        stage=_text(data.get("stage")) or BetaClearanceJob.STAGE_QUEUE,
        progress=_clamp_progress(data.get("progress")),
    )
    job.save()
    return job


def update_clearance_job(job, data):
    if "product_name" in data:
        name = _text(data.get("product_name"))
        if not name:
            raise ValueError("نام محصول را وارد کنید.")
        job.product_name = name
    if "sale_id" in data:
        job.sale = _resolve_sale(data.get("sale_id"))
    if "destination" in data:
        job.destination = _text(data.get("destination"))
    if "stage" in data:
        job.stage = _text(data.get("stage")) or job.stage
    if "progress" in data:
        job.progress = _clamp_progress(data.get("progress"))
    note = _text(data.get("note"))
    if note:
        job.notes_log = _append_note(job.notes_log, note)
    job.save()
    return job


def advance_clearance_job(job):
    job = _advance_pipeline(job, BetaClearanceJob.STAGE_ORDER)
    if job.stage == BetaClearanceJob.STAGE_RELEASED and job.sale_id:
        from logic.sale_workflow import complete_factory_production

        try:
            complete_factory_production(job.sale, None)
        except ValueError:
            pass
    return job


def clearance_stats():
    qs = BetaClearanceJob.objects.all()
    by_stage = _count_by(qs, "stage")
    return {
        "total": qs.count(),
        "by_stage": {code: by_stage.get(code, 0) for code, _ in BetaClearanceJob.STAGE_CHOICES},
        "stages": [{"value": c, "label": l} for c, l in BetaClearanceJob.STAGE_CHOICES],
        "final_stage": BetaClearanceJob.STAGE_RELEASED,
    }
