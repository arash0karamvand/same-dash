"""API واحدهای کارگاهی بتا."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import (
    MANAGE_BETA_ASSEMBLY,
    MANAGE_BETA_CARPENTRY,
    MANAGE_BETA_CLEARANCE,
    MANAGE_BETA_CUSHION,
    MANAGE_BETA_FABRIC,
    MANAGE_BETA_FOAM,
    MANAGE_BETA_PAINT,
    MANAGE_BETA_QC,
    MANAGE_BETA_UPHOLSTERY,
    VIEW_BETA_ASSEMBLY,
    VIEW_BETA_CARPENTRY,
    VIEW_BETA_CLEARANCE,
    VIEW_BETA_CUSHION,
    VIEW_BETA_FABRIC,
    VIEW_BETA_FOAM,
    VIEW_BETA_PAINT,
    VIEW_BETA_QC,
    VIEW_BETA_UPHOLSTERY,
    has_permission,
)
from backend.models import (
    BetaAssemblyJob,
    BetaCarpentryAttendance,
    BetaCarpentryExternalService,
    BetaCarpentryFreight,
    BetaCarpentryOrder,
    BetaCarpentryTool,
    BetaCarpentryWoodPurchase,
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
)
from logic.audit import log_action
from logic import beta_carpentry_modules as CM
from logic import beta_workshops as L
from logic.pagination import paginate


def _can(user, view_perm, manage=False, manage_perm=None):
    if manage:
        return has_permission(user, manage_perm)
    return has_permission(user, view_perm) or has_permission(user, manage_perm)


def _denied():
    return fail("Permission denied", status=403)


def _get_or_404(model, pk, message):
    obj = model.objects.filter(pk=pk).first()
    if not obj:
        return None, fail(message, status=404)
    return obj, None


# --- نجاری ---

@api_view("GET")
def carpentry_stats(request):
    if not _can(request.user, VIEW_BETA_CARPENTRY, manage_perm=MANAGE_BETA_CARPENTRY):
        return _denied()
    return success(L.carpentry_stats(request.GET))


@api_view("GET")
def carpentry_sources(request):
    if not _can(request.user, VIEW_BETA_CARPENTRY, manage_perm=MANAGE_BETA_CARPENTRY):
        return _denied()
    limit_sales = request.GET.get("limit_sales") or 100
    limit_frames = request.GET.get("limit_frames") or 200
    return success(L.carpentry_sources(limit_sales=limit_sales, limit_frames=limit_frames))


@api_view("GET", "POST")
def carpentry_workshop_list(request):
    if not _can(request.user, VIEW_BETA_CARPENTRY, manage_perm=MANAGE_BETA_CARPENTRY):
        return _denied()
    if request.method == "GET":
        return success({"results": L.list_workshops()})
    if not has_permission(request.user, MANAGE_BETA_CARPENTRY):
        return _denied()
    try:
        workshop = L.create_workshop(parse_json(request))
        log_action(request.user, "create", f"واحد نجاری بتا: {workshop.name}")
        return success(L.workshop_to_dict(workshop), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("PUT", "DELETE")
def carpentry_workshop_detail(request, pk):
    if not has_permission(request.user, MANAGE_BETA_CARPENTRY):
        return _denied()
    workshop, err = _get_or_404(BetaCarpentryWorkshop, pk, "واحد نجاری یافت نشد.")
    if err:
        return err
    if request.method == "DELETE":
        try:
            L.delete_workshop(workshop)
        except ValueError as exc:
            return fail(str(exc), status=400)
        log_action(request.user, "delete", f"واحد نجاری بتا: {workshop.name}")
        return success({"id": pk})
    try:
        L.update_workshop(workshop, parse_json(request))
        log_action(request.user, "update", f"واحد نجاری بتا: {workshop.name}")
        return success(L.workshop_to_dict(workshop))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "POST")
def carpentry_order_list(request):
    if not _can(request.user, VIEW_BETA_CARPENTRY, manage_perm=MANAGE_BETA_CARPENTRY):
        return _denied()
    if request.method == "GET":
        qs = L.filter_carpentry_orders(BetaCarpentryOrder.objects.all(), request.GET)
        page, meta = paginate(qs, request.GET)
        return success({"results": [L.carpentry_order_to_dict(o) for o in page], **meta})
    if not has_permission(request.user, MANAGE_BETA_CARPENTRY):
        return _denied()
    try:
        order = L.create_carpentry_order(parse_json(request))
        log_action(request.user, "create", f"دستور نجاری بتا: {order.code}")
        return success(L.carpentry_order_to_dict(order), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def carpentry_order_detail(request, pk):
    if not _can(request.user, VIEW_BETA_CARPENTRY, manage_perm=MANAGE_BETA_CARPENTRY):
        return _denied()
    order, err = _get_or_404(BetaCarpentryOrder, pk, "دستور نجاری یافت نشد.")
    if err:
        return err
    if request.method == "GET":
        return success(L.carpentry_order_to_dict(order))
    if not has_permission(request.user, MANAGE_BETA_CARPENTRY):
        return _denied()
    if request.method == "DELETE":
        order.soft_delete()
        log_action(request.user, "delete", f"دستور نجاری بتا: {order.code}")
        return success({"id": pk})
    try:
        L.update_carpentry_order(order, parse_json(request))
        log_action(request.user, "update", f"دستور نجاری بتا: {order.code}")
        return success(L.carpentry_order_to_dict(order))
    except ValueError as exc:
        return fail(str(exc), status=400)


def _carpentry_resource_list(request, *, model, filter_fn, to_dict, create_fn, log_label):
    if not _can(request.user, VIEW_BETA_CARPENTRY, manage_perm=MANAGE_BETA_CARPENTRY):
        return _denied()
    if request.method == "GET":
        qs = filter_fn(model.objects.all(), request.GET)
        page, meta = paginate(qs, request.GET, default_limit=100)
        return success({"results": [to_dict(row) for row in page], **meta})
    if not has_permission(request.user, MANAGE_BETA_CARPENTRY):
        return _denied()
    try:
        item = create_fn(parse_json(request))
        log_action(request.user, "create", f"{log_label} بتا: {getattr(item, 'code', item.pk)}")
        return success(to_dict(item), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


def _carpentry_resource_detail(request, pk, *, model, to_dict, update_fn, log_label, not_found):
    if not _can(request.user, VIEW_BETA_CARPENTRY, manage_perm=MANAGE_BETA_CARPENTRY):
        return _denied()
    item, err = _get_or_404(model, pk, not_found)
    if err:
        return err
    if request.method == "GET":
        return success(to_dict(item))
    if not has_permission(request.user, MANAGE_BETA_CARPENTRY):
        return _denied()
    if request.method == "DELETE":
        item.soft_delete()
        log_action(request.user, "delete", f"{log_label} بتا: {getattr(item, 'code', item.pk)}")
        return success({"id": pk})
    try:
        update_fn(item, parse_json(request))
        log_action(request.user, "update", f"{log_label} بتا: {getattr(item, 'code', item.pk)}")
        return success(to_dict(item))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "POST")
def carpentry_tool_list(request):
    return _carpentry_resource_list(
        request,
        model=BetaCarpentryTool,
        filter_fn=CM.filter_tools,
        to_dict=CM.tool_to_dict,
        create_fn=CM.create_tool,
        log_label="ابزار نجاری",
    )


@api_view("GET", "PUT", "DELETE")
def carpentry_tool_detail(request, pk):
    return _carpentry_resource_detail(
        request,
        pk,
        model=BetaCarpentryTool,
        to_dict=CM.tool_to_dict,
        update_fn=CM.update_tool,
        log_label="ابزار نجاری",
        not_found="ابزار یافت نشد.",
    )


@api_view("GET", "POST")
def carpentry_wood_list(request):
    return _carpentry_resource_list(
        request,
        model=BetaCarpentryWoodPurchase,
        filter_fn=CM.filter_wood_purchases,
        to_dict=CM.wood_purchase_to_dict,
        create_fn=CM.create_wood_purchase,
        log_label="خرید چوب",
    )


@api_view("GET", "PUT", "DELETE")
def carpentry_wood_detail(request, pk):
    return _carpentry_resource_detail(
        request,
        pk,
        model=BetaCarpentryWoodPurchase,
        to_dict=CM.wood_purchase_to_dict,
        update_fn=CM.update_wood_purchase,
        log_label="خرید چوب",
        not_found="خرید چوب یافت نشد.",
    )


@api_view("GET", "POST")
def carpentry_service_list(request):
    return _carpentry_resource_list(
        request,
        model=BetaCarpentryExternalService,
        filter_fn=CM.filter_external_services,
        to_dict=CM.external_service_to_dict,
        create_fn=CM.create_external_service,
        log_label="خدمت برون‌سازمانی",
    )


@api_view("GET", "PUT", "DELETE")
def carpentry_service_detail(request, pk):
    return _carpentry_resource_detail(
        request,
        pk,
        model=BetaCarpentryExternalService,
        to_dict=CM.external_service_to_dict,
        update_fn=CM.update_external_service,
        log_label="خدمت برون‌سازمانی",
        not_found="خدمت یافت نشد.",
    )


@api_view("GET", "POST")
def carpentry_freight_list(request):
    return _carpentry_resource_list(
        request,
        model=BetaCarpentryFreight,
        filter_fn=CM.filter_freight,
        to_dict=CM.freight_to_dict,
        create_fn=CM.create_freight,
        log_label="باربری نجاری",
    )


@api_view("GET", "PUT", "DELETE")
def carpentry_freight_detail(request, pk):
    return _carpentry_resource_detail(
        request,
        pk,
        model=BetaCarpentryFreight,
        to_dict=CM.freight_to_dict,
        update_fn=CM.update_freight,
        log_label="باربری نجاری",
        not_found="رکورد باربری یافت نشد.",
    )


@api_view("GET", "POST")
def carpentry_attendance_list(request):
    return _carpentry_resource_list(
        request,
        model=BetaCarpentryAttendance,
        filter_fn=CM.filter_attendance,
        to_dict=CM.attendance_to_dict,
        create_fn=CM.create_attendance,
        log_label="تردد نجاری",
    )


@api_view("GET", "PUT", "DELETE")
def carpentry_attendance_detail(request, pk):
    return _carpentry_resource_detail(
        request,
        pk,
        model=BetaCarpentryAttendance,
        to_dict=CM.attendance_to_dict,
        update_fn=CM.update_attendance,
        log_label="تردد نجاری",
        not_found="رکورد تردد یافت نشد.",
    )


# --- رنگ ---

@api_view("GET")
def paint_stats(request):
    if not _can(request.user, VIEW_BETA_PAINT, manage_perm=MANAGE_BETA_PAINT):
        return _denied()
    return success(L.paint_stats())


@api_view("GET", "POST")
def paint_order_list(request):
    if not _can(request.user, VIEW_BETA_PAINT, manage_perm=MANAGE_BETA_PAINT):
        return _denied()
    if request.method == "GET":
        qs = L.filter_paint_orders(BetaPaintOrder.objects.all(), request.GET)
        page, meta = paginate(qs, request.GET, default_limit=100)
        return success({"results": [L.paint_order_to_dict(o) for o in page], **meta})
    if not has_permission(request.user, MANAGE_BETA_PAINT):
        return _denied()
    try:
        order = L.create_paint_order(parse_json(request))
        log_action(request.user, "create", f"سفارش رنگ بتا: {order.code}")
        return success(L.paint_order_to_dict(order), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def paint_order_detail(request, pk):
    if not _can(request.user, VIEW_BETA_PAINT, manage_perm=MANAGE_BETA_PAINT):
        return _denied()
    order, err = _get_or_404(BetaPaintOrder, pk, "سفارش رنگ یافت نشد.")
    if err:
        return err
    if request.method == "GET":
        return success(L.paint_order_to_dict(order))
    if not has_permission(request.user, MANAGE_BETA_PAINT):
        return _denied()
    if request.method == "DELETE":
        order.soft_delete()
        log_action(request.user, "delete", f"سفارش رنگ بتا: {order.code}")
        return success({"id": pk})
    try:
        L.update_paint_order(order, parse_json(request))
        log_action(request.user, "update", f"سفارش رنگ بتا: {order.code}")
        return success(L.paint_order_to_dict(order))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("POST")
def paint_order_advance(request, pk):
    if not has_permission(request.user, MANAGE_BETA_PAINT):
        return _denied()
    order, err = _get_or_404(BetaPaintOrder, pk, "سفارش رنگ یافت نشد.")
    if err:
        return err
    try:
        L.advance_paint_order(order, parse_json(request).get("note") or "")
        log_action(request.user, "update", f"ارتقای مرحله رنگ بتا: {order.code}")
        return success(L.paint_order_to_dict(order))
    except ValueError as exc:
        return fail(str(exc), status=400)


# --- رویه‌کوبی ---

@api_view("GET")
def upholstery_stats(request):
    if not _can(request.user, VIEW_BETA_UPHOLSTERY, manage_perm=MANAGE_BETA_UPHOLSTERY):
        return _denied()
    return success(L.upholstery_stats(request.GET))


@api_view("GET", "POST")
def upholstery_job_list(request):
    if not _can(request.user, VIEW_BETA_UPHOLSTERY, manage_perm=MANAGE_BETA_UPHOLSTERY):
        return _denied()
    if request.method == "GET":
        qs = L.filter_upholstery_jobs(BetaUpholsteryJob.objects.all(), request.GET)
        page, meta = paginate(qs, request.GET, default_limit=50)
        return success({"results": [L.upholstery_job_to_dict(j) for j in page], **meta})
    if not has_permission(request.user, MANAGE_BETA_UPHOLSTERY):
        return _denied()
    try:
        job = L.create_upholstery_job(parse_json(request))
        log_action(request.user, "create", f"کار رویه‌کوبی بتا: {job.code}")
        return success(L.upholstery_job_to_dict(job), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def upholstery_job_detail(request, pk):
    if not _can(request.user, VIEW_BETA_UPHOLSTERY, manage_perm=MANAGE_BETA_UPHOLSTERY):
        return _denied()
    job, err = _get_or_404(BetaUpholsteryJob, pk, "کار رویه‌کوبی یافت نشد.")
    if err:
        return err
    if request.method == "GET":
        return success(L.upholstery_job_to_dict(job))
    if not has_permission(request.user, MANAGE_BETA_UPHOLSTERY):
        return _denied()
    if request.method == "DELETE":
        job.soft_delete()
        log_action(request.user, "delete", f"کار رویه‌کوبی بتا: {job.code}")
        return success({"id": pk})
    try:
        L.update_upholstery_job(job, parse_json(request))
        log_action(request.user, "update", f"کار رویه‌کوبی بتا: {job.code}")
        return success(L.upholstery_job_to_dict(job))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("POST")
def upholstery_job_advance(request, pk):
    if not has_permission(request.user, MANAGE_BETA_UPHOLSTERY):
        return _denied()
    job, err = _get_or_404(BetaUpholsteryJob, pk, "کار رویه‌کوبی یافت نشد.")
    if err:
        return err
    L.advance_upholstery_job(job)
    log_action(request.user, "update", f"ارتقای مرحله رویه‌کوبی بتا: {job.code}")
    return success(L.upholstery_job_to_dict(job))


# --- پارچه ---

@api_view("GET")
def fabric_stats(request):
    if not _can(request.user, VIEW_BETA_FABRIC, manage_perm=MANAGE_BETA_FABRIC):
        return _denied()
    return success(L.fabric_stats())


@api_view("GET", "POST")
def fabric_roll_list(request):
    if not _can(request.user, VIEW_BETA_FABRIC, manage_perm=MANAGE_BETA_FABRIC):
        return _denied()
    if request.method == "GET":
        qs = L.filter_fabric_rolls(BetaFabricRoll.objects.all(), request.GET)
        page, meta = paginate(qs, request.GET, default_limit=50)
        return success({"results": [L.fabric_roll_to_dict(r) for r in page], **meta})
    if not has_permission(request.user, MANAGE_BETA_FABRIC):
        return _denied()
    try:
        roll = L.create_fabric_roll(parse_json(request))
        log_action(request.user, "create", f"طاقه پارچه بتا: {roll.code}")
        return success(L.fabric_roll_to_dict(roll), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def fabric_roll_detail(request, pk):
    if not _can(request.user, VIEW_BETA_FABRIC, manage_perm=MANAGE_BETA_FABRIC):
        return _denied()
    roll, err = _get_or_404(BetaFabricRoll, pk, "طاقه پارچه یافت نشد.")
    if err:
        return err
    if request.method == "GET":
        return success(L.fabric_roll_to_dict(roll))
    if not has_permission(request.user, MANAGE_BETA_FABRIC):
        return _denied()
    if request.method == "DELETE":
        if roll.dispatches.exists():
            return fail("این طاقه حواله خروج دارد و قابل حذف نیست.", status=400)
        roll.soft_delete()
        log_action(request.user, "delete", f"طاقه پارچه بتا: {roll.code}")
        return success({"id": pk})
    try:
        L.update_fabric_roll(roll, parse_json(request))
        log_action(request.user, "update", f"طاقه پارچه بتا: {roll.code}")
        return success(L.fabric_roll_to_dict(roll))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "POST")
def fabric_dispatch_list(request):
    if not _can(request.user, VIEW_BETA_FABRIC, manage_perm=MANAGE_BETA_FABRIC):
        return _denied()
    if request.method == "GET":
        qs = BetaFabricDispatch.objects.select_related("roll").all()
        page, meta = paginate(qs, request.GET, default_limit=50)
        return success({"results": [L.fabric_dispatch_to_dict(d) for d in page], **meta})
    if not has_permission(request.user, MANAGE_BETA_FABRIC):
        return _denied()
    try:
        dispatch = L.create_fabric_dispatch(parse_json(request))
        log_action(request.user, "create", f"حواله پارچه بتا: {dispatch.code}")
        return success(L.fabric_dispatch_to_dict(dispatch), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


# --- کنترل کیفیت ---

@api_view("GET")
def qc_stats(request):
    if not _can(request.user, VIEW_BETA_QC, manage_perm=MANAGE_BETA_QC):
        return _denied()
    return success(L.qc_stats(request.GET))


@api_view("GET", "POST")
def qc_inspection_list(request):
    if not _can(request.user, VIEW_BETA_QC, manage_perm=MANAGE_BETA_QC):
        return _denied()
    if request.method == "GET":
        qs = L.filter_qc_inspections(BetaQcInspection.objects.all(), request.GET)
        page, meta = paginate(qs, request.GET, default_limit=50)
        return success({"results": [L.qc_inspection_to_dict(i) for i in page], **meta})
    if not has_permission(request.user, MANAGE_BETA_QC):
        return _denied()
    try:
        item = L.create_qc_inspection(parse_json(request))
        log_action(request.user, "create", f"بازرسی QC بتا: {item.code}")
        return success(L.qc_inspection_to_dict(item), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def qc_inspection_detail(request, pk):
    if not _can(request.user, VIEW_BETA_QC, manage_perm=MANAGE_BETA_QC):
        return _denied()
    item, err = _get_or_404(BetaQcInspection, pk, "بازرسی یافت نشد.")
    if err:
        return err
    if request.method == "GET":
        return success(L.qc_inspection_to_dict(item))
    if not has_permission(request.user, MANAGE_BETA_QC):
        return _denied()
    if request.method == "DELETE":
        item.soft_delete()
        log_action(request.user, "delete", f"بازرسی QC بتا: {item.code}")
        return success({"id": pk})
    try:
        L.update_qc_inspection(item, parse_json(request))
        log_action(request.user, "update", f"بازرسی QC بتا: {item.code}")
        return success(L.qc_inspection_to_dict(item))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("POST")
def qc_inspection_evaluate(request, pk):
    if not has_permission(request.user, MANAGE_BETA_QC):
        return _denied()
    item, err = _get_or_404(BetaQcInspection, pk, "بازرسی یافت نشد.")
    if err:
        return err
    try:
        L.evaluate_qc_inspection(item, parse_json(request))
        log_action(request.user, "update", f"ارزیابی QC بتا: {item.code}")
        return success(L.qc_inspection_to_dict(item))
    except ValueError as exc:
        return fail(str(exc), status=400)


# --- فوم ---

@api_view("GET")
def foam_stats(request):
    if not _can(request.user, VIEW_BETA_FOAM, manage_perm=MANAGE_BETA_FOAM):
        return _denied()
    return success(L.foam_stats())


@api_view("GET", "POST")
def foam_job_list(request):
    if not _can(request.user, VIEW_BETA_FOAM, manage_perm=MANAGE_BETA_FOAM):
        return _denied()
    if request.method == "GET":
        qs = L.filter_foam_jobs(BetaFoamJob.objects.all(), request.GET)
        page, meta = paginate(qs, request.GET, default_limit=100)
        return success({"results": [L.foam_job_to_dict(j) for j in page], **meta})
    if not has_permission(request.user, MANAGE_BETA_FOAM):
        return _denied()
    try:
        job = L.create_foam_job(parse_json(request))
        log_action(request.user, "create", f"کار فوم بتا: {job.code}")
        return success(L.foam_job_to_dict(job), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def foam_job_detail(request, pk):
    if not _can(request.user, VIEW_BETA_FOAM, manage_perm=MANAGE_BETA_FOAM):
        return _denied()
    job, err = _get_or_404(BetaFoamJob, pk, "کار فوم یافت نشد.")
    if err:
        return err
    if request.method == "GET":
        return success(L.foam_job_to_dict(job))
    if not has_permission(request.user, MANAGE_BETA_FOAM):
        return _denied()
    if request.method == "DELETE":
        job.soft_delete()
        log_action(request.user, "delete", f"کار فوم بتا: {job.code}")
        return success({"id": pk})
    try:
        L.update_foam_job(job, parse_json(request))
        log_action(request.user, "update", f"کار فوم بتا: {job.code}")
        return success(L.foam_job_to_dict(job))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("POST")
def foam_job_advance(request, pk):
    if not has_permission(request.user, MANAGE_BETA_FOAM):
        return _denied()
    job, err = _get_or_404(BetaFoamJob, pk, "کار فوم یافت نشد.")
    if err:
        return err
    L.advance_foam_job(job)
    log_action(request.user, "update", f"ارتقای مرحله فوم بتا: {job.code}")
    return success(L.foam_job_to_dict(job))


# --- کوسن ---

@api_view("GET")
def cushion_stats(request):
    if not _can(request.user, VIEW_BETA_CUSHION, manage_perm=MANAGE_BETA_CUSHION):
        return _denied()
    return success(L.cushion_stats())


@api_view("GET", "POST")
def cushion_job_list(request):
    if not _can(request.user, VIEW_BETA_CUSHION, manage_perm=MANAGE_BETA_CUSHION):
        return _denied()
    if request.method == "GET":
        qs = L.filter_cushion_jobs(BetaCushionJob.objects.all(), request.GET)
        page, meta = paginate(qs, request.GET, default_limit=100)
        return success({"results": [L.cushion_job_to_dict(j) for j in page], **meta})
    if not has_permission(request.user, MANAGE_BETA_CUSHION):
        return _denied()
    try:
        job = L.create_cushion_job(parse_json(request))
        log_action(request.user, "create", f"کار کوسن بتا: {job.code}")
        return success(L.cushion_job_to_dict(job), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def cushion_job_detail(request, pk):
    if not _can(request.user, VIEW_BETA_CUSHION, manage_perm=MANAGE_BETA_CUSHION):
        return _denied()
    job, err = _get_or_404(BetaCushionJob, pk, "کار کوسن یافت نشد.")
    if err:
        return err
    if request.method == "GET":
        return success(L.cushion_job_to_dict(job))
    if not has_permission(request.user, MANAGE_BETA_CUSHION):
        return _denied()
    if request.method == "DELETE":
        job.soft_delete()
        log_action(request.user, "delete", f"کار کوسن بتا: {job.code}")
        return success({"id": pk})
    try:
        L.update_cushion_job(job, parse_json(request))
        log_action(request.user, "update", f"کار کوسن بتا: {job.code}")
        return success(L.cushion_job_to_dict(job))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("POST")
def cushion_job_advance(request, pk):
    if not has_permission(request.user, MANAGE_BETA_CUSHION):
        return _denied()
    job, err = _get_or_404(BetaCushionJob, pk, "کار کوسن یافت نشد.")
    if err:
        return err
    L.advance_cushion_job(job)
    log_action(request.user, "update", f"ارتقای مرحله کوسن بتا: {job.code}")
    return success(L.cushion_job_to_dict(job))


# --- نیاز پارچه خط تولید ---

@api_view("GET", "POST")
def fabric_need_list(request):
    if not _can(request.user, VIEW_BETA_FABRIC, manage_perm=MANAGE_BETA_FABRIC):
        return _denied()
    if request.method == "GET":
        qs = L.filter_fabric_needs(BetaFabricNeed.objects.all(), request.GET)
        page, meta = paginate(qs, request.GET, default_limit=100)
        return success({"results": [L.fabric_need_to_dict(n) for n in page], **meta})
    if not has_permission(request.user, MANAGE_BETA_FABRIC):
        return _denied()
    try:
        need = L.create_fabric_need(parse_json(request))
        log_action(request.user, "create", f"نیاز پارچه بتا: {need.code}")
        return success(L.fabric_need_to_dict(need), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def fabric_need_detail(request, pk):
    if not _can(request.user, VIEW_BETA_FABRIC, manage_perm=MANAGE_BETA_FABRIC):
        return _denied()
    need, err = _get_or_404(BetaFabricNeed, pk, "نیاز پارچه یافت نشد.")
    if err:
        return err
    if request.method == "GET":
        return success(L.fabric_need_to_dict(need))
    if not has_permission(request.user, MANAGE_BETA_FABRIC):
        return _denied()
    if request.method == "DELETE":
        need.soft_delete()
        log_action(request.user, "delete", f"نیاز پارچه بتا: {need.code}")
        return success({"id": pk})
    try:
        L.update_fabric_need(need, parse_json(request))
        log_action(request.user, "update", f"نیاز پارچه بتا: {need.code}")
        return success(L.fabric_need_to_dict(need))
    except ValueError as exc:
        return fail(str(exc), status=400)


# --- مونتاژ ---

@api_view("GET")
def assembly_stats(request):
    if not _can(request.user, VIEW_BETA_ASSEMBLY, manage_perm=MANAGE_BETA_ASSEMBLY):
        return _denied()
    return success(L.assembly_stats())


@api_view("GET", "POST")
def assembly_job_list(request):
    if not _can(request.user, VIEW_BETA_ASSEMBLY, manage_perm=MANAGE_BETA_ASSEMBLY):
        return _denied()
    if request.method == "GET":
        qs = L.filter_assembly_jobs(BetaAssemblyJob.objects.all(), request.GET)
        page, meta = paginate(qs, request.GET, default_limit=100)
        return success({"results": [L.assembly_job_to_dict(j) for j in page], **meta})
    if not has_permission(request.user, MANAGE_BETA_ASSEMBLY):
        return _denied()
    try:
        job = L.create_assembly_job(parse_json(request))
        log_action(request.user, "create", f"کار مونتاژ بتا: {job.code}")
        return success(L.assembly_job_to_dict(job), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def assembly_job_detail(request, pk):
    if not _can(request.user, VIEW_BETA_ASSEMBLY, manage_perm=MANAGE_BETA_ASSEMBLY):
        return _denied()
    job, err = _get_or_404(BetaAssemblyJob, pk, "کار مونتاژ یافت نشد.")
    if err:
        return err
    if request.method == "GET":
        return success(L.assembly_job_to_dict(job))
    if not has_permission(request.user, MANAGE_BETA_ASSEMBLY):
        return _denied()
    if request.method == "DELETE":
        job.soft_delete()
        log_action(request.user, "delete", f"کار مونتاژ بتا: {job.code}")
        return success({"id": pk})
    try:
        L.update_assembly_job(job, parse_json(request))
        log_action(request.user, "update", f"کار مونتاژ بتا: {job.code}")
        return success(L.assembly_job_to_dict(job))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("POST")
def assembly_job_advance(request, pk):
    if not has_permission(request.user, MANAGE_BETA_ASSEMBLY):
        return _denied()
    job, err = _get_or_404(BetaAssemblyJob, pk, "کار مونتاژ یافت نشد.")
    if err:
        return err
    L.advance_assembly_job(job)
    log_action(request.user, "update", f"ارتقای مرحله مونتاژ بتا: {job.code}")
    return success(L.assembly_job_to_dict(job))


# --- ترخیص ---

@api_view("GET")
def clearance_stats(request):
    if not _can(request.user, VIEW_BETA_CLEARANCE, manage_perm=MANAGE_BETA_CLEARANCE):
        return _denied()
    return success(L.clearance_stats())


@api_view("GET", "POST")
def clearance_job_list(request):
    if not _can(request.user, VIEW_BETA_CLEARANCE, manage_perm=MANAGE_BETA_CLEARANCE):
        return _denied()
    if request.method == "GET":
        qs = L.filter_clearance_jobs(BetaClearanceJob.objects.all(), request.GET)
        page, meta = paginate(qs, request.GET, default_limit=100)
        return success({"results": [L.clearance_job_to_dict(j) for j in page], **meta})
    if not has_permission(request.user, MANAGE_BETA_CLEARANCE):
        return _denied()
    try:
        job = L.create_clearance_job(parse_json(request))
        log_action(request.user, "create", f"کار ترخیص بتا: {job.code}")
        return success(L.clearance_job_to_dict(job), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "PUT", "DELETE")
def clearance_job_detail(request, pk):
    if not _can(request.user, VIEW_BETA_CLEARANCE, manage_perm=MANAGE_BETA_CLEARANCE):
        return _denied()
    job, err = _get_or_404(BetaClearanceJob, pk, "کار ترخیص یافت نشد.")
    if err:
        return err
    if request.method == "GET":
        return success(L.clearance_job_to_dict(job))
    if not has_permission(request.user, MANAGE_BETA_CLEARANCE):
        return _denied()
    if request.method == "DELETE":
        job.soft_delete()
        log_action(request.user, "delete", f"کار ترخیص بتا: {job.code}")
        return success({"id": pk})
    try:
        L.update_clearance_job(job, parse_json(request))
        log_action(request.user, "update", f"کار ترخیص بتا: {job.code}")
        return success(L.clearance_job_to_dict(job))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("POST")
def clearance_job_advance(request, pk):
    if not has_permission(request.user, MANAGE_BETA_CLEARANCE):
        return _denied()
    job, err = _get_or_404(BetaClearanceJob, pk, "کار ترخیص یافت نشد.")
    if err:
        return err
    L.advance_clearance_job(job)
    log_action(request.user, "update", f"ارتقای مرحله ترخیص بتا: {job.code}")
    return success(L.clearance_job_to_dict(job))
