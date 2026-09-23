"""API endpoints برای فرم‌های اداری"""

from django.shortcuts import get_object_or_404

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import MANAGE_OFFICE_FORMS, VIEW_OFFICE_FORMS, has_permission
from backend.models import (
    AssistanceRequest,
    AttendanceConfirmation,
    PettyCashRequest,
    ProductionOrder,
    WarehouseTransfer,
)
from logic.audit import log_action
from logic.excel_export import (
    export_assistance_request_excel,
    export_attendance_confirmation_excel,
    export_petty_cash_excel,
    export_production_order_excel,
    export_warehouse_transfer_excel,
)
from logic.office_forms import (
    approve_assistance_request,
    pay_assistance_request,
    assistance_request_to_dict,
    attendance_confirmation_to_dict,
    create_assistance_request,
    create_attendance_confirmation,
    create_petty_cash_request,
    create_production_order,
    create_warehouse_transfer,
    list_assistance_requests,
    list_attendance_confirmations,
    list_petty_cash_requests,
    list_production_orders,
    list_warehouse_transfers,
    petty_cash_to_dict,
    process_petty_cash_request,
    production_order_to_dict,
    update_assistance_request,
    warehouse_transfer_to_dict,
)


# ========== Assistance Requests ==========


@api_view("GET", "POST", permission=VIEW_OFFICE_FORMS)
def assistance_requests(request):
    """لیست و ثبت درخواست مساعده"""
    if request.method == "GET":
        qs = list_assistance_requests(request.GET, request.user)
        from logic.pagination import paginate

        page, meta = paginate(qs, request.GET)
        results = [assistance_request_to_dict(obj) for obj in page]
        return success({"results": results, **meta})

    # POST
    data = parse_json(request)
    try:
        obj = create_assistance_request(data, request.user)
        return success({"assistance_request": assistance_request_to_dict(obj)}, status=201)
    except ValueError as e:
        return fail(str(e), status=400)


@api_view("GET", "PUT", permission=VIEW_OFFICE_FORMS)
def assistance_request_detail(request, pk):
    """جزئیات، ویرایش و تایید درخواست مساعده"""
    obj = get_object_or_404(AssistanceRequest, pk=pk)

    if request.method == "GET":
        return success(assistance_request_to_dict(obj))

    # PUT
    data = parse_json(request)
    action = data.get("action")

    try:
        if action == "approve":
            if not has_permission(request.user, MANAGE_OFFICE_FORMS):
                return fail("Permission denied", status=403)
            obj = approve_assistance_request(obj, request.user)
        elif action == "pay":
            if not has_permission(request.user, MANAGE_OFFICE_FORMS):
                return fail("Permission denied", status=403)
            obj = pay_assistance_request(obj, request.user)
        else:
            obj = update_assistance_request(obj, data, request.user)

        return success(assistance_request_to_dict(obj))
    except ValueError as e:
        return fail(str(e), status=400)


@api_view("GET", permission=VIEW_OFFICE_FORMS)
def assistance_request_export(request, pk):
    """خروجی اکسل درخواست مساعده"""
    obj = get_object_or_404(AssistanceRequest, pk=pk)
    return export_assistance_request_excel(obj)


# ========== Petty Cash Requests ==========


@api_view("GET", "POST", permission=VIEW_OFFICE_FORMS)
def petty_cash_requests(request):
    """لیست و ثبت درخواست تنخواه"""
    if request.method == "GET":
        qs = list_petty_cash_requests(request.GET, request.user)
        from logic.pagination import paginate

        page, meta = paginate(qs, request.GET)
        results = [petty_cash_to_dict(obj) for obj in page]
        return success({"results": results, **meta})

    # POST
    data = parse_json(request)
    try:
        obj = create_petty_cash_request(data, request.user)
        return success({"petty_cash": petty_cash_to_dict(obj)}, status=201)
    except ValueError as e:
        return fail(str(e), status=400)


@api_view("GET", "PUT", permission=VIEW_OFFICE_FORMS)
def petty_cash_detail(request, pk):
    """جزئیات درخواست تنخواه"""
    obj = get_object_or_404(PettyCashRequest, pk=pk)
    if request.method == "PUT":
        if not has_permission(request.user, MANAGE_OFFICE_FORMS):
            return fail("Permission denied", status=403)
        data = parse_json(request)
        try:
            obj = process_petty_cash_request(obj, data.get("action"), request.user, data)
        except ValueError as exc:
            return fail(str(exc), status=400)
    return success(petty_cash_to_dict(obj))


