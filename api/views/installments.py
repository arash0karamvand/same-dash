"""CRUD اقساط و گزارش چک."""

from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_date as django_parse_date

from api.filters import parse_date
from api.helpers import api_view, fail, parse_json, success
from api.serializers import checks_report_to_dict, installment_to_dict
from auth.permissions import MANAGE_INSTALLMENTS, VIEW_INSTALLMENTS, has_permission
from backend.models import Sale, SaleInstallment
from logic.installments import checks_report, pay_installment
from logic.audit import log_action


def _get_installment(pk):
    try:
        return SaleInstallment.objects.select_related("sale", "sale__customer").get(pk=pk)
    except SaleInstallment.DoesNotExist:
        return None


@api_view("GET", "POST")
def installment_list(request):
    if request.method == "GET":
        if not has_permission(request.user, VIEW_INSTALLMENTS):
            return fail("Permission denied", status=403)
        qs = SaleInstallment.objects.select_related("sale", "sale__customer").all()
        sale_id = request.GET.get("sale")
        if sale_id:
            qs = qs.filter(sale_id=sale_id)
        payment_method = request.GET.get("payment_method")
        if payment_method:
            qs = qs.filter(payment_method=payment_method)
        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        year = request.GET.get("year")
        month = request.GET.get("month")
        if year and month:
            qs = qs.filter(due_date__year=int(year), due_date__month=int(month))
        date_from = parse_date(request.GET.get("date_from"))
        date_to = parse_date(request.GET.get("date_to"))
        if date_from:
            qs = qs.filter(due_date__gte=date_from)
        if date_to:
            qs = qs.filter(due_date__lte=date_to)
        return success({"results": [installment_to_dict(i) for i in qs]})

    if not has_permission(request.user, MANAGE_INSTALLMENTS):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    try:
        sale = Sale.objects.get(pk=data.get("sale_id"))
    except Sale.DoesNotExist:
        return fail("Sale not found", status=404)

    due = data.get("due_date")
    due_date = django_parse_date(due) if due else None
    if not due_date:
        return fail("due_date is required", status=400)

    try:
        amount = Decimal(str(data.get("amount")))
    except (InvalidOperation, TypeError):
        return fail("Invalid amount", status=400)

    inst = SaleInstallment.objects.create(
        sale=sale,
        amount=amount,
        due_date=due_date,
        payment_method=data.get("payment_method") or "cash",
        check_number=(data.get("check_number") or "").strip(),
        bank_name=(data.get("bank_name") or "").strip(),
        notes=(data.get("notes") or "").strip(),
    )
    log_action(
        request.user,
        "create",
        f"قسط جدید {int(amount)} — فروش #{sale.id}",
        entity_type="SaleInstallment",
        entity_id=inst.id,
    )
    return success(installment_to_dict(inst), status=201)


@api_view("GET", "PUT", "DELETE")
def installment_detail(request, pk):
    inst = _get_installment(pk)
    if inst is None:
        return fail("Installment not found", status=404)

    if request.method == "GET":
        if not has_permission(request.user, VIEW_INSTALLMENTS):
            return fail("Permission denied", status=403)
        return success(installment_to_dict(inst))

    if not has_permission(request.user, MANAGE_INSTALLMENTS):
        return fail("Permission denied", status=403)

    if request.method == "DELETE":
        if inst.status == "paid":
            return fail("Cannot delete paid installment", status=400)
        inst.soft_delete()
        log_action(
            request.user,
            "delete",
            f"حذف قسط #{inst.id}",
            entity_type="SaleInstallment",
            entity_id=inst.id,
        )
        return success({"deleted": True})

    data = parse_json(request)
    if inst.status == "paid":
        return fail("Cannot edit paid installment", status=400)
    for field in ("check_number", "bank_name", "notes", "payment_method"):
        if field in data:
            setattr(inst, field, (data.get(field) or "").strip())
    if "amount" in data:
        inst.amount = Decimal(str(data["amount"]))
    if "due_date" in data:
        due_date = django_parse_date(data["due_date"])
        if due_date:
            inst.due_date = due_date
    inst.save()
    log_action(
        request.user,
        "update",
        f"ویرایش قسط #{inst.id}",
        entity_type="SaleInstallment",
        entity_id=inst.id,
    )
    return success(installment_to_dict(inst))


@api_view("POST")
def installment_pay(request, pk):
    if not has_permission(request.user, MANAGE_INSTALLMENTS):
        return fail("Permission denied", status=403)
    inst = _get_installment(pk)
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
    return success(installment_to_dict(inst))


@api_view("GET")
def checks_monthly_report(request):
    if not has_permission(request.user, VIEW_INSTALLMENTS):
        return fail("Permission denied", status=403)
    from django.utils import timezone

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
