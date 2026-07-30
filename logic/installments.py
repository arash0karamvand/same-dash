"""منطق اقساط و چک."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date as django_parse_date

from backend.models import Sale, SaleInstallment
from logic.sales import normalize_payment_method, record_payment


def _parse_optional_date(value):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value
    return django_parse_date(str(value))


@transaction.atomic
def create_installments(sale, items):
    if len(items) > 16:
        raise ValueError("حداکثر ۱۶ چک مطابق فرم اکسل قابل ثبت است.")
    created = []
    for item in items:
        due_date = item["due_date"]
        if isinstance(due_date, str):
            due_date = django_parse_date(due_date)
        if not due_date:
            raise ValueError("تاریخ سررسید قسط نامعتبر است.")
        inst = SaleInstallment.objects.create(
            sale=sale,
            amount=Decimal(str(item["amount"])),
            due_date=due_date,
            payment_method=item.get("payment_method") or sale.payment_method,
            check_number=(item.get("check_number") or "").strip(),
            bank_name=(item.get("bank_name") or "").strip(),
            notes=(item.get("notes") or "").strip(),
            received_at=_parse_optional_date(item.get("received_at")),
            receiver_name=(item.get("receiver_name") or "").strip(),
        )
        created.append(inst)
    return created


@transaction.atomic
def pay_installment(installment, recorded_by=None):
    if installment.status == "paid":
        raise ValueError("این قسط قبلاً پرداخت شده است.")
    if installment.status == "cancelled":
        raise ValueError("قسط لغوشده قابل پرداخت نیست.")

    if (
        installment.payment_method == "check"
        and installment.accounting_registered_at
    ):
        from logic.check_accounting import clear_registered_check

        return clear_registered_check(installment, recorded_by=recorded_by)

    record_payment(
        installment.sale,
        installment.amount,
        description=f"پرداخت قسط سررسید {installment.due_date}",
        recorded_by=recorded_by,
    )
    installment.status = "paid"
    installment.paid_at = timezone.now()
    installment.save(update_fields=["status", "paid_at"])
    return installment


def checks_report(year=None, month=None, date_from=None, date_to=None):
    qs = SaleInstallment.objects.filter(payment_method="check").select_related("sale", "sale__customer")
    if date_from and date_to:
        qs = qs.filter(due_date__gte=date_from, due_date__lte=date_to)
    elif year and month:
        qs = qs.filter(due_date__year=year, due_date__month=month)
    else:
        qs = qs.none()

    results = list(qs)
    total = sum(i.amount for i in results)
    paid_total = sum(i.amount for i in results if i.status == "paid")

    return {
        "year": year,
        "month": month,
        "count": len(results),
        "total_amount": int(total),
        "paid_amount": int(paid_total),
        "pending_amount": int(total - paid_total),
        "results": results,
    }


def get_installment(pk):
    try:
        return SaleInstallment.objects.select_related(
            "sale",
            "sale__customer",
            "registration_account",
            "deposit_account",
        ).get(pk=pk)
    except SaleInstallment.DoesNotExist:
        return None


def apply_installment_filters(qs, params, parse_date_fn):
    sale_id = params.get("sale")
    if sale_id:
        qs = qs.filter(sale_id=sale_id)
    payment_method = params.get("payment_method")
    if payment_method:
        qs = qs.filter(payment_method=payment_method)
    status = params.get("status")
    if status:
        qs = qs.filter(status=status)
    year = params.get("year")
    month = params.get("month")
    if year and month:
        qs = qs.filter(due_date__year=int(year), due_date__month=int(month))
    date_from = parse_date_fn(params.get("date_from"))
    date_to = parse_date_fn(params.get("date_to"))
    if date_from:
        qs = qs.filter(due_date__gte=date_from)
    if date_to:
        qs = qs.filter(due_date__lte=date_to)
    return qs


def list_installments(params, parse_date_fn):
    qs = SaleInstallment.objects.select_related(
        "sale",
        "sale__customer",
        "registration_account",
        "deposit_account",
    ).all()
    return apply_installment_filters(qs, params, parse_date_fn)


def create_installment(data):
    try:
        sale = Sale.objects.get(pk=data.get("sale_id"))
    except Sale.DoesNotExist as exc:
        raise ValueError("Sale not found") from exc

    due = data.get("due_date")
    due_date = django_parse_date(due) if due else None
    if not due_date:
        raise ValueError("due_date is required")

    try:
        amount = Decimal(str(data.get("amount")))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid amount") from exc

    payment_method = normalize_payment_method(data.get("payment_method") or "check")
    return SaleInstallment.objects.create(
        sale=sale,
        amount=amount,
        due_date=due_date,
        payment_method=payment_method,
        check_number=(data.get("check_number") or "").strip(),
        bank_name=(data.get("bank_name") or "").strip(),
        notes=(data.get("notes") or "").strip(),
        received_at=_parse_optional_date(data.get("received_at")),
        receiver_name=(data.get("receiver_name") or "").strip(),
    )


def update_installment(inst, data):
    if inst.status == "paid":
        raise ValueError("Cannot edit paid installment")
    for field in ("check_number", "bank_name", "notes", "payment_method", "receiver_name"):
        if field in data:
            value = (data.get(field) or "").strip()
            if field == "payment_method":
                value = normalize_payment_method(value)
            setattr(inst, field, value)
    if "received_at" in data:
        inst.received_at = _parse_optional_date(data.get("received_at"))
    if "amount" in data:
        inst.amount = Decimal(str(data["amount"]))
    if "due_date" in data:
        due_date = django_parse_date(data["due_date"])
        if due_date:
            inst.due_date = due_date
    inst.save()
    return inst


def delete_installment(inst):
    if inst.status == "paid":
        raise ValueError("Cannot delete paid installment")
    inst.soft_delete()
    return inst
