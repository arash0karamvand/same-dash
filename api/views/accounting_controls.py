import csv
from io import StringIO

from django.http import HttpResponse

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import APPROVE_ACCOUNTING, VIEW_ACCOUNTING
from backend.models import AccountingPeriod
from logic.accounting_controls import (
    close_period,
    discrepancy_scan,
    reconciliation_report,
    reopen_period,
)
from logic.accounting_management_reports import (
    journal_report,
    payable_aging,
    receivable_aging,
    vat_report,
)


@api_view("GET", permission=VIEW_ACCOUNTING)
def reconciliation(request):
    try:
        return success(reconciliation_report(
            request.GET.get("date_from"),
            request.GET.get("date_to"),
        ))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", permission=VIEW_ACCOUNTING)
def discrepancy_scan_view(request):
    try:
        return success(discrepancy_scan(request.GET))
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", permission=VIEW_ACCOUNTING)
def discrepancy_scan_export(request):
    try:
        report = discrepancy_scan(request.GET, paginate=False)
    except ValueError as exc:
        return fail(str(exc), status=400)

    output = StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "حوزه", "شدت", "نوع کنترل", "عنوان", "شرح", "تاریخ",
        "شماره سند/مرجع", "بدهکار", "بستانکار", "دفتر", "زیرسیستم",
        "اختلاف", "مسدودکننده",
    ])
    for item in report["items"]:
        amounts = item.get("amounts") or {}
        refs = item.get("refs") or {}
        reference = (
            refs.get("document_code")
            or refs.get("invoice_number")
            or refs.get("source_key")
            or refs.get("sale_id")
            or refs.get("supplier_id")
            or refs.get("material_id")
            or ""
        )
        writer.writerow([
            item.get("domain", ""),
            item.get("severity", ""),
            item.get("kind", ""),
            item.get("title", ""),
            item.get("message", ""),
            item.get("occurred_at", ""),
            reference,
            amounts.get("debit"),
            amounts.get("credit"),
            amounts.get("book"),
            amounts.get("subledger"),
            amounts.get("difference"),
            "بله" if item.get("blocking") else "خیر",
        ])
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="accounting-imbalance-report.csv"'
    return response


@api_view("POST", permission=APPROVE_ACCOUNTING)
def period_close(request):
    data = parse_json(request)
    try:
        return success(close_period(
            data.get("date_from"),
            data.get("date_to"),
            user=request.user,
            reason=data.get("reason") or "",
        ), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("POST", permission=APPROVE_ACCOUNTING)
def period_reopen(request, pk):
    data = parse_json(request)
    try:
        return success(reopen_period(
            pk,
            user=request.user,
            reason=data.get("reason") or "",
        ))
    except AccountingPeriod.DoesNotExist:
        return fail("دوره یافت نشد.", status=404)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", permission=VIEW_ACCOUNTING)
def management_report(request):
    kind = (request.GET.get("kind") or "journal").strip()
    if kind == "receivable-aging":
        return success(receivable_aging(request.GET.get("as_of")))
    if kind == "payable-aging":
        return success(payable_aging(request.GET.get("as_of")))
    if kind == "vat":
        return success(vat_report(
            request.GET.get("date_from") or "",
            request.GET.get("date_to") or "",
        ))
    if kind == "journal":
        return success(journal_report(
            request.GET.get("date_from") or "",
            request.GET.get("date_to") or "",
            request.GET.get("limit") or 1000,
        ))
    return fail("نوع گزارش معتبر نیست.", status=400)
