"""مراکز هزینه، تسهیم سربار، آحاد معادل و ضایعات عادی."""

from decimal import Decimal, ROUND_DOWN

from django.db import transaction
from django.utils.dateparse import parse_date

from backend.models import (
    CostCenter,
    InventoryTransaction,
    Ledger,
    OverheadAllocationLine,
    OverheadPeriod,
    ProductMaterial,
    WorkshopRecipeMaterial,
    WipClose,
)
from logic.accounting import create_journal
from logic.accounting_accounts import get_account
from logic.accounting_events import issue_event_draft, register_event
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.ledger import LEGAL_LEDGER


def _ledger_row(ledger=LEGAL_LEDGER):
    return Ledger.objects.get(code=ledger.id)


def _decimal(value, label):
    try:
        amount = Decimal(str(value if value is not None else 0))
    except Exception as exc:
        raise ValueError(f"{label} نامعتبر است.") from exc
    return amount


def cost_center_to_dict(center):
    return {
        "id": center.id,
        "code": center.code,
        "name": center.name,
        "kind": center.kind,
        "kind_label": center.get_kind_display(),
        "allocation_base": center.allocation_base,
        "allocation_base_label": center.get_allocation_base_display(),
        "base_quantity": float(center.base_quantity or 0),
        "branch": center.branch_id or "",
        "is_active": center.is_active,
    }


def list_cost_centers(*, ledger=LEGAL_LEDGER):
    rows = CostCenter.objects.filter(ledger__code=ledger.id).order_by("code")
    return [cost_center_to_dict(row) for row in rows]


@transaction.atomic
def save_cost_center(data, *, center=None, ledger=LEGAL_LEDGER):
    code = (data.get("code") or "").strip()
    name = (data.get("name") or "").strip()
    if not code or not name:
        raise ValueError("کد و نام مرکز هزینه الزامی است.")
    kind = (data.get("kind") or CostCenter.KIND_PRODUCTION).strip()
    if kind not in dict(CostCenter.KIND_CHOICES):
        raise ValueError("نوع مرکز هزینه نامعتبر است.")
    base = (data.get("allocation_base") or CostCenter.BASE_MACHINE_HOURS).strip()
    if base not in dict(CostCenter.BASE_CHOICES):
        raise ValueError("مبنای تسهیم نامعتبر است.")
    quantity = _decimal(data.get("base_quantity"), "مقدار مبنا")
    if quantity < 0:
        raise ValueError("مقدار مبنا نمی‌تواند منفی باشد.")
    ledger_row = _ledger_row(ledger)
    branch = (data.get("branch") or "").strip() or None
    if branch:
        from backend.models import Branch
        if not Branch.objects.filter(code=branch).exists():
            raise ValueError("شعبه یافت نشد.")
    if center is None:
        if CostCenter.objects.filter(ledger=ledger_row, code=code).exists():
            raise ValueError("این کد مرکز هزینه قبلاً ثبت شده است.")
        center = CostCenter(ledger=ledger_row, code=code)
    elif CostCenter.objects.filter(ledger=ledger_row, code=code).exclude(pk=center.pk).exists():
        raise ValueError("این کد مرکز هزینه قبلاً ثبت شده است.")
    center.code = code
    center.name = name
    center.kind = kind
    center.allocation_base = base
    center.base_quantity = quantity
    center.branch_id = branch
    if "is_active" in data:
        center.is_active = bool(data.get("is_active"))
    center.save()
    return cost_center_to_dict(center)


def overhead_to_dict(period):
    lines = [
        {
            "cost_center_id": line.cost_center_id,
            "cost_center_name": line.cost_center.name,
            "base_quantity": float(line.base_quantity or 0),
            "share_amount": int(line.share_amount or 0),
        }
        for line in period.lines.select_related("cost_center")
    ]
    journal = period.journal
    return {
        "id": period.id,
        "year": period.year,
        "month": period.month,
        "amount": int(period.amount or 0),
        "status": period.status,
        "status_label": period.get_status_display(),
        "document_code": journal.document_code if journal else "",
        "journal_status": journal.status if journal else "",
        "lines": lines,
    }


