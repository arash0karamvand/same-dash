"""API CRM — همان تب‌ها و پارامترهای فایل اکسل CRM 1405."""

from django.http import HttpResponse

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import APPROVE_SALE_ACCOUNTING
from logic.crm_workbook_schema import CRM_SHEETS
from logic.crm_workbook_service import (
    delete_row,
    export_all_rows,
    get_schema,
    import_workbook,
    list_sheet_rows,
    sync_customers_from_sales,
    upsert_row,
)


@api_view("GET", permission=APPROVE_SALE_ACCOUNTING)
def crm_workbook_schema(request):
    return success(get_schema())


@api_view("GET", permission=APPROVE_SALE_ACCOUNTING)
def crm_workbook_list(request, sheet):
    if sheet not in CRM_SHEETS:
        return fail("تب نامعتبر", status=404)
    try:
        limit = min(int(request.GET.get("limit") or 500), 2000)
        offset = max(int(request.GET.get("offset") or 0), 0)
    except (TypeError, ValueError):
        limit, offset = 500, 0
    search = request.GET.get("search") or ""
    return success(list_sheet_rows(sheet, search=search, limit=limit, offset=offset))


@api_view("POST", permission=APPROVE_SALE_ACCOUNTING)
def crm_workbook_upsert(request, sheet):
    if sheet not in CRM_SHEETS:
        return fail("تب نامعتبر", status=404)
    body = parse_json(request)
    data = body.get("data")
    if not isinstance(data, dict):
        return fail("data الزامی است", status=400)
    row_id = body.get("id")
    try:
        row = upsert_row(
            sheet=sheet,
            data=data,
            row_id=int(row_id) if row_id else None,
            user=request.user,
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success({"id": row.id, "invoice_ref": row.invoice_ref, "data": row.data})


@api_view("POST", permission=APPROVE_SALE_ACCOUNTING)
def crm_workbook_delete(request, row_id):
    body = parse_json(request)
    sheet = body.get("sheet")
    try:
        delete_row(int(row_id), sheet=sheet)
    except ValueError as exc:
        return fail(str(exc), status=404)
    return success({"deleted": True})


@api_view("POST", permission=APPROVE_SALE_ACCOUNTING)
def crm_workbook_import(request):
    upload = request.FILES.get("file")
    if not upload:
        return fail("فایل الزامی است", status=400)
    password = request.POST.get("password") or request.GET.get("password")
    replace = (request.POST.get("replace") or "true").lower() != "false"
    try:
        stats = import_workbook(upload, request.user, password=password, replace=replace)
    except ValueError as exc:
        return fail(str(exc), status=400)
    except Exception as exc:
        return fail(f"خطا در خواندن فایل: {exc}", status=400)
    return success({"message": "فایل CRM وارد شد", **stats})


@api_view("GET", permission=APPROVE_SALE_ACCOUNTING)
def crm_workbook_export(request):
    content = export_all_rows()
    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="CRM-export.xlsx"'
    return response


@api_view("POST", permission=APPROVE_SALE_ACCOUNTING)
def crm_workbook_sync_sales(request):
    body = parse_json(request)
    try:
        limit = min(int(body.get("limit") or 5000), 10000)
    except (TypeError, ValueError):
        limit = 5000
    stats = sync_customers_from_sales(request.user, limit=limit)
    return success({"message": "تب مشتریان از فاکتورهای سیستم به‌روز شد", **stats})
