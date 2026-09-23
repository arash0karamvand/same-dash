"""مراکز هزینه، خزانه و گزارش مراکز درآمد."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import (
    APPROVE_ACCOUNTING,
    CREATE_ACCOUNTING,
    CREATE_FACTORY_ACCOUNTING,
    VIEW_ACCOUNTING,
    VIEW_FACTORY_ACCOUNTING,
    has_permission,
)
from logic.accounting_reports import profit_center_report
from logic.costing import (
    allocate_overhead,
    list_cost_centers,
    list_overhead_periods,
    list_wip_closes,
    save_cost_center,
    save_overhead_period,
    save_wip_close,
    post_abnormal_spoilage,
    spoilage_report,
)
from logic.customers import get_customer
from logic.ledger import LEGAL_LEDGER
from logic.treasury import allocate_deposit, check_plan_rows, create_deposit, list_deposits, pay_planned_check
from backend.models import CostCenter, OverheadPeriod, SaleInstallment, UnidentifiedDeposit


def _denied(user, permission):
    if not has_permission(user, permission):
        return fail("Permission denied", status=403)
    return None


def _denied_any(user, *permissions):
    if not any(has_permission(user, permission) for permission in permissions):
        return fail("Permission denied", status=403)
    return None


@api_view("GET", "POST")
def cost_centers(request):
    if request.method == "GET":
        denied = _denied_any(request.user, VIEW_ACCOUNTING, VIEW_FACTORY_ACCOUNTING)
        if denied:
            return denied
        return success({"results": list_cost_centers(ledger=LEGAL_LEDGER)})
    denied = _denied_any(request.user, CREATE_ACCOUNTING, CREATE_FACTORY_ACCOUNTING)
    if denied:
        return denied
    try:
        row = save_cost_center(parse_json(request), ledger=LEGAL_LEDGER)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(row, status=201)


@api_view("PUT", "DELETE")
def cost_center_detail(request, pk):
    denied = _denied_any(request.user, CREATE_ACCOUNTING, CREATE_FACTORY_ACCOUNTING)
    if denied:
        return denied
    try:
        center = CostCenter.objects.get(pk=pk, ledger__code=LEGAL_LEDGER.id)
    except CostCenter.DoesNotExist:
        return fail("مرکز هزینه یافت نشد.", status=404)
    if request.method == "DELETE":
        if center.journal_lines.exists() or center.allocation_lines.exists():
            center.is_active = False
            center.save(update_fields=["is_active"])
            return success({"id": center.id, "is_active": False})
        center.delete()
        return success({"deleted": True})
    try:
        row = save_cost_center(parse_json(request), center=center, ledger=LEGAL_LEDGER)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(row)


@api_view("GET", "POST")
def overhead_periods(request):
    if request.method == "GET":
        denied = _denied_any(request.user, VIEW_ACCOUNTING, VIEW_FACTORY_ACCOUNTING)
        if denied:
            return denied
        return success({"results": list_overhead_periods(ledger=LEGAL_LEDGER)})
    denied = _denied_any(request.user, CREATE_ACCOUNTING, CREATE_FACTORY_ACCOUNTING)
    if denied:
        return denied
    try:
        row = save_overhead_period(parse_json(request), ledger=LEGAL_LEDGER)
    except (ValueError, TypeError) as exc:
        return fail(str(exc), status=400)
    return success(row, status=201)


@api_view("POST")
def overhead_allocate(request, pk):
    denied = _denied_any(request.user, CREATE_ACCOUNTING, CREATE_FACTORY_ACCOUNTING)
    if denied:
        return denied
    try:
        row = allocate_overhead(pk, user=request.user, ledger=LEGAL_LEDGER)
    except OverheadPeriod.DoesNotExist:
        return fail("دوره سربار یافت نشد.", status=404)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(row)


@api_view("GET", "POST")
def wip_closes(request):
    if request.method == "GET":
        denied = _denied_any(request.user, VIEW_ACCOUNTING, VIEW_FACTORY_ACCOUNTING)
        if denied:
            return denied
        return success({"results": list_wip_closes(ledger=LEGAL_LEDGER)})
    denied = _denied_any(request.user, CREATE_ACCOUNTING, CREATE_FACTORY_ACCOUNTING)
    if denied:
        return denied
    try:
        row = save_wip_close(parse_json(request), ledger=LEGAL_LEDGER)
    except (ValueError, TypeError) as exc:
        return fail(str(exc), status=400)
    return success(row, status=201)


@api_view("GET", "POST")
def spoilage(request):
    required = (
        (CREATE_ACCOUNTING, CREATE_FACTORY_ACCOUNTING)
        if request.method == "POST"
        else (VIEW_ACCOUNTING, VIEW_FACTORY_ACCOUNTING)
    )
    denied = _denied_any(request.user, *required)
    if denied:
        return denied
    if request.method == "POST":
        try:
            return success(post_abnormal_spoilage(
                date_from=(request.GET.get("date_from") or "").strip(),
                date_to=(request.GET.get("date_to") or "").strip(),
                user=request.user,
                ledger=LEGAL_LEDGER,
            ))
        except ValueError as exc:
            return fail(str(exc), status=400)
    return success(spoilage_report(
        date_from=(request.GET.get("date_from") or "").strip(),
        date_to=(request.GET.get("date_to") or "").strip(),
    ))


@api_view("GET", permission=VIEW_ACCOUNTING)
def profit_centers(request):
    return success(profit_center_report())


@api_view("GET", "POST")
def deposits(request):
    if request.method == "GET":
        denied = _denied(request.user, VIEW_ACCOUNTING)
        if denied:
            return denied
        return success({"results": list_deposits()})
    denied = _denied(request.user, CREATE_ACCOUNTING)
    if denied:
        return denied
    try:
        row = create_deposit(parse_json(request), user=request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(row, status=201)


@api_view("POST")
def deposit_allocate(request, pk):
    denied = _denied(request.user, CREATE_ACCOUNTING)
    if denied:
        return denied
    data = parse_json(request)
    customer = get_customer(data.get("customer_id"))
    if not customer:
        return fail("مشتری یافت نشد.", status=404)
    try:
        row = allocate_deposit(pk, customer, user=request.user)
    except UnidentifiedDeposit.DoesNotExist:
        return fail("واریز یافت نشد.", status=404)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(row)


@api_view("GET", permission=VIEW_ACCOUNTING)
def check_plan(request):
    return success({"results": check_plan_rows()})


@api_view("POST", permission=APPROVE_ACCOUNTING)
def check_plan_pay(request, pk):
    data = parse_json(request)
    try:
        row = pay_planned_check(pk, data.get("deposit_account_id"), user=request.user)
    except SaleInstallment.DoesNotExist:
        return fail("چک یافت نشد.", status=404)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(row)