def list_overhead_periods(*, ledger=LEGAL_LEDGER):
    rows = OverheadPeriod.objects.filter(ledger__code=ledger.id).prefetch_related("lines__cost_center")
    return [overhead_to_dict(row) for row in rows]


@transaction.atomic
def save_overhead_period(data, *, ledger=LEGAL_LEDGER):
    year = int(data.get("year") or 0)
    month = int(data.get("month") or 0)
    amount = _decimal(data.get("amount"), "مبلغ استخر")
    if year < 1300 or not 1 <= month <= 12:
        raise ValueError("سال و ماه دوره نامعتبر است.")
    if amount <= 0:
        raise ValueError("مبلغ استخر باید بزرگ‌تر از صفر باشد.")
    ledger_row = _ledger_row(ledger)
    period, _created = OverheadPeriod.objects.get_or_create(
        ledger=ledger_row, year=year, month=month, defaults={"amount": amount}
    )
    if period.journal_id and period.journal.status == period.journal.STATUS_POSTED:
        raise ValueError("سند تسهیم این دوره ثبت قطعی شده و قابل تغییر نیست.")
    period.amount = amount
    period.status = OverheadPeriod.STATUS_DRAFT
    period.save(update_fields=["amount", "status"])
    return overhead_to_dict(period)


def _share_amounts(centers, amount):
    total_base = sum(Decimal(center.base_quantity or 0) for center in centers)
    if total_base <= 0:
        raise ValueError("برای تسهیم، حداقل یک مرکز با مقدار مبنای مثبت لازم است.")
    amount_int = int(amount)
    shares = []
    used = 0
    usable = [center for center in centers if Decimal(center.base_quantity or 0) > 0]
    for index, center in enumerate(usable):
        if index == len(usable) - 1:
            share = amount_int - used
        else:
            raw = Decimal(amount_int) * Decimal(center.base_quantity) / total_base
            share = int(raw.to_integral_value(rounding=ROUND_DOWN))
            used += share
        if share > 0:
            shares.append((center, share))
    if not shares:
        raise ValueError("مبلغ استخر برای تسهیم کافی نیست.")
    return shares


@transaction.atomic
def allocate_overhead(period_id, *, user=None, ledger=LEGAL_LEDGER):
    period = OverheadPeriod.objects.select_for_update().get(pk=period_id, ledger__code=ledger.id)
    if period.journal_id and period.journal.status == period.journal.STATUS_POSTED:
        raise ValueError("سند تسهیم این دوره قبلاً ثبت قطعی شده است.")
    if period.journal_id and period.journal.status != period.journal.STATUS_VOID:
        period.journal.status = period.journal.STATUS_VOID
        period.journal.posted_at = None
        period.journal.save(update_fields=["status", "posted_at"])
    centers = list(
        CostCenter.objects.filter(ledger=period.ledger, is_active=True).order_by("code")
    )
    shares = _share_amounts(centers, period.amount)
    wip = get_account(ACCOUNT_SLUGS.WIP_INVENTORY, ledger=ledger)
    overhead = get_account(ACCOUNT_SLUGS.PRODUCTION_OVERHEAD, ledger=ledger)
    description = f"تسهیم سربار {period.year}/{period.month:02d}"
    lines = [
        {
            "account": wip,
            "debit": share,
            "credit": 0,
            "description": f"{description} — {center.name}",
            "cost_center": center,
        }
        for center, share in shares
    ]
    lines.append({
        "account": overhead,
        "debit": 0,
        "credit": int(period.amount),
        "description": description,
    })
    journal = create_journal(
        lines=lines,
        entry_type="adjustment",
        description=description,
        is_approved=False,
        ledger=ledger,
        user=user,
    )
    period.lines.all().delete()
    OverheadAllocationLine.objects.bulk_create([
        OverheadAllocationLine(
            period=period,
            cost_center=center,
            base_quantity=center.base_quantity,
            share_amount=share,
        )
        for center, share in shares
    ])
    period.journal = journal
    period.status = OverheadPeriod.STATUS_ALLOCATED
    period.save(update_fields=["journal", "status"])
    return overhead_to_dict(period)


