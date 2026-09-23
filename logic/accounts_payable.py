"""حساب‌های پرداختنی کارخانه در برابر تامین‌کنندگان مواد اولیه.

ورود کالا به انبار:
    بدهکار موجودی مواد اولیه (بهای پس از تخفیف تجاری + حمل + بیمه + سایر مخارج)
    بدهکار مالیات ارزش افزوده خرید
    بستانکار حساب معین تامین‌کننده

صدور چک پرداختی، فاکتور را تسویه می‌کند و بدهی را به اسناد پرداختنی منتقل می‌کند:
    بدهکار تامین‌کننده
    بستانکار اسناد پرداختنی تامین‌کنندگان

پاس شدن چک در سررسید:
    بدهکار اسناد پرداختنی تامین‌کنندگان
    بستانکار بانک

تسویه نقدی همان بدهکار تامین‌کننده است، با بستانکار بانک یا صندوق.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction
from django.db.models import F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from backend.models import (
    Account,
    JournalLine,
    Material,
    MaterialSupplier,
    PayableAllocation,
    PayableCheck,
    PayableSettlement,
    PurchaseInvoice,
    PurchaseInvoiceLine,
)
from logic.accounting import create_journal
from logic.accounting_accounts import get_account
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.giant_books.money import money_int, rial
from logic.inventory_costing import receive_stock
from logic.ledger import LEGAL_LEDGER
from logic.trade_books import DEFAULT_VAT_RATE, purchase_amounts
from logic.vat_engine import parse_rate

NOTES_SLUG = "supplier-notes-payable"
NOTES_CODE = "SPNOTES"
BUCKET_LABELS = {
    "overdue": "سررسید گذشته",
    "due_7": "تا ۷ روز",
    "due_30": "تا ۳۰ روز",
    "later": "بعد از ۳۰ روز",
    "closed": "تسویه",
}


def _money(value):
    try:
        return money_int(rial(value))
    except Exception as exc:
        raise ValueError("مبلغ نامعتبر است.") from exc


def _date(value, label):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} الزامی است.")
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"{label} نامعتبر است.") from exc


def _as_of(value):
    if value in (None, ""):
        return date.today()
    return _date(value, "تاریخ گزارش")


def _pk(value, label):
    try:
        pk = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} نامعتبر است.") from exc
    if pk <= 0:
        raise ValueError(f"{label} نامعتبر است.")
    return pk


def _actor(user):
    if getattr(user, "is_authenticated", False):
        return user
    return None


def _noon(day):
    moment = datetime.combine(day, time(12, 0))
    if timezone.is_naive(moment):
        return timezone.make_aware(moment)
    return moment


def _portion(total, take, remaining):
    total = _money(total)
    if take == remaining:
        return total
    if remaining == 0:
        return 0
    return int((Decimal(total) * Decimal(take) / Decimal(remaining)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _remaining(invoice):
    return _money(invoice.payable_amount) - _money(invoice.settled_amount)


def _bucket(due, as_of, remaining):
    if remaining <= 0:
        return "closed"
    days = (due - as_of).days
    if days < 0:
        return "overdue"
    if days <= 7:
        return "due_7"
    if days <= 30:
        return "due_30"
    return "later"


def _controls():
    return {
        "inventory": get_account(ACCOUNT_SLUGS.RAW_MATERIALS_INVENTORY, ledger=LEGAL_LEDGER),
        "vat": get_account(ACCOUNT_SLUGS.VAT_RECEIVABLE, ledger=LEGAL_LEDGER),
        "payable": get_account(ACCOUNT_SLUGS.ACCOUNTS_PAYABLE, ledger=LEGAL_LEDGER),
        "bank": get_account(ACCOUNT_SLUGS.BANK, ledger=LEGAL_LEDGER),
        "cash": get_account(ACCOUNT_SLUGS.CASH_DOCUMENTS, ledger=LEGAL_LEDGER),
    }


def notes_account():
    """حساب معین اسناد پرداختنی تامین‌کنندگان، زیر حساب‌های پرداختنی کارخانه."""
    parent = _controls()["payable"]
    account, _created = Account.objects.get_or_create(
        ledger=parent.ledger,
        slug=NOTES_SLUG,
        defaults={
            "parent": parent,
            "code": NOTES_CODE,
            "name": "اسناد پرداختنی تامین‌کنندگان",
            "account_class": parent.account_class,
            "normal_balance": parent.normal_balance,
            "sort_order": 1,
            "is_active": True,
        },
    )
    return account


def _next_supplier_code():
    numbers = []
    for code in MaterialSupplier.objects.values_list("code", flat=True):
        if code.startswith("SP") and code[2:].isdigit():
            numbers.append(int(code[2:]))
    return f"SP{(max(numbers) if numbers else 0) + 1:04d}"


def _lines(pairs):
    rows = []
    for account, debit, credit, text in pairs:
        if debit == 0 and credit == 0:
            continue
        rows.append({"account": account, "debit": debit, "credit": credit, "description": text})
    return rows


def supplier_to_dict(supplier, open_balance=None):
    if open_balance is None:
        open_balance = _money(getattr(supplier, "open_balance", 0) or 0)
    account = supplier.account
    return {
        "id": supplier.id,
        "code": supplier.code,
        "name": supplier.name,
        "phone": supplier.phone,
        "national_id": supplier.national_id,
        "address": supplier.address,
        "credit_days": supplier.credit_days,
        "is_active": supplier.is_active,
        "account_id": account.id,
        "account_code": account.full_code,
        "account_name": account.name,
        "open_balance": open_balance,
    }


def invoice_to_dict(invoice, as_of=None):
    day = as_of or date.today()
    remaining = _remaining(invoice)
    bucket = _bucket(invoice.due_date, day, remaining)
    names = [line.material.name for line in invoice.lines.all()]
    return {
        "id": invoice.id,
        "supplier_id": invoice.supplier_id,
        "supplier_name": invoice.supplier.name,
        "invoice_number": invoice.invoice_number,
        "warehouse_receipt": invoice.warehouse_receipt,
        "invoice_date": invoice.invoice_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "days_to_due": (invoice.due_date - day).days,
        "bucket": bucket,
        "bucket_label": BUCKET_LABELS[bucket],
        "status": invoice.status,
        "status_label": invoice.get_status_display(),
        "goods_net": _money(invoice.goods_net),
        "charges": _money(invoice.charges),
        "inventory_amount": _money(invoice.inventory_amount),
        "vat_rate": str(invoice.vat_rate),
        "vat_amount": _money(invoice.vat_amount),
        "payable_amount": _money(invoice.payable_amount),
        "settled_amount": _money(invoice.settled_amount),
        "remaining": remaining,
        "materials": "، ".join(names),
        "description": invoice.description,
        "document_code": invoice.journal.document_code if invoice.journal_id else "",
    }


def check_to_dict(row, as_of=None):
    day = as_of or date.today()
    remaining = _money(row.amount) if row.status == PayableCheck.STATUS_ISSUED else 0
    bucket = _bucket(row.due_date, day, remaining)
    return {
        "id": row.id,
        "supplier_id": row.supplier_id,
        "supplier_name": row.supplier.name,
        "check_number": row.check_number,
        "bank_name": row.bank_name,
        "amount": _money(row.amount),
        "issue_date": row.issue_date.isoformat(),
        "due_date": row.due_date.isoformat(),
        "days_to_due": (row.due_date - day).days,
        "bucket": bucket,
        "bucket_label": BUCKET_LABELS[bucket],
        "status": row.status,
        "status_label": row.get_status_display(),
        "cleared_on": row.cleared_on.isoformat() if row.cleared_on else "",
        "document_code": row.settlement.journal.document_code,
        "clear_document_code": row.clear_journal.document_code if row.clear_journal_id else "",
    }


def settlement_to_dict(row):
    return {
        "id": row.id,
        "supplier_id": row.supplier_id,
        "supplier_name": row.supplier.name,
        "kind": row.kind,
        "kind_label": row.get_kind_display(),
        "amount": _money(row.amount),
        "settled_on": row.settled_on.isoformat(),
        "is_void": row.is_void,
        "document_code": row.journal.document_code,
        "check_number": row.issued_check.check_number if getattr(row, "issued_check", None) else "",
        "allocations": [
            {"invoice_id": item.invoice_id, "invoice_number": item.invoice.invoice_number, "amount": _money(item.amount)}
            for item in row.allocations.all()
        ],
    }


def list_suppliers():
    rows = MaterialSupplier.objects.select_related("account").annotate(
        open_balance=Coalesce(
            Sum(F("invoices__payable_amount") - F("invoices__settled_amount")),
            Value(0),
        )
    )
    return [supplier_to_dict(row, _money(row.open_balance)) for row in rows]


def _invoice_queryset():
    return PurchaseInvoice.objects.select_related("supplier", "journal").prefetch_related("lines__material")


def list_invoices(as_of=None, *, open_only=False):
    day = as_of or date.today()
    open_rows = _invoice_queryset().filter(
        status__in=[PurchaseInvoice.STATUS_OPEN, PurchaseInvoice.STATUS_PARTIAL]
    ).order_by("due_date", "id")
    if open_only:
        return [invoice_to_dict(row, day) for row in open_rows]
    settled = _invoice_queryset().filter(status=PurchaseInvoice.STATUS_SETTLED).order_by("-id")[:30]
    return [invoice_to_dict(row, day) for row in list(open_rows) + list(settled)]


def list_checks(as_of=None):
    day = as_of or date.today()
    issued = PayableCheck.objects.select_related(
        "supplier", "settlement__journal", "clear_journal"
    ).filter(status=PayableCheck.STATUS_ISSUED).order_by("due_date", "id")
    rest = PayableCheck.objects.select_related(
        "supplier", "settlement__journal", "clear_journal"
    ).exclude(status=PayableCheck.STATUS_ISSUED).order_by("-id")[:40]
    return [check_to_dict(row, day) for row in list(issued) + list(rest)]


def list_settlements():
    rows = PayableSettlement.objects.select_related("supplier", "journal", "issued_check").prefetch_related(
        "allocations__invoice"
    ).order_by("-id")[:40]
    return [settlement_to_dict(row) for row in rows]


def _totals(invoices, checks):
    def invoice_sum(bucket):
        return sum(row["remaining"] for row in invoices if row["bucket"] == bucket)

    def check_sum(bucket):
        return sum(row["amount"] for row in checks if row["bucket"] == bucket)

    return {
        "open_payable": sum(row["remaining"] for row in invoices),
        "overdue_payable": invoice_sum("overdue"),
        "due_7_payable": invoice_sum("due_7"),
        "due_30_payable": invoice_sum("due_30"),
        "open_checks": check_sum("overdue") + check_sum("due_7") + check_sum("due_30") + check_sum("later"),
        "overdue_checks": check_sum("overdue"),
        "due_7_checks": check_sum("due_7"),
    }


def due_schedule(as_of=None):
    """سررسید فاکتورهای باز و چک‌های صادرشده."""
    day = _as_of(as_of)
    invoices = list_invoices(day, open_only=True)
    checks = [row for row in list_checks(day) if row["status"] == PayableCheck.STATUS_ISSUED]
    return {"as_of": day.isoformat(), "invoices": invoices, "checks": checks, **_totals(invoices, checks)}


def overview(as_of=None):
    day = _as_of(as_of)
    schedule = due_schedule(day)
    return {
        "as_of": day.isoformat(),
        "suppliers": list_suppliers(),
        "invoices": list_invoices(day),
        "checks": list_checks(day),
        "settlements": list_settlements(),
        "schedule": {key: value for key, value in schedule.items() if key not in {"invoices", "checks"}},
    }


def _credit_days(value):
    try:
        days = int(30 if value in (None, "") else value)
    except (TypeError, ValueError) as exc:
        raise ValueError("مهلت پرداخت نامعتبر است.") from exc
    if days < 0 or days > 365:
        raise ValueError("مهلت پرداخت باید بین ۰ و ۳۶۵ روز باشد.")
    return days


@transaction.atomic
def create_supplier(data, *, user=None):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("نام تامین‌کننده الزامی است.")
    parent = _controls()["payable"]
    code = _next_supplier_code()
    account = Account.objects.create(
        ledger=parent.ledger,
        parent=parent,
        slug=f"supplier-{code.lower()}",
        code=code,
        name=name[:120],
        account_class=parent.account_class,
        normal_balance=parent.normal_balance,
        sort_order=10,
    )
    supplier = MaterialSupplier.objects.create(
        code=code,
        name=name[:150],
        phone=(data.get("phone") or "").strip()[:20],
        national_id=(data.get("national_id") or "").strip()[:20],
        address=(data.get("address") or "").strip()[:300],
        credit_days=_credit_days(data.get("credit_days")),
        account=account,
    )
    return supplier_to_dict(supplier, 0)


def _locked_supplier(supplier_id):
    try:
        return MaterialSupplier.objects.select_for_update().select_related("account").get(pk=_pk(supplier_id, "تامین‌کننده"))
    except MaterialSupplier.DoesNotExist as exc:
        raise MaterialSupplier.DoesNotExist("تامین‌کننده پیدا نشد.") from exc


def _spread(rows, charges, goods_net):
    if charges == 0:
        for row in rows:
            row["inventory_raw"] = row["goods_net"]
        return
    if goods_net <= 0:
        for index, row in enumerate(rows):
            row["inventory_raw"] = row["goods_net"] + (charges if index == len(rows) - 1 else 0)
        return
    allocated = 0
    last = len(rows) - 1
    for index, row in enumerate(rows):
        if index == last:
            share = charges - allocated
        else:
            share = _portion(charges, row["goods_net"], goods_net)
            if allocated + share > charges:
                share = charges - allocated
            allocated += share
        row["inventory_raw"] = row["goods_net"] + share


def _store_cost(row):
    raw = row["inventory_raw"]
    if raw <= 0:
        raise ValueError("بهای تمام‌شده هر ردیف باید بزرگ‌تر از صفر باشد.")
    unit = _money(Decimal(raw) / Decimal(row["quantity"]))
    stored = _money(Decimal(unit) * Decimal(row["quantity"]))
    if stored <= 0:
        raise ValueError("بهای تمام‌شده ردیف پس از گرد کردن صفر شد.")
    row["unit_cost"] = unit
    row["inventory_amount"] = stored


def _price_lines(data):
    raw_lines = data.get("lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        raise ValueError("فاکتور باید حداقل یک ردیف کالا داشته باشد.")
    if len(raw_lines) > 40:
        raise ValueError("تعداد ردیف‌های فاکتور بیش از حد است.")
    rate = data.get("vat_rate", DEFAULT_VAT_RATE)
    rows = []
    for raw in raw_lines:
        priced = purchase_amounts(
            quantity=raw.get("quantity"),
            unit_price=raw.get("unit_price"),
            trade_discount=raw.get("trade_discount") or 0,
            freight=0,
            insurance=0,
            other_cost=0,
            vat_rate=0,
        )
        priced["material_id"] = _pk(raw.get("material_id"), "کالا")
        rows.append(priced)
    charges = _money(data.get("freight") or 0) + _money(data.get("insurance") or 0) + _money(data.get("other_cost") or 0)
    if _money(data.get("freight") or 0) < 0 or _money(data.get("insurance") or 0) < 0 or _money(data.get("other_cost") or 0) < 0:
        raise ValueError("مخارج خرید نمی‌تواند منفی باشد.")
    goods_net = sum(row["goods_net"] for row in rows)
    _spread(rows, charges, goods_net)
    for row in rows:
        _store_cost(row)
    vat_rate = parse_rate(rate)
    vat = _money(Decimal(goods_net) * vat_rate / Decimal(100))
    inventory = sum(row["inventory_amount"] for row in rows)
    if inventory <= 0:
        raise ValueError("بهای تمام‌شده خرید باید بزرگ‌تر از صفر باشد.")
    return rows, {
        "goods_net": goods_net,
        "charges": charges,
        "inventory_amount": inventory,
        "vat_rate": vat_rate,
        "vat_amount": vat,
        "payable": inventory + vat,
        "freight": _money(data.get("freight") or 0),
        "insurance": _money(data.get("insurance") or 0),
        "other_cost": _money(data.get("other_cost") or 0),
    }


@transaction.atomic
def post_purchase_invoice(data, *, user=None):
    """ثبت فاکتور خرید همزمان با رسید انبار و صدور سند موجودی / تامین‌کننده."""
    supplier = _locked_supplier(data.get("supplier_id"))
    if not supplier.is_active:
        raise ValueError("این تامین‌کننده غیرفعال است.")
    invoice_number = (data.get("invoice_number") or "").strip()
    receipt = (data.get("warehouse_receipt") or "").strip()
    if not invoice_number:
        raise ValueError("شماره فاکتور، سند مثبته است و باید وارد شود.")
    if not receipt:
        raise ValueError("شماره رسید انبار برای ثبت خرید لازم است.")
    if PurchaseInvoice.objects.filter(supplier=supplier, invoice_number=invoice_number).exists():
        raise ValueError("این شماره فاکتور برای تامین‌کننده قبلاً ثبت شده است.")
    invoice_date = _date(data.get("invoice_date") or date.today().isoformat(), "تاریخ فاکتور")
    if data.get("due_date"):
        due = _date(data.get("due_date"), "تاریخ سررسید")
    else:
        due = invoice_date + timedelta(days=supplier.credit_days)
    if due < invoice_date:
        raise ValueError("سررسید نمی‌تواند قبل از تاریخ فاکتور باشد.")
    rows, amounts = _price_lines(data)
    material_ids = sorted({row["material_id"] for row in rows})
    materials = {
        item.id: item
        for item in Material.objects.select_for_update().filter(pk__in=material_ids)
    }
    if len(materials) != len(material_ids):
        raise ValueError("کالا پیدا نشد.")
    names = []
    for row in rows:
        material = materials[row["material_id"]]
        names.append(material.name)
        row["material"] = material
    label = "، ".join(dict.fromkeys(names))
    if len(label) > 180:
        label = label[:177] + "…"
    accounts = _controls()
    journal = create_journal(
        lines=_lines([
            (accounts["inventory"], amounts["inventory_amount"], 0, f"ورود به انبار {receipt} — {label}"),
            (accounts["vat"], amounts["vat_amount"], 0, f"مالیات خرید {invoice_number}"),
            (supplier.account, 0, amounts["payable"], f"فاکتور {invoice_number} — {supplier.name}"),
        ]),
        entry_type="adjustment",
        description=f"خرید مواد — {supplier.name} — فاکتور {invoice_number}",
        entry_date=_noon(invoice_date),
        is_approved=False,
        ledger=LEGAL_LEDGER,
        user=_actor(user),
    )
    actor = _actor(user)
    try:
        invoice = PurchaseInvoice.objects.create(
            supplier=supplier,
            invoice_number=invoice_number[:60],
            warehouse_receipt=receipt[:60],
            invoice_date=invoice_date,
            due_date=due,
            goods_net=amounts["goods_net"],
            charges=amounts["charges"],
            inventory_amount=amounts["inventory_amount"],
            vat_rate=amounts["vat_rate"],
            vat_amount=amounts["vat_amount"],
            payable_amount=amounts["payable"],
            description=(data.get("description") or "").strip()[:300],
            journal=journal,
            created_by=actor,
        )
    except IntegrityError as exc:
        raise ValueError("این شماره فاکتور برای تامین‌کننده قبلاً ثبت شده است.") from exc
    warnings = []
    for index, row in enumerate(rows, 1):
        material = row["material"]
        move = receive_stock(
            material,
            row["quantity"],
            row["unit_cost"],
            reason="purchase",
            reference=f"ap:{invoice_number}",
            recorded_by=actor,
        )
        PurchaseInvoiceLine.objects.create(
            invoice=invoice,
            material=material,
            quantity=row["quantity"],
            unit_price=row["unit_price"],
            trade_discount=row["trade_discount"],
            goods_net=row["goods_net"],
            inventory_amount=row["inventory_amount"],
            unit_cost=row["unit_cost"],
            inventory_move=move,
            line_number=index,
        )
        point = Decimal(material.reorder_point or 0)
        if point > 0 and Decimal(material.stock or 0) <= point:
            warnings.append(f"موجودی {material.name} به نقطه سفارش رسیده است.")
    payload = invoice_to_dict(invoice, invoice_date)
    payload["warning"] = " ".join(warnings)
    payload["amounts"] = {
        "inventory_amount": amounts["inventory_amount"],
        "vat_amount": amounts["vat_amount"],
        "payable": amounts["payable"],
        "goods_net": amounts["goods_net"],
        "charges": amounts["charges"],
    }
    return payload


def _refresh_invoice(invoice):
    remaining = _remaining(invoice)
    if remaining < 0:
        raise ValueError("مانده فاکتور منفی شده است.")
    if remaining == 0:
        invoice.status = PurchaseInvoice.STATUS_SETTLED
    elif _money(invoice.settled_amount) > 0:
        invoice.status = PurchaseInvoice.STATUS_PARTIAL
    else:
        invoice.status = PurchaseInvoice.STATUS_OPEN
    invoice.save(update_fields=["settled_amount", "status"])


def _apply_allocations(rows):
    for invoice, amount in rows:
        invoice.settled_amount = _money(invoice.settled_amount) + amount
        _refresh_invoice(invoice)


def _release_allocations(settlement):
    for allocation in settlement.allocations.select_related("invoice"):
        invoice = PurchaseInvoice.objects.select_for_update().get(pk=allocation.invoice_id)
        invoice.settled_amount = _money(invoice.settled_amount) - _money(allocation.amount)
        if _money(invoice.settled_amount) < 0:
            raise ValueError("برگشت تسویه از مانده پرداخت‌شده فاکتور بیشتر است.")
        _refresh_invoice(invoice)


def _allocate(supplier, data):
    raw = data.get("allocations") or []
    stated = data.get("amount")
    if raw:
        if not isinstance(raw, list):
            raise ValueError("تخصیص تسویه نامعتبر است.")
        rows = []
        seen = set()
        for item in raw:
            invoice = PurchaseInvoice.objects.select_for_update().get(
                pk=_pk(item.get("invoice_id"), "فاکتور"),
                supplier=supplier,
            )
            if invoice.id in seen:
                raise ValueError("یک فاکتور دوبار در تسویه آمده است.")
            seen.add(invoice.id)
            amount = _money(item.get("amount"))
            if amount <= 0:
                raise ValueError("مبلغ تسویه هر فاکتور باید بزرگ‌تر از صفر باشد.")
            if amount > _remaining(invoice):
                raise ValueError(f"مبلغ تسویه از مانده فاکتور {invoice.invoice_number} بیشتر است.")
            rows.append((invoice, amount))
        total = sum(amount for _invoice, amount in rows)
        if stated not in (None, ""):
            if _money(stated) != total:
                raise ValueError("مبلغ پرداخت با جمع تسویه فاکتورها برابر نیست.")
        if total <= 0:
            raise ValueError("مبلغ پرداخت باید بزرگ‌تر از صفر باشد.")
        return rows, total
    if stated in (None, ""):
        raise ValueError("مبلغ پرداخت یا فاکتورهای قابل تسویه را مشخص کنید.")
    total = _money(stated)
    if total <= 0:
        raise ValueError("مبلغ پرداخت باید بزرگ‌تر از صفر باشد.")
    left = total
    rows = []
    invoices = PurchaseInvoice.objects.select_for_update().filter(
        supplier=supplier,
        status__in=[PurchaseInvoice.STATUS_OPEN, PurchaseInvoice.STATUS_PARTIAL],
    ).order_by("due_date", "id")
    for invoice in invoices:
        if left <= 0:
            break
        room = _remaining(invoice)
        if room <= 0:
            continue
        take = min(room, left)
        rows.append((invoice, take))
        left -= take
    if left > 0:
        raise ValueError("مبلغ پرداخت از مانده فاکتورهای باز این تامین‌کننده بیشتر است.")
    if not rows:
        raise ValueError("فاکتور بازی برای تسویه وجود ندارد.")
    return rows, total


def _remember_settlement(supplier, kind, total, day, rows, journal, user):
    settlement = PayableSettlement.objects.create(
        supplier=supplier,
        kind=kind,
        amount=total,
        settled_on=day,
        journal=journal,
        created_by=_actor(user),
    )
    PayableAllocation.objects.bulk_create([
        PayableAllocation(settlement=settlement, invoice=invoice, amount=amount)
        for invoice, amount in rows
    ])
    _apply_allocations(rows)
    return settlement


@transaction.atomic
def issue_payable_check(data, *, user=None):
    """صدور چک: بدهکار تامین‌کننده، بستانکار اسناد پرداختنی، و تسویه فاکتورها."""
    supplier = _locked_supplier(data.get("supplier_id"))
    number = (data.get("check_number") or "").strip()
    bank_name = (data.get("bank_name") or "").strip()
    if not number:
        raise ValueError("شماره چک الزامی است.")
    if not bank_name:
        raise ValueError("نام بانک چک الزامی است.")
    if PayableCheck.objects.filter(supplier=supplier, check_number=number).exists():
        raise ValueError("این شماره چک برای تامین‌کننده قبلاً ثبت شده است.")
    issue_date = _date(data.get("issue_date") or date.today().isoformat(), "تاریخ صدور")
    due = _date(data.get("due_date"), "تاریخ سررسید")
    if due < issue_date:
        raise ValueError("سررسید چک نمی‌تواند قبل از تاریخ صدور باشد.")
    rows, total = _allocate(supplier, data)
    notes = notes_account()
    journal = create_journal(
        lines=_lines([
            (supplier.account, total, 0, f"چک {number} — {supplier.name}"),
            (notes, 0, total, f"اسناد پرداختنی چک {number}"),
        ]),
        entry_type="payment",
        description=f"صدور چک پرداختی {number} — {supplier.name}",
        entry_date=_noon(issue_date),
        is_approved=False,
        ledger=LEGAL_LEDGER,
        user=_actor(user),
    )
    settlement = _remember_settlement(
        supplier, PayableSettlement.KIND_CHECK, total, issue_date, rows, journal, user,
    )
    try:
        check = PayableCheck.objects.create(
            supplier=supplier,
            settlement=settlement,
            check_number=number[:40],
            bank_name=bank_name[:80],
            amount=total,
            issue_date=issue_date,
            due_date=due,
        )
    except IntegrityError as exc:
        raise ValueError("این شماره چک برای تامین‌کننده قبلاً ثبت شده است.") from exc
    payload = check_to_dict(PayableCheck.objects.select_related(
        "supplier", "settlement__journal", "clear_journal"
    ).get(pk=check.pk), issue_date)
    payload["allocations"] = [
        {"invoice_id": invoice.id, "invoice_number": invoice.invoice_number, "amount": amount}
        for invoice, amount in rows
    ]
    return payload


@transaction.atomic
def settle_invoices(data, *, user=None):
    """تسویه فاکتور با بانک یا صندوق، بدون چک."""
    supplier = _locked_supplier(data.get("supplier_id"))
    kind = (data.get("method") or PayableSettlement.KIND_BANK).strip()
    if kind not in {PayableSettlement.KIND_BANK, PayableSettlement.KIND_CASH}:
        raise ValueError("نحوه تسویه باید بانک یا صندوق باشد.")
    settled_on = _date(data.get("settled_on") or date.today().isoformat(), "تاریخ تسویه")
    rows, total = _allocate(supplier, data)
    accounts = _controls()
    credit = accounts["cash"] if kind == PayableSettlement.KIND_CASH else accounts["bank"]
    label = "صندوق" if kind == PayableSettlement.KIND_CASH else "بانک"
    journal = create_journal(
        lines=_lines([
            (supplier.account, total, 0, f"تسویه {supplier.name}"),
            (credit, 0, total, f"پرداخت از {label}"),
        ]),
        entry_type="payment",
        description=f"تسویه حساب {supplier.name} از {label}",
        entry_date=_noon(settled_on),
        is_approved=False,
        ledger=LEGAL_LEDGER,
        user=_actor(user),
    )
    settlement = _remember_settlement(supplier, kind, total, settled_on, rows, journal, user)
    payload = settlement_to_dict(
        PayableSettlement.objects.select_related("supplier", "journal").prefetch_related(
            "allocations__invoice"
        ).get(pk=settlement.pk)
    )
    return payload


def _locked_check(check_id):
    try:
        return PayableCheck.objects.select_for_update().select_related(
            "supplier__account", "settlement", "clear_journal"
        ).get(pk=_pk(check_id, "چک"))
    except PayableCheck.DoesNotExist as exc:
        raise PayableCheck.DoesNotExist("چک پیدا نشد.") from exc


@transaction.atomic
def clear_payable_check(check_id, data=None, *, user=None):
    """پاس شدن چک: بدهکار اسناد پرداختنی، بستانکار بانک."""
    data = data or {}
    check = _locked_check(check_id)
    if check.status != PayableCheck.STATUS_ISSUED:
        raise ValueError("فقط چک صادرشده قابل پاس شدن است.")
    cleared_on = _date(data.get("cleared_on") or date.today().isoformat(), "تاریخ پاس شدن")
    if cleared_on < check.issue_date:
        raise ValueError("تاریخ پاس شدن نمی‌تواند قبل از صدور چک باشد.")
    amount = _money(check.amount)
    notes = notes_account()
    bank = _controls()["bank"]
    journal = create_journal(
        lines=_lines([
            (notes, amount, 0, f"پاس شدن چک {check.check_number}"),
            (bank, 0, amount, f"بانک — چک {check.check_number}"),
        ]),
        entry_type="payment",
        description=f"پاس شدن چک {check.check_number} — {check.supplier.name}",
        entry_date=_noon(cleared_on),
        is_approved=False,
        ledger=LEGAL_LEDGER,
        user=_actor(user),
    )
    check.status = PayableCheck.STATUS_CLEARED
    check.cleared_on = cleared_on
    check.clear_journal = journal
    check.save(update_fields=["status", "cleared_on", "clear_journal"])
    return check_to_dict(PayableCheck.objects.select_related(
        "supplier", "settlement__journal", "clear_journal"
    ).get(pk=check.pk), cleared_on)


@transaction.atomic
def void_payable_check(check_id, data=None, *, user=None):
    """ابطال چک صادرشده و برگشت مانده فاکتورهایی که با آن تسویه شده بودند."""
    check = _locked_check(check_id)
    if check.status != PayableCheck.STATUS_ISSUED:
        raise ValueError("فقط چک صادرشده و هنوز پاس‌نشده قابل ابطال است.")
    amount = _money(check.amount)
    notes = notes_account()
    journal = create_journal(
        lines=_lines([
            (notes, amount, 0, f"ابطال چک {check.check_number}"),
            (check.supplier.account, 0, amount, f"برگشت بدهی {check.supplier.name}"),
        ]),
        entry_type="payment",
        description=f"ابطال چک {check.check_number} — {check.supplier.name}",
        entry_date=_noon(date.today()),
        is_approved=False,
        ledger=LEGAL_LEDGER,
        user=_actor(user),
    )
    settlement = PayableSettlement.objects.select_for_update().get(pk=check.settlement_id)
    _release_allocations(settlement)
    settlement.is_void = True
    settlement.save(update_fields=["is_void"])
    check.status = PayableCheck.STATUS_VOID
    check.clear_journal = journal
    check.save(update_fields=["status", "clear_journal"])
    return check_to_dict(PayableCheck.objects.select_related(
        "supplier", "settlement__journal", "clear_journal"
    ).get(pk=check.pk))


def account_balance(account):
    """مانده حساب با ماهیت بستانکار: بستانکار منهای بدهکار."""
    totals = JournalLine.objects.filter(account=account, journal__status="posted").aggregate(
        debit=Coalesce(Sum("debit"), Value(0)),
        credit=Coalesce(Sum("credit"), Value(0)),
    )
    return _money(totals["credit"]) - _money(totals["debit"])
