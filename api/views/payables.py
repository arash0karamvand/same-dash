"""چرخه یکپارچه حساب‌های پرداختنی در دفتر قانونی."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import CREATE_ACCOUNTING, EDIT_ACCOUNTING, VIEW_ACCOUNTING, has_permission
from logic.accounts_payable import (
    clear_payable_check,
    create_supplier,
    issue_payable_check,
    list_checks,
    list_invoices,
    list_settlements,
    list_suppliers,
    overview,
    post_purchase_invoice,
    settle_invoices,
    void_payable_check,
)


@api_view("GET", permission=VIEW_ACCOUNTING)
def payable_overview(request):
    return success(overview(request.GET.get("as_of")))


@api_view("GET", "POST")
def suppliers(request):
    required = VIEW_ACCOUNTING if request.method == "GET" else CREATE_ACCOUNTING
    if not has_permission(request.user, required):
        return fail("Permission denied", status=403)
    if request.method == "GET":
        return success({"results": list_suppliers()})
    try:
        return success(create_supplier(parse_json(request), user=request.user), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "POST")
def invoices(request):
    required = VIEW_ACCOUNTING if request.method == "GET" else CREATE_ACCOUNTING
    if not has_permission(request.user, required):
        return fail("Permission denied", status=403)
    if request.method == "GET":
        return success({
            "results": list_invoices(
                request.GET.get("as_of"),
                open_only=request.GET.get("open_only") in {"1", "true", "True"},
            )
        })
    try:
        return success(post_purchase_invoice(parse_json(request), user=request.user), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", permission=VIEW_ACCOUNTING)
def settlements(request):
    return success({"results": list_settlements()})


@api_view("POST", permission=CREATE_ACCOUNTING)
def settle(request):
    try:
        return success(settle_invoices(parse_json(request), user=request.user), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("GET", "POST")
def checks(request):
    required = VIEW_ACCOUNTING if request.method == "GET" else CREATE_ACCOUNTING
    if not has_permission(request.user, required):
        return fail("Permission denied", status=403)
    if request.method == "GET":
        return success({"results": list_checks(request.GET.get("as_of"))})
    try:
        return success(issue_payable_check(parse_json(request), user=request.user), status=201)
    except ValueError as exc:
        return fail(str(exc), status=400)


@api_view("POST", permission=EDIT_ACCOUNTING)
def check_clear(request, pk):
    try:
        return success(clear_payable_check(pk, parse_json(request), user=request.user))
    except (ValueError, LookupError) as exc:
        return fail(str(exc), status=400)


@api_view("POST", permission=EDIT_ACCOUNTING)
def check_void(request, pk):
    try:
        return success(void_payable_check(pk, parse_json(request), user=request.user))
    except (ValueError, LookupError) as exc:
        return fail(str(exc), status=400)