def wip_to_dict(row):
    return {
        "id": row.id,
        "year": row.year,
        "month": row.month,
        "product_id": row.product_id,
        "product_name": row.product.name if row.product_id else "",
        "recipe_id": row.recipe_id,
        "recipe_name": row.recipe.name if row.recipe_id else "",
        "completed_units": float(row.completed_units or 0),
        "ending_wip_units": float(row.ending_wip_units or 0),
        "percent_complete": float(row.percent_complete or 0),
        "equivalent_units": float(row.equivalent_units or 0),
        "material_cost": int(row.material_cost or 0),
        "labor_cost": int(row.labor_cost or 0),
        "overhead_cost": int(row.overhead_cost or 0),
        "document_code": row.journal.document_code if row.journal_id else "",
        "notes": row.notes or "",
    }


def list_wip_closes(*, ledger=LEGAL_LEDGER):
    rows = WipClose.objects.filter(ledger__code=ledger.id).select_related("product", "recipe")
    return [wip_to_dict(row) for row in rows]


@transaction.atomic
def save_wip_close(data, *, ledger=LEGAL_LEDGER):
    year = int(data.get("year") or 0)
    month = int(data.get("month") or 0)
    if year < 1300 or not 1 <= month <= 12:
        raise ValueError("سال و ماه دوره نامعتبر است.")
    completed = _decimal(data.get("completed_units"), "تعداد تکمیل‌شده")
    ending = _decimal(data.get("ending_wip_units"), "کالای نیمه‌کاره")
    percent = _decimal(data.get("percent_complete"), "درصد تکمیل")
    material_cost = _decimal(data.get("material_cost"), "هزینه مواد")
    labor_cost = _decimal(data.get("labor_cost"), "هزینه دستمزد")
    overhead_cost = _decimal(data.get("overhead_cost"), "هزینه سربار")
    if completed < 0 or ending < 0 or percent < 0 or percent > 100:
        raise ValueError("مقادیر بستن کالای در جریان ساخت نامعتبر است.")
    if min(material_cost, labor_cost, overhead_cost) < 0:
        raise ValueError("هزینه‌های بستن کالای در جریان نمی‌توانند منفی باشند.")
    product_id = data.get("product_id") or None
    recipe_id = data.get("recipe_id") or None
    row = WipClose(
        ledger=_ledger_row(ledger),
        year=year,
        month=month,
        product_id=int(product_id) if product_id else None,
        recipe_id=int(recipe_id) if recipe_id else None,
        completed_units=completed,
        ending_wip_units=ending,
        percent_complete=percent,
        material_cost=material_cost,
        labor_cost=labor_cost,
        overhead_cost=overhead_cost,
        notes=(data.get("notes") or "").strip(),
    )
    row.save()
    total_cost = material_cost + labor_cost + overhead_cost
    if total_cost > 0:
        finished_goods = get_account(ACCOUNT_SLUGS.FINISHED_GOODS_INVENTORY, ledger=ledger)
        wip = get_account(ACCOUNT_SLUGS.WIP_INVENTORY, ledger=ledger)
        description = f"انتقال کالای تکمیل‌شده از WIP — {year}/{month:02d}"
        event, _created = register_event(
            source_module="production",
            source_type="WipClose",
            source=row.pk,
            event_type="wip_completed",
            payload={
                "material_cost": str(material_cost),
                "labor_cost": str(labor_cost),
                "overhead_cost": str(overhead_cost),
                "total_cost": str(total_cost),
            },
        )
        row.journal = issue_event_draft(
            event,
            lines=[
                {"account": finished_goods, "debit": total_cost, "credit": 0, "description": description},
                {"account": wip, "debit": 0, "credit": total_cost, "description": description},
            ],
            entry_type="adjustment",
            description=description,
        )
        row.save(update_fields=["journal"])
    return wip_to_dict(row)


