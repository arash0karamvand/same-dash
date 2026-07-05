"""منطق اقساط و چک."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date as django_parse_date

from backend.models import SaleInstallment
from logic.sales import record_payment


@transaction.atomic
def create_installments(sale, items):
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
        )
        created.append(inst)
    return created


@transaction.atomic
def pay_installment(installment, recorded_by=None):
    if installment.status == "paid":
        raise ValueError("این قسط قبلاً پرداخت شده است.")
    if installment.status == "cancelled":
        raise ValueError("قسط لغوشده قابل پرداخت نیست.")

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