@api_view("GET", permission=VIEW_OFFICE_FORMS)
def petty_cash_export(request, pk):
    """خروجی اکسل تنخواه"""
    obj = get_object_or_404(PettyCashRequest, pk=pk)
    return export_petty_cash_excel(obj)


# ========== Warehouse Transfers ==========


@api_view("GET", "POST", permission=VIEW_OFFICE_FORMS)
def warehouse_transfers(request):
    """لیست و ثبت جابجایی انبار"""
    if request.method == "GET":
        qs = list_warehouse_transfers(request.GET, request.user)
        from logic.pagination import paginate

        page, meta = paginate(qs, request.GET)
        results = [warehouse_transfer_to_dict(obj) for obj in page]
        return success({"results": results, **meta})

    # POST
    data = parse_json(request)
    try:
        obj = create_warehouse_transfer(data, request.user)
        return success({"transfer": warehouse_transfer_to_dict(obj)}, status=201)
    except ValueError as e:
        return fail(str(e), status=400)


@api_view("GET", permission=VIEW_OFFICE_FORMS)
def warehouse_transfer_detail(request, pk):
    """جزئیات جابجایی انبار"""
    obj = get_object_or_404(WarehouseTransfer, pk=pk)
    return success(warehouse_transfer_to_dict(obj))


@api_view("GET", permission=VIEW_OFFICE_FORMS)
def warehouse_transfer_export(request, pk):
    """خروجی اکسل جابجایی انبار"""
    obj = get_object_or_404(WarehouseTransfer, pk=pk)
    return export_warehouse_transfer_excel(obj)


# ========== Production Orders ==========


@api_view("GET", "POST", permission=VIEW_OFFICE_FORMS)
def production_orders(request):
    """لیست و ثبت سفارش تولید"""
    if request.method == "GET":
        qs = list_production_orders(request.GET, request.user)
        from logic.pagination import paginate

        page, meta = paginate(qs, request.GET)
        results = [production_order_to_dict(obj) for obj in page]
        return success({"results": results, **meta})

    # POST
    data = parse_json(request)
    try:
        obj = create_production_order(data, request.user)
        return success({"production_order": production_order_to_dict(obj)}, status=201)
    except ValueError as e:
        return fail(str(e), status=400)


@api_view("GET", permission=VIEW_OFFICE_FORMS)
def production_order_detail(request, pk):
    """جزئیات سفارش تولید"""
    obj = get_object_or_404(ProductionOrder, pk=pk)
    return success(production_order_to_dict(obj))


@api_view("GET", permission=VIEW_OFFICE_FORMS)
def production_order_export(request, pk):
    """خروجی اکسل سفارش تولید"""
    obj = get_object_or_404(ProductionOrder, pk=pk)
    return export_production_order_excel(obj)


# ========== Attendance Confirmations ==========


@api_view("GET", "POST", permission=VIEW_OFFICE_FORMS)
def attendance_confirmations(request):
    """لیست و ثبت تاییدیه کارکرد"""
    if request.method == "GET":
        qs = list_attendance_confirmations(request.GET, request.user)
        from logic.pagination import paginate

        page, meta = paginate(qs, request.GET)
        results = [attendance_confirmation_to_dict(obj) for obj in page]
        return success({"results": results, **meta})

    # POST
    data = parse_json(request)
    try:
        obj = create_attendance_confirmation(data, request.user)
        return success({"attendance": attendance_confirmation_to_dict(obj)}, status=201)
    except ValueError as e:
        return fail(str(e), status=400)


@api_view("GET", permission=VIEW_OFFICE_FORMS)
def attendance_confirmation_detail(request, pk):
    """جزئیات تاییدیه کارکرد"""
    obj = get_object_or_404(AttendanceConfirmation, pk=pk)
    return success(attendance_confirmation_to_dict(obj))


@api_view("GET", permission=VIEW_OFFICE_FORMS)
def attendance_confirmation_export(request, pk):
    """خروجی اکسل تاییدیه کارکرد"""
    obj = get_object_or_404(AttendanceConfirmation, pk=pk)
    return export_attendance_confirmation_excel(obj)