def _rate_for_material(material_id, product_ids):
    rates = list(
        ProductMaterial.objects.filter(material_id=material_id, product_id__in=product_ids)
        .values_list("normal_spoilage_rate", flat=True)
    )
    rates.extend(
        WorkshopRecipeMaterial.objects.filter(material_id=material_id)
        .filter(recipe__products_paint__id__in=product_ids)
        .values_list("normal_spoilage_rate", flat=True)
    )
    for field in ("products_fabric", "products_foam", "products_cushion", "products_webbing"):
        rates.extend(
            WorkshopRecipeMaterial.objects.filter(material_id=material_id)
            .filter(**{f"recipe__{field}__id__in": product_ids})
            .values_list("normal_spoilage_rate", flat=True)
        )
    if not rates:
        return Decimal(0)
    return max(Decimal(rate or 0) for rate in rates)


def spoilage_report(*, date_from="", date_to=""):
    from backend.models import Sale
    from logic.materials import compute_factory_order_material_requirements

    qs = InventoryTransaction.objects.filter(
        reason="production_consumption", quantity__lt=0, material__isnull=False
    ).select_related("material")
    start = parse_date(date_from) if date_from else None
    end = parse_date(date_to) if date_to else None
    if start:
        qs = qs.filter(created_at__date__gte=start)
    if end:
        qs = qs.filter(created_at__date__lte=end)
    rows = []
    for tx in qs.order_by("-created_at")[:300]:
        actual = -Decimal(tx.quantity)
        standard = Decimal(0)
        rate = Decimal(0)
        reference = tx.reference or ""
        sale_id = None
        if reference.startswith("sale:"):
            try:
                sale_id = int(reference.split(":", 1)[1])
            except ValueError:
                sale_id = None
        if sale_id:
            sale = Sale.objects.filter(pk=sale_id).first()
            if sale:
                product_ids = list(sale.line_items.values_list("product_id", flat=True))
                product_ids = [pk for pk in product_ids if pk]
                rate = _rate_for_material(tx.material_id, product_ids)
                for item in compute_factory_order_material_requirements(sale, queue_aware=False):
                    if item.get("material_id") == tx.material_id:
                        standard += Decimal(str(item.get("required_quantity") or 0))
        allowed = standard * (Decimal(1) + rate / Decimal(100))
        abnormal = standard > 0 and actual > allowed
        abnormal_quantity = max(Decimal(0), actual - allowed) if abnormal else Decimal(0)
        abnormal_amount = (abnormal_quantity * Decimal(tx.unit_cost or tx.material.unit_cost or 0)).quantize(
            Decimal("1")
        )
        rows.append({
            "material_id": tx.material_id,
            "material_name": tx.material.name,
            "actual_quantity": float(actual),
            "standard_quantity": float(standard),
            "spoilage_rate": float(rate),
            "allowed_quantity": float(allowed),
            "abnormal": abnormal,
            "abnormal_quantity": float(abnormal_quantity),
            "abnormal_amount": int(abnormal_amount),
            "reference": reference,
            "created_at": tx.created_at.isoformat(),
        })
    return {"results": rows, "abnormal_count": sum(1 for row in rows if row["abnormal"])}


@transaction.atomic
def post_abnormal_spoilage(*, date_from="", date_to="", user=None, ledger=LEGAL_LEDGER):
    report = spoilage_report(date_from=date_from, date_to=date_to)
    amount = sum(int(row.get("abnormal_amount") or 0) for row in report["results"])
    if amount <= 0:
        raise ValueError("ضایعات غیرعادی دارای مبلغی برای ثبت نیست.")
    expense = get_account(ACCOUNT_SLUGS.ADMIN_OVERHEAD, ledger=ledger)
    wip = get_account(ACCOUNT_SLUGS.WIP_INVENTORY, ledger=ledger)
    key = f"{date_from or 'start'}:{date_to or 'end'}"
    description = f"شناسایی ضایعات غیرعادی {key}"
    event, _created = register_event(
        source_module="production",
        source_type="SpoilagePeriod",
        source=key,
        event_type="abnormal_spoilage",
        payload={"amount": amount, "count": report["abnormal_count"]},
    )
    journal = issue_event_draft(
        event,
        lines=[
            {"account": expense, "debit": amount, "credit": 0, "description": description},
            {"account": wip, "debit": 0, "credit": amount, "description": description},
        ],
        entry_type="adjustment",
        description=description,
        user=user,
    )
    return {
        **report,
        "document_code": journal.document_code,
        "journal_status": journal.status,
        "amount": amount,
    }
