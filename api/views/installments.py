"""CRUD اقساط و گزارش چک."""

from django.http import HttpResponse
from django.utils import timezone

from api.filters import parse_date
from api.helpers import api_view, fail, parse_json, success
from api.serializers import checks_report_to_dict, installment_to_dict
from auth.permissions import MANAGE_INSTALLMENTS, VIEW_INSTALLMENTS, has_permission
from logic.audit import log_action
from logic.checks_excel_export import (
    checks_excel_bytes,
    checks_excel_filename,
    content_disposition_attachment,
)
from logic.installments import (
    checks_report,
    create_installment,
    delete_installment,
    get_installment,
    list_installments,
    pay_installment,
    update_installment,
)


@api_view("GET", "POST")
def installment_list(request):
    if request.method == "GET":
        if not has_permission(request.user, VIEW_INSTALLMENTS):
            return fail("Permission denied", status=403)
        qs = list_installments(request.GET, parse_date)
        return success({"results": [installment_to_dict(i, user=request.user) for i in qs]})

    if not has_permission(request.user, MANAGE_INSTALLMENTS):
        return fail("Permission denied", status=403)

    try:
        inst = create_installment(parse_json(request))
    except ValueError as exc:
        status = 404 if str(exc) == "Sale not found" else 400
        return fail(str(exc), status=status)

    log_action(
        request.user,
        "create",
        f"قسط جدید {int(inst.amount)} — فروش #{inst.sale_id}",
        entity_type="SaleInstallment",
        entity_id=inst.id,
    )
    return success(installment_to_dict(inst, user=request.user), status=201)


@api_view("GET", "PUT", "DELETE")
def installment_detail(request, pk):
    inst = get_installment(pk)
    if inst is None:
        return fail("Installment not found", status=404)

    if request.method == "GET":
        if not has_permission(request.user, VIEW_INSTALLMENTS):
            return fail("Permission denied", status=403)
        return success(installment_to_dict(inst, user=request.user))

    if not has_permission(request.user, MANAGE_INSTALLMENTS):
        return fail("Permission denied", status=403)

    if request.method == "DELETE":
        try:
            delete_installment(inst)
        except ValueError as exc:
            return fail(str(exc), status=400)
        log_action(
            request.user,
            "delete",
            f"حذف قسط #{inst.id}",
            entity_type="SaleInstallment",
            entity_id=inst.id,
        )
        return success({"deleted": True})

    try:
        update_installment(inst, parse_json(request))
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "update",
        f"ویرایش قسط #{inst.id}",
        entity_type="SaleInstallment",
        entity_id=inst.id,
    )
    return success(installment_to_dict(inst, user=request.user))


@api_view("POST")
def installment_pay(request, pk):
    if not has_permission(request.user, MANAGE_INSTALLMENTS):
        return fail("Permission denied", status=403)
    inst = get_installment(pk)
    if inst is None:
        return fail("Installment not found", status=404)
    try:
        inst = pay_installment(inst, recorded_by=request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "payment",
        f"پرداخت قسط #{inst.id} — {int(inst.amount)}",
        entity_type="SaleInstallment",
        entity_id=inst.id,
    )
    return success(installment_to_dict(inst, user=request.user))


@api_view("GET")
def checks_monthly_report(request):
    if not has_permission(request.user, VIEW_INSTALLMENTS):
        return fail("Permission denied", status=403)

    now = timezone.localdate()
    date_from = parse_date(request.GET.get("date_from"))
    date_to = parse_date(request.GET.get("date_to"))
    if date_from and date_to:
        report = checks_report(date_from=date_from, date_to=date_to)
    else:
        year = int(request.GET.get("year") or now.year)
        month = int(request.GET.get("month") or now.month)
        report = checks_report(year=year, month=month)
    return success(checks_report_to_dict(report))


@api_view("GET")
def installments_export_excel(request):
    if not has_permission(request.user, VIEW_INSTALLMENTS):
        return fail("Permission denied", status=403)

    try:
        from openpyxl import load_workbook  # noqa: F401
    except ImportError:
        return fail("openpyxl نصب نیست.", status=500)

    qs = list_installments(request.GET, parse_date).filter(payment_method="check")
    sale_id = request.GET.get("sale_id")
    if sale_id:
        qs = qs.filter(sale_id=sale_id)
    installments = list(qs.select_related("sale", "sale__customer", "sale__seller"))

    try:
        content = checks_excel_bytes(installments)
    except FileNotFoundError as exc:
        return fail(str(exc), status=500)

    filename = checks_excel_filename(f"checks_{sale_id}" if sale_id else "checks")
    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = content_disposition_attachment(filename)
    return response
